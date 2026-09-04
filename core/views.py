import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView

from .forms import CambioPasswordForm, ComentarioForm, TicketForm
from ai.tasks import _ejecutar_analisis
from ai.providers import RetryableProviderError
from .models import (
    Adjunto,
    AnalisisIA,
    Comentario,
    EstadoTicket,
    RolUsuario,
    Sistema,
    Ticket,
    TicketDesarrollador,
    TipoAdjunto,
    TipoAnalisis,
)


def _tipo_por_nombre(nombre):
    ext = os.path.splitext(nombre)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"):
        return TipoAdjunto.IMAGEN
    return TipoAdjunto.DOCUMENTO


def _guardar_adjuntos(archivos, *, ticket=None, comentario=None, usuario):
    """Guarda los archivos subidos, asignando el ticket o comentario correspondiente.
    `archivos` es una lista de UploadedFile (campo múltiple 'archivos')."""
    guardados = []
    for archivo in archivos:
        adj = Adjunto(
            ticket=ticket,
            comentario=comentario,
            subido_por=usuario,
            archivo=archivo,
            nombre_archivo=os.path.basename(archivo.name),
            tipo_archivo=_tipo_por_nombre(archivo.name),
        )
        adj.save()
        guardados.append(adj)
    return guardados


def _eliminar_adjuntos(adjuntos):
    """Elimina de BD y borra el archivo físico de cada adjunto."""
    for adj in adjuntos:
        if adj.archivo:
            adj.archivo.delete(save=False)
        adj.delete()


def _es_participante_activo(usuario, ticket):
    """El dueño (solicitante) o un desarrollador/coordinador que colabora
    activamente (NO liberado) en el ticket."""
    if usuario.pk == ticket.solicitante_id:
        return True
    return ticket.ticketdesarrollador_set.filter(
        usuario=usuario, activo=True
    ).exists()


def _puede_comentar(usuario, ticket):
    """Solo el creador del ticket y los desarrolladores que lo están trabajando
    (colaboradores ACTIVOS, no liberados) pueden comentar, y solo
    si el ticket no está cerrado. Superuser también queda sujeto a estas reglas."""
    if ticket.estado == EstadoTicket.CERRADO:
        return False
    return _es_participante_activo(usuario, ticket)


def _sistemas_visibles(usuario):
    """Sistemas a los que el usuario tiene acceso (vía UsuarioSistema)."""
    return Sistema.objects.filter(usuariosistema__usuario=usuario)


class CambiarPasswordView(LoginRequiredMixin, PasswordChangeView):
    template_name = "core/password_change.html"
    form_class = CambioPasswordForm
    success_url = reverse_lazy("ticket_list")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, "Contraseña actualizada correctamente.")
        return respuesta


class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "core/ticket_list.html"
    context_object_name = "tickets"

    @property
    def _modo_cliente(self):
        return getattr(settings, "MODO_FILTRO_CLIENTE", False)

    def get_paginate_by(self, queryset):
        # En modo cliente traemos todo el dataset del usuario (sin paginar);
        # el filtrado y paginacion ocurren en el navegador (estilo Angular Material).
        # Si el volumen crece y baja el rendimiento, pasar a modo server.
        if self._modo_cliente:
            return None
        return 20

    def get_queryset(self):
        usuario = self.request.user
        # Orden por defecto: numero de ticket (pk) descendente (mas nuevos primero)
        qs = Ticket.objects.select_related("sistema", "solicitante").order_by("-pk")

        if usuario.is_superuser:
            pass  # superuser ve todos los tickets sin restricción
        elif usuario.rol == RolUsuario.SOLICITANTE:
            qs = qs.filter(solicitante=usuario)
        else:
            # Desarrollador (o Coordinador a futuro): ve tickets de sus sistemas
            qs = qs.filter(sistema__in=_sistemas_visibles(usuario))

        # En modo cliente los filtros son del navegador (JS); el server solo
        # aplica la visibilidad por rol para entregar todo el dataset.
        if not self._modo_cliente:
            sistema_id = self.request.GET.get("sistema")
            if sistema_id:
                qs = qs.filter(sistema_id=sistema_id)

            estado = self.request.GET.get("estado")
            if estado:
                qs = qs.filter(estado=estado)

            q = self.request.GET.get("q")
            if q:
                qs = qs.filter(titulo__icontains=q)

            # Filtro "tomado" relativo al desarrollador logueado (solo devs):
            #   por_mi    -> colaborador activo = el usuario actual
            #   por_otros -> ticket tomado (colab activo) pero NO por el usuario
            #   sin_tomar -> sin ningún colaborador activo
            tomado = self.request.GET.get("tomado")
            if tomado and usuario.rol == RolUsuario.DESARROLLADOR:
                if tomado == "por_mi":
                    qs = qs.filter(ticketdesarrollador__usuario=usuario, ticketdesarrollador__activo=True).distinct()
                elif tomado == "por_otros":
                    qs = qs.exclude(ticketdesarrollador__usuario=usuario, ticketdesarrollador__activo=True).filter(ticketdesarrollador__activo=True).distinct()
                elif tomado == "sin_tomar":
                    qs = qs.exclude(ticketdesarrollador__activo=True).distinct()

        # Prefetch de colaboradores activos (read-only) para pintar el badge
        # de ticket reabierto "tomado" (verde) vs "sin tomar" (rojo).
        qs = qs.prefetch_related(
            Prefetch(
                "ticketdesarrollador_set",
                queryset=TicketDesarrollador.objects.filter(activo=True),
                to_attr="colabs_activos",
            )
        )
        return qs

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["core/partials/ticket_table.html"]
        return ["core/ticket_list.html"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        usuario = self.request.user
        # Superuser ve todos los sistemas en el filtro (mismo bypass que get_queryset)
        if usuario.is_superuser:
            ctx["sistemas_disponibles"] = Sistema.objects.all()
        else:
            ctx["sistemas_disponibles"] = _sistemas_visibles(usuario)
        ctx["estados_disponibles"] = EstadoTicket.choices
        # Select "tomado/sin tomar" solo visible para desarrolladores
        ctx["es_desarrollador"] = usuario.rol == RolUsuario.DESARROLLADOR
        # Marcar "tomado" (tiene colaborador activo) por ticket para el badge.
        # Se asigna como atributo real de instancia porque resolver anotaciones
        # dentro de {% include ... with %} recursiona en Django.
        for t in ctx["tickets"]:
            t.tomado = bool(getattr(t, "colabs_activos", []))
            t.tomado_mi = any(
                td.usuario_id == usuario.pk
                for td in getattr(t, "colabs_activos", [])
            )
            t.nombres_colabs = ", ".join(
                (td.usuario.get_full_name() or td.usuario.username)
                for td in getattr(t, "colabs_activos", [])
            )
        return ctx


class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = "core/ticket_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.solicitante = self.request.user
        response = super().form_valid(form)
        _guardar_adjuntos(
            self.request.FILES.getlist("archivos"),
            ticket=self.object,
            usuario=self.request.user,
        )
        # Acá, en Fase 2, se dispara generar_analisis_ticket.delay(self.object.id)
        return response

    def get_success_url(self):
        return f"/tickets/{self.object.pk}/"


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = "core/ticket_detail.html"
    context_object_name = "ticket"

    def get_queryset(self):
        # Mismo criterio de visibilidad que el listado (con bypass de superuser)
        usuario = self.request.user
        qs = Ticket.objects.select_related("sistema", "solicitante").prefetch_related(
            "comentarios", "adjuntos", "desarrolladores", "analisis"
        )
        if usuario.is_superuser:
            return qs  # superuser ve cualquier ticket sin restricción de rol
        if usuario.rol == RolUsuario.SOLICITANTE:
            return qs.filter(solicitante=usuario)
        return qs.filter(sistema__in=_sistemas_visibles(usuario))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["comentario_form"] = ComentarioForm()
        ctx["puede_actuar"] = self._puede_actuar(self.request.user, self.object)
        ctx["puede_comentar"] = _puede_comentar(self.request.user, self.object)
        ctx["puede_liberar"] = self.object.ticketdesarrollador_set.filter(
            usuario=self.request.user, activo=True
        ).exists()
        ctx["puede_cerrar"] = self._puede_cerrar(self.request.user, self.object)
        ctx["puede_reabrir"] = self._puede_reabrir(self.request.user, self.object)
        ctx["puede_gestionar_comentarios"] = _es_participante_activo(
            self.request.user, self.object
        )
        ctx["tomado"] = self.object.ticketdesarrollador_set.filter(activo=True).exists()
        ctx["tomado_mi"] = self.object.ticketdesarrollador_set.filter(
            usuario=self.request.user, activo=True
        ).exists()
        # Análisis conceptual (Fase 2): el más reciente de tipo CONCEPTUAL.
        analisis = list(
            self.object.analisis.filter(tipo=TipoAnalisis.CONCEPTUAL)
        )
        ctx["analisis_conceptual"] = analisis[0] if analisis else None
        ctx["puede_analizar"] = self._puede_actuar(self.request.user, self.object)
        return ctx

    @staticmethod
    def _puede_cerrar(usuario, ticket):
        """Cualquier actor con rol de gestión (dueño solicitante, desarrollador,
        coordinador) puede cerrar un ticket abierto (EN_PROCESO, PENDIENTE,
        REABIERTO). No tiene sentido cerrar un ticket ya cerrado."""
        if ticket.estado == EstadoTicket.CERRADO:
            return False
        if usuario.rol in (RolUsuario.DESARROLLADOR, RolUsuario.COORDINADOR):
            return True
        return usuario.pk == ticket.solicitante_id

    @staticmethod
    def _puede_reabrir(usuario, ticket):
        """Solo actor con rol de gestión (dueño solicitante, desarrollador,
        coordinador) puede reabrir un ticket cerrado."""
        if ticket.estado != EstadoTicket.CERRADO:
            return False
        if usuario.rol in (RolUsuario.DESARROLLADOR, RolUsuario.COORDINADOR):
            return True
        return usuario.pk == ticket.solicitante_id

    @staticmethod
    def _puede_actuar(usuario, ticket):
        """El usuario ve la tarjeta de acciones si tiene al menos un botón
        disponible: todo actor con rol de gestión (dev, coor o dueño) puede
        actuar sobre el ticket en cualquier estado (cerrar, reabrir, tomar/liberar)."""
        if usuario.rol in (RolUsuario.DESARROLLADOR, RolUsuario.COORDINADOR):
            return True
        return usuario.pk == ticket.solicitante_id


@login_required
def tomar_ticket(request, pk):
    """Un desarrollador se suma como colaborador activo del ticket (sin sacar a los demás).
    Solo si el ticket está PENDIENTE pasa a EN_PROCESO (y se recuerda el estado previo
    para restaurarlo al liberar). Si está REABIERTO, se suma como colaborador pero el
    ticket sigue REABIERTO."""
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.user.rol != RolUsuario.DESARROLLADOR:
        raise PermissionDenied("Solo un desarrollador puede tomar un ticket.")
    # Si había liberado antes, vuelve a ser colaborador activo (mantiene el único registro).
    td, _ = TicketDesarrollador.objects.get_or_create(
        ticket=ticket, usuario=request.user
    )
    if not td.activo:
        td.activo = True
        td.save(update_fields=["activo"])
    if ticket.estado == EstadoTicket.PENDIENTE:
        ticket.estado_previo = ticket.estado
        ticket.estado = EstadoTicket.EN_PROCESO
        ticket.save(update_fields=["estado", "estado_previo"])
    return redirect("ticket_detail", pk=pk)


@login_required
def liberar_ticket(request, pk):
    """Un desarrollador/coordinador deja de trabajar el ticket (libera).
    Se conserva el histórico de participación (activo=False) pero ya no puede comentar.
    Si era el último colaborador activo: un EN_PROCESO vuelve a su estado previo
    (PENDIENTE), mientras que un REABIERTO queda REABIERTO (rojo, sin tomar)."""
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    es_dev_coor = request.user.rol in (RolUsuario.DESARROLLADOR, RolUsuario.COORDINADOR)
    if not es_dev_coor:
        raise PermissionDenied("Solo desarrollador/coordinador puede liberar un ticket.")
    td = TicketDesarrollador.objects.filter(ticket=ticket, usuario=request.user).first()
    if td is None or not td.activo:
        raise PermissionDenied("No sos colaborador activo de este ticket.")
    td.activo = False
    td.save(update_fields=["activo"])

    quedan_activos = ticket.ticketdesarrollador_set.filter(activo=True).exists()
    if not quedan_activos:
        # Un EN_PROCESO liberado por el último colaborador vuelve al estado previo
        # (PENDIENTE, ya que desde REABIERTO ya no se pasa a EN_PROCESO). Un REABIERTO
        # tomado y luego liberado queda REABIERTO (rojo, sin tomar): no cambia de estado.
        if ticket.estado == EstadoTicket.EN_PROCESO:
            ticket.estado = ticket.estado_previo or EstadoTicket.PENDIENTE
        ticket.estado_previo = None
        ticket.save(update_fields=["estado", "estado_previo"])
    return redirect("ticket_detail", pk=pk)


@login_required
def cambiar_estado_ticket(request, pk):
    """Cambio de estado por transicion, acotado por rol (sin select genérico).
    - Cualquier estado abierto (EN_PROCESO/PENDIENTE/REABIERTO) -> CERRADO:
      dueño, desarrollador o coordinador.
    - CERRADO -> REABIERTO: dueño, desarrollador o coordinador. Si lo reabre
      un desarrollador que no era colaborador, pasa a ser colaborador activo."""
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    nuevo_estado = request.POST.get("estado")
    es_actor_gestion = (
        request.user.rol in (RolUsuario.DESARROLLADOR, RolUsuario.COORDINADOR)
        or request.user.pk == ticket.solicitante_id
    )

    permitido = False
    if (
        nuevo_estado == EstadoTicket.CERRADO
        and ticket.estado != EstadoTicket.CERRADO
        and es_actor_gestion
    ):
        # Cerrar desde cualquier estado abierto (EN_PROCESO, PENDIENTE, REABIERTO)
        permitido = True
    elif (
        nuevo_estado == EstadoTicket.REABIERTO
        and ticket.estado == EstadoTicket.CERRADO
        and es_actor_gestion
    ):
        permitido = True

    if not permitido:
        raise PermissionDenied("Transición de estado no permitida.")

    if nuevo_estado == EstadoTicket.CERRADO:
        ticket.cerrado_en = timezone.now()
        ticket.estado_previo = None
    elif nuevo_estado == EstadoTicket.REABIERTO:
        ticket.cerrado_en = None
        # Si reabre un desarrollador que no es colaborador, se suma como colaborador activo.
        if (
            request.user.rol == RolUsuario.DESARROLLADOR
            and not ticket.ticketdesarrollador_set.filter(
                usuario=request.user, activo=True
            ).exists()
        ):
            td, _ = TicketDesarrollador.objects.get_or_create(
                ticket=ticket, usuario=request.user
            )
            if not td.activo:
                td.activo = True
                td.save(update_fields=["activo"])

    ticket.estado = nuevo_estado
    ticket.save(update_fields=["estado", "cerrado_en", "estado_previo"])
    return redirect("ticket_detail", pk=pk)


@login_required
def agregar_comentario(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    if not _puede_comentar(request.user, ticket):
        raise PermissionDenied("No podés comentar en este ticket.")
    form = ComentarioForm(request.POST)
    if form.is_valid():
        comentario = form.save(commit=False)
        comentario.ticket = ticket
        comentario.usuario = request.user
        comentario.save()
        _guardar_adjuntos(
            request.FILES.getlist("archivos"),
            comentario=comentario,
            usuario=request.user,
        )
    return redirect("ticket_detail", pk=pk)


@login_required
def editar_comentario(request, pk):
    """Edita un comentario (solo su autor, y debe seguir participando activamente:
    dueño o colaborador activo; un dev liberado ya no puede editar sus comentarios)."""
    comentario = get_object_or_404(Comentario, pk=pk)
    if comentario.usuario != request.user:
        raise PermissionDenied("Solo el autor puede editar su comentario.")
    if not _es_participante_activo(request.user, comentario.ticket):
        raise PermissionDenied("Ya no participás activamente en este ticket.")
    if request.method == "POST":
        form = ComentarioForm(request.POST, instance=comentario)
        if form.is_valid():
            comentario.modificado_en = timezone.now()
            form.save()
            # Agregar adjuntos nuevos
            _guardar_adjuntos(
                request.FILES.getlist("archivos"),
                comentario=comentario,
                usuario=request.user,
            )
            # Eliminar adjuntos marcados (borra el archivo físico + registro)
            eliminar = request.POST.get("adjuntos_eliminar", "")
            eliminar_pks = [p.strip() for p in eliminar.split(",") if p.strip().isdigit()]
            if eliminar_pks:
                a_eliminar = comentario.adjuntos.filter(pk__in=eliminar_pks)
                _eliminar_adjuntos(a_eliminar)
            messages.success(request, "Comentario actualizado.")
        return redirect("ticket_detail", pk=comentario.ticket_id)
    return redirect("ticket_detail", pk=comentario.ticket_id)


@login_required
def eliminar_comentario(request, pk):
    """Elimina un comentario lógicamente (soft delete): solo su autor y solo POST;
    debe seguir participando activamente (dueño o colaborador activo).
    El registro se conserva (eliminado_en) para el histórico; se oculta de la vista."""
    if request.method != "POST":
        raise PermissionDenied
    comentario = get_object_or_404(Comentario, pk=pk)
    if comentario.usuario != request.user:
        raise PermissionDenied("Solo el autor puede eliminar su comentario.")
    if not _es_participante_activo(request.user, comentario.ticket):
        raise PermissionDenied("Ya no participás activamente en este ticket.")
    ticket_id = comentario.ticket_id
    comentario.soft_delete()
    messages.success(request, "Comentario eliminado.")
    return redirect("ticket_detail", pk=ticket_id)


@login_required
def descargar_adjunto(request, pk):
    """Devuelve el archivo adjunto con descarga forzada (no lo visualiza en línea).
    Aplica la misma visibilidad por rol que el detalle del ticket."""
    adj = get_object_or_404(Adjunto, pk=pk)
    ticket = adj.ticket or (adj.comentario.ticket if adj.comentario else None)

    usuario = request.user
    if ticket is not None and not usuario.is_superuser:
        if usuario.rol == RolUsuario.SOLICITANTE:
            if ticket.solicitante != usuario:
                raise PermissionDenied("No podés acceder a este adjunto.")
        elif ticket.sistema_id not in _sistemas_visibles(usuario).values_list("id", flat=True):
            raise PermissionDenied("No podés acceder a este adjunto.")

    return FileResponse(
        adj.archivo.open("rb"),
        as_attachment=True,
        filename=adj.nombre_archivo,
        content_type="application/octet-stream",
    )


@login_required
def analizar_ticket(request, pk):
    """Dispara el análisis conceptual (IA) de un ticket.

    Es un endpoint híbrido:
    - Por HTTP normal (sin fetch): flash + redirect al detalle (fallback).
    - Via XMLHttpRequest (fetch desde el botón Analizar): responde JSON para
      que la UI muestre el progreso y los reintentos. Los errores transitorios
      (429/5xx) devuelven 503 para que el cliente reintente; los duros, 400.
    """
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    if not TicketDetailView._puede_actuar(request.user, ticket):
        raise PermissionDenied("No podés analizar este ticket.")

    es_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    try:
        _ejecutar_analisis(ticket.pk)
        mensaje = "Análisis conceptual actualizado."
        if es_ajax:
            # El éxito AJAX se muestra inline en verde (#analizar-msg); no setear
            # flash para no acumular un mensaje azul en el próximo GET.
            return JsonResponse({"ok": True, "message": mensaje,
                                 "redirect": reverse("ticket_detail", kwargs={"pk": ticket.pk})})
        messages.success(request, mensaje)
    except RetryableProviderError as exc:
        if es_ajax:
            mensaje = (str(exc) if request.user.rol != RolUsuario.SOLICITANTE
                       else "Servicio de IA temporalmente saturado. Intentá de nuevo más tarde.")
            return JsonResponse({"ok": False, "retryable": True, "message": mensaje}, status=503)
        mensaje = "No se pudo generar el análisis (servicio de IA temporalmente saturado). Intentá de nuevo."
        messages.error(request, mensaje)
    except Exception as exc:
        if es_ajax:
            mensaje = ("No se pudo generar el análisis. Intentá de nuevo más tarde."
                       if request.user.rol == RolUsuario.SOLICITANTE
                       else f"No se pudo generar el análisis: {exc}")
            return JsonResponse({"ok": False, "retryable": False, "message": mensaje}, status=400)
        if request.user.rol == RolUsuario.SOLICITANTE:
            messages.error(request, "No se pudo generar el análisis. Intentá de nuevo más tarde.")
        else:
            messages.error(request, f"No se pudo generar el análisis: {exc}")

    # Sólo llega acá en el fallback sin JS: los paths AJAX retornan antes.
    return redirect("ticket_detail", pk=ticket.pk)
