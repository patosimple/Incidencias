import os
import time
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.db.models import F, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Greatest
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView

from .forms import CambioPasswordForm, ComentarioForm, TicketEditarForm, TicketForm
from ai.tasks import _ejecutar_analisis
from ai.providers import RetryableProviderError
from .models import (
    Adjunto,
    AnalisisIA,
    Comentario,
    EstadoTicket,
    LecturaTicket,
    RolUsuario,
    Sistema,
    Ticket,
    TicketDesarrollador,
    TipoAdjunto,
    TipoAnalisis,
)


def _tipo_por_nombre(nombre):
    ext = os.path.splitext(nombre)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".heic", ".heif"):
        return TipoAdjunto.IMAGEN
    return TipoAdjunto.DOCUMENTO


# Whitelist de extensiones de adjunto: todo lo que NO esté acá se rechaza.
# Excluidos a propósito: ejecutables/scripts (.exe .msi .bat .cmd .ps1 .vbs .jar
# .sh ...), .svg (puede embeder scripts), archivos de macro de Office
# (.xlsm .docm .pptm — corren VBA) y formatos de documento activo (.html .xml).
EXTENSIONES_ADJUNTO_PERMITIDAS = {
    # imágenes / capturas
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic", ".heif",
    # documentos ofimáticos + PDF + texto
    ".pdf", ".doc", ".docx", ".rtf", ".xls", ".xlsx", ".csv",
    ".ppt", ".pptx", ".txt",
    # suites ofimáticas similares (LibreOffice/OpenOffice)
    ".odt", ".ods", ".odp",
    # comprimidos (el usuario los extrae localmente)
    ".zip", ".rar", ".7z",
}
_MSG_EXTENSIONES_PERMITIDAS = "formatos: imágenes, PDF, documentos de Office, texto y comprimidos (zip/rar/7z)"


MAX_ADJUNTO_BYTES = 10 * 1024 * 1024  # 10 MB


def _guardar_adjuntos(archivos, *, ticket=None, comentario=None, usuario):
    """Guarda los archivos subidos, asignando el ticket o comentario correspondiente.
    `archivos` es una lista de UploadedFile (campo múltiple 'archivos').
    Lanza ValueError si algún archivo supera MAX_ADJUNTO_BYTES o su extensión no está permitida."""
    for archivo in archivos:
        if archivo.size > MAX_ADJUNTO_BYTES:
            mb = round(archivo.size / (1024 * 1024), 1)
            raise ValueError(
                f'El archivo "{archivo.name}" pesa {mb} MB y el máximo permitido es 10 MB.'
            )
        ext = os.path.splitext(archivo.name)[1].lower()
        if ext not in EXTENSIONES_ADJUNTO_PERMITIDAS:
            raise ValueError(
                f'El archivo "{archivo.name}" no tiene un tipo permitido. '
                f'Permitidos: {_MSG_EXTENSIONES_PERMITIDAS}.'
            )
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


def _contexto_detalle(request, ticket, comentario_form=None, toast=None, toast_tipo=None):
    """Contexto completo del detalle, compartido entre la vista GET y los
    re-renders de HTMX. Al mutar el ticket (tomar/liberar/estado/comentarios)
    los flags se recalculan acá con el estado ya actualizado.
    `toast` (opcional) es un texto de confirmación que se muestra como notificación
    flotante (no en flujo, para no empujar el layout) cuando la acción ya se
    confirma visualmente con el propio swap HTMX."""
    ctx = {
        "ticket": ticket,
        "comentario_form": comentario_form if comentario_form is not None else ComentarioForm(),
        "puede_actuar": TicketDetailView._puede_actuar(request.user, ticket),
        "puede_comentar": _puede_comentar(request.user, ticket),
        "puede_liberar": ticket.ticketdesarrollador_set.filter(
            usuario=request.user, activo=True
        ).exists(),
        "puede_cerrar": TicketDetailView._puede_cerrar(request.user, ticket),
        "puede_reabrir": TicketDetailView._puede_reabrir(request.user, ticket),
        "puede_gestionar_comentarios": (
            _es_participante_activo(request.user, ticket)
            and ticket.estado != EstadoTicket.CERRADO
        ),
        "puede_gestionar_ticket": (
            request.user.pk == ticket.solicitante_id
            and ticket.estado != EstadoTicket.CERRADO
        ),
        "tomado": ticket.ticketdesarrollador_set.filter(activo=True).exists(),
        "tomado_mi": ticket.ticketdesarrollador_set.filter(
            usuario=request.user, activo=True
        ).exists(),
        # Análisis IA: el más reciente de tipo TÉCNICO (único hoy). Por ahora
        # NO disponible para solicitantes (dev/coord lo ven).
        "puede_analizar": (
            request.user.rol in (RolUsuario.DESARROLLADOR, RolUsuario.COORDINADOR)
            and ticket.estado != EstadoTicket.CERRADO
        ),
        "puede_ver_analisis": request.user.rol in (
            RolUsuario.DESARROLLADOR,
            RolUsuario.COORDINADOR,
        ),
        "toast": toast,
        "toast_tipo": toast_tipo,
    }
    analisis = list(ticket.analisis.filter(tipo=TipoAnalisis.TECNICO))
    ctx["analisis_conceptual"] = analisis[0] if analisis else None

    # Marca el ticket como leído por el usuario actual (indicador de novedades
    # del listado). Se upserta en cada apertura del detalle (GET y swaps HTMX),
    # para cada rol, sin importar quién tomó el ticket.
    LecturaTicket.objects.update_or_create(
        usuario=request.user,
        ticket=ticket,
        defaults={"ultima_lectura_en": timezone.now()},
    )
    return ctx


def _render_ticket_pagina(request, ticket, comentario_form=None, toast=None, toast_tipo=None):
    """Renderiza el partial del detalle completo (#ticket-pagina), que HTMX
    usa para swappear la página sin recargar tras una acción."""
    return render(
        request,
        "core/partials/ticket_pagina.html",
        _contexto_detalle(request, ticket, comentario_form, toast, toast_tipo),
    )


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

            # Filtro "mostrar=nuevos": solo tickets con actividad nueva para el
            # usuario logueado (nunca leídos o con creado/cerrado/editado/último
            # comentario visible posterior a su última lectura).
            mostrar = self.request.GET.get("mostrar")
            if mostrar == "nuevos":
                ultima_lectura = Subquery(
                    LecturaTicket.objects.filter(
                        usuario=usuario, ticket=OuterRef("pk")
                    ).values("ultima_lectura_en")[:1]
                )
                ultimo_comentario = Subquery(
                    Comentario.objects.filter(ticket=OuterRef("pk"))
                    .annotate(_efectivo=Greatest("creado_en", "modificado_en"))
                    .order_by("-_efectivo")
                    .values("_efectivo")[:1]
                )
                qs = qs.annotate(
                    _ultima_lectura=ultima_lectura,
                    _ultimo_comentario=ultimo_comentario,
                ).filter(
                    Q(_ultima_lectura__isnull=True)
                    | Q(creado_en__gt=F("_ultima_lectura"))
                    | Q(cerrado_en__gt=F("_ultima_lectura"))
                    | Q(reabierto_en__gt=F("_ultima_lectura"))
                    | Q(modificado_en__gt=F("_ultima_lectura"))
                    | Q(_ultimo_comentario__gt=F("_ultima_lectura"))
                )

        # Prefetch de colaboradores activos (read-only) para pintar el badge
        # de ticket reabierto "tomado" (verde) vs "sin tomar" (rojo).
        # También se prefetchan los comentarios visibles (solo sus fechas) para
        # computar en Python la "última actividad" del indicador de novedades.
        qs = qs.prefetch_related(
            Prefetch(
                "ticketdesarrollador_set",
                queryset=TicketDesarrollador.objects.filter(activo=True),
                to_attr="colabs_activos",
            ),
            Prefetch(
                "comentarios",
                queryset=Comentario.objects.only(
                    "ticket_id", "creado_en", "modificado_en"
                ),
                to_attr="comentarios_recientes",
            ),
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
        # Toggle de novedades: círculo del header de la lista. El estado visual
        # (mitad lleno = viendo todos; lleno = solo novedades) y la URL a la que
        # lleva el clic (en modo server) se computan acá en una sola vez.
        mostrando_nuevos = self.request.GET.get("mostrar") == "nuevos"
        ctx["es_mostrando_nuevos"] = mostrando_nuevos
        params = {k: v for k, v in self.request.GET.items() if k != "mostrar"}
        if not mostrando_nuevos:
            params["mostrar"] = "nuevos"
        base = reverse("ticket_list")
        query = urlencode(params)
        ctx["url_lista_novedades"] = f"{base}?{query}" if query else base
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
        # Indicador de novedades por-usuario: un ticket "tiene novedad" si nunca
        # se leyó o si hubo actividad (creado/cerrado/editado o el último
        # comentario visible) posterior a la última lectura. Se computa con un
        # mapa de lecturas del usuario (1 query) + los comentarios prefetched.
        lecturas = dict(
            LecturaTicket.objects.filter(usuario=usuario).values_list(
                "ticket_id", "ultima_lectura_en"
            )
        )
        for t in ctx["tickets"]:
            lectura = lecturas.get(t.pk)
            if lectura is None:
                t.novedad = True
                continue
            fechas = [
                f
                for f in (
                    t.creado_en,
                    t.cerrado_en,
                    t.reabierto_en,
                    t.modificado_en,
                )
                if f
            ]
            fechas.extend(
                (c.modificado_en or c.creado_en)
                for c in getattr(t, "comentarios_recientes", [])
            )
            t.novedad = bool(fechas) and max(fechas) > lectura
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
        try:
            _guardar_adjuntos(
                self.request.FILES.getlist("archivos"),
                ticket=self.object,
                usuario=self.request.user,
            )
        except ValueError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
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
        ctx.update(_contexto_detalle(self.request, self.object))
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
    if request.headers.get("HX-Request"):
        return _render_ticket_pagina(request, ticket)
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
    if request.headers.get("HX-Request"):
        return _render_ticket_pagina(request, ticket)
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
        ticket.reabierto_en = None
        ticket.estado_previo = None
    elif nuevo_estado == EstadoTicket.REABIERTO:
        ticket.cerrado_en = None
        ticket.reabierto_en = timezone.now()
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
    ticket.save(
        update_fields=["estado", "cerrado_en", "reabierto_en", "estado_previo"]
    )
    if request.headers.get("HX-Request"):
        return _render_ticket_pagina(request, ticket)
    return redirect("ticket_detail", pk=pk)


@login_required
def editar_ticket(request, pk):
    """Edita título y descripción de un ticket (solo el solicitante dueño y
    solo si el ticket no está cerrado; el sistema no se puede cambiar)."""
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.user.pk != ticket.solicitante_id:
        raise PermissionDenied("Solo el solicitante (dueño) puede editar el ticket.")
    if ticket.estado == EstadoTicket.CERRADO:
        raise PermissionDenied("El ticket está cerrado; no se puede editar.")
    if request.method == "POST":
        form = TicketEditarForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket.modificado_en = timezone.now()
            form.save()
            try:
                _guardar_adjuntos(
                    request.FILES.getlist("archivos"),
                    ticket=ticket,
                    usuario=request.user,
                )
            except ValueError as e:
                if request.headers.get("HX-Request"):
                    return _render_ticket_pagina(request, ticket, toast=str(e), toast_tipo="warning")
                messages.warning(request, str(e))
            eliminar_pks = [
                p.strip()
                for p in request.POST.get("adjuntos_eliminar", "").split(",")
                if p.strip().isdigit()
            ]
            if eliminar_pks:
                _eliminar_adjuntos(ticket.adjuntos.filter(pk__in=eliminar_pks))
            if request.headers.get("HX-Request"):
                return _render_ticket_pagina(request, ticket, toast="Ticket actualizado.")
            messages.success(request, "Ticket actualizado.")
        if request.headers.get("HX-Request"):
            return _render_ticket_pagina(request, ticket)
        return redirect("ticket_detail", pk=ticket.pk)
    return redirect("ticket_detail", pk=ticket.pk)


@login_required
def eliminar_ticket(request, pk):
    """Elimina un ticket (solo el solicitante dueño y solo POST). Soft delete:
    se conserva el registro y sus dependencias (histórico) pero se oculta de la
    vista (manager por defecto). Como el detalle deja de existir, se navega al
    listado: en HTMX se responde con header HX-Redirect (el cliente cambia de
    página); en fallback sin JS, redirect normal."""
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.user.pk != ticket.solicitante_id:
        raise PermissionDenied("Solo el solicitante (dueño) puede eliminar el ticket.")
    if ticket.estado == EstadoTicket.CERRADO:
        raise PermissionDenied("El ticket está cerrado; no se puede eliminar.")
    ticket.soft_delete()
    if request.headers.get("HX-Request"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = reverse("ticket_list")
        return response
    messages.success(request, "Ticket eliminado.")
    return redirect("ticket_list")


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
        try:
            _guardar_adjuntos(
                request.FILES.getlist("archivos"),
                comentario=comentario,
                usuario=request.user,
            )
        except ValueError as e:
            if request.headers.get("HX-Request"):
                return _render_ticket_pagina(request, ticket, toast=str(e), toast_tipo="warning")
            messages.warning(request, str(e))
        if request.headers.get("HX-Request"):
            return _render_ticket_pagina(request, ticket)
        return redirect("ticket_detail", pk=pk)
    # Form inválido: en HTMX devolver la página con los errores del form;
    # como fallback sin JS, redirigir (comportamiento histórico).
    if request.headers.get("HX-Request"):
        return _render_ticket_pagina(request, ticket, comentario_form=form)
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
    if comentario.ticket.estado == EstadoTicket.CERRADO:
        raise PermissionDenied("El ticket está cerrado; no se pueden editar comentarios.")
    if request.method == "POST":
        form = ComentarioForm(request.POST, instance=comentario)
        if form.is_valid():
            comentario.modificado_en = timezone.now()
            form.save()
            # Agregar adjuntos nuevos
            try:
                _guardar_adjuntos(
                    request.FILES.getlist("archivos"),
                    comentario=comentario,
                    usuario=request.user,
                )
            except ValueError as e:
                if request.headers.get("HX-Request"):
                    return _render_ticket_pagina(request, comentario.ticket, toast=str(e), toast_tipo="warning")
                messages.warning(request, str(e))
            # Eliminar adjuntos marcados (borra el archivo físico + registro)
            eliminar = request.POST.get("adjuntos_eliminar", "")
            eliminar_pks = [p.strip() for p in eliminar.split(",") if p.strip().isdigit()]
            if eliminar_pks:
                a_eliminar = comentario.adjuntos.filter(pk__in=eliminar_pks)
                _eliminar_adjuntos(a_eliminar)
            if request.headers.get("HX-Request"):
                return _render_ticket_pagina(
                    request, comentario.ticket, toast="Comentario actualizado."
                )
            messages.success(request, "Comentario actualizado.")
        if request.headers.get("HX-Request"):
            return _render_ticket_pagina(request, comentario.ticket)
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
    if comentario.ticket.estado == EstadoTicket.CERRADO:
        raise PermissionDenied("El ticket está cerrado; no se puede eliminar el comentario.")
    ticket_id = comentario.ticket_id
    _eliminar_adjuntos(comentario.adjuntos.all())
    comentario.soft_delete()
    if request.headers.get("HX-Request"):
        return _render_ticket_pagina(
            request, comentario.ticket, toast="Comentario eliminado.", toast_tipo="error"
        )
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
    """Dispara el análisis IA (técnico) de un ticket.

    Es un endpoint híbrido:
    - Por HTTP normal (sin fetch): flash + redirect al detalle (fallback).
    - Via XMLHttpRequest (fetch desde el botón Analizar): responde JSON para
      que la UI muestre el progreso y los reintentos. Los errores transitorios
      (429/5xx) devuelven 503 para que el cliente reintente; los duros, 400.
    """
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    # Por ahora el análisis IA es SOLO para dev/coord (no para solicitantes),
    # consistente con la sección oculta en el detalle. Consiste en la misma
    # condición de `puede_ver_analisis` del context del detalle.
    if request.user.rol not in (RolUsuario.DESARROLLADOR, RolUsuario.COORDINADOR):
        raise PermissionDenied("El análisis IA no está disponible para tu rol.")
    if ticket.estado == EstadoTicket.CERRADO:
        raise PermissionDenied("El ticket está cerrado; no se puede volver a analizar.")

    es_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # TEMPORAL (para testear): checkbox "manual" del form-analizar. Desmarcado =>
    # el análisis NO incluye el manual de uso (solo Sistema.prompt). El form
    # manda "on" (checked) u "off" (hidden previo al checkbox); si no llega el
    # campo (cliente no-HTML), default True = comportamiento previo.
    usar_manual = request.POST.get("manual", "on") == "on"

    inicio = time.monotonic()
    try:
        _ejecutar_analisis(ticket.pk, usar_manual=usar_manual)
        # En AJAX el tiempo total lo ajusta el cliente en el HTML (incluye los
        # reintentos y el render); acá solo el detalle para el fallback sin JS.
        mensaje = "Análisis actualizado."
        if not es_ajax:
            mensaje += f" ({time.monotonic() - inicio:.1f}s)"
        if es_ajax:
            # Éxito AJAX: se muestra verde inline (#analizar-msg) y se devuelve el
            # HTML del cuerpo de la tarjeta para refrescarla sin recargar la página.
            # No se setea flash para no acumular un mensaje azul en el próximo GET.
            analisis = ticket.analisis.filter(tipo=TipoAnalisis.TECNICO).first()
            cuerpo = render_to_string(
                "core/partials/analisis_cuerpo.html",
                {
                    "analisis_conceptual": analisis,
                    "puede_analizar": (
                        request.user.rol in (RolUsuario.DESARROLLADOR, RolUsuario.COORDINADOR)
                        and ticket.estado != EstadoTicket.CERRADO
                    ),
                },
            )
            return JsonResponse({
                "ok": True,
                "message": mensaje,
                "cuerpo": cuerpo,
                "redirect": reverse("ticket_detail", kwargs={"pk": ticket.pk}),
            })
        messages.success(request, mensaje)
    except RetryableProviderError as exc:
        if es_ajax:
            mensaje = (f"ERROR al analizar: {exc}"
                       if request.user.rol != RolUsuario.SOLICITANTE
                       else "Servicio de IA temporalmente saturado. Intentá de nuevo más tarde.")
            return JsonResponse({"ok": False, "retryable": True, "message": mensaje}, status=503)
        detalle = f" ({time.monotonic() - inicio:.1f}s)"
        mensaje = f"ERROR al analizar: No se pudo generar el análisis (servicio de IA temporalmente saturado). Intentá de nuevo.{detalle}"
        messages.error(request, mensaje)
    except Exception as exc:
        if es_ajax:
            mensaje = ("No se pudo generar el análisis. Intentá de nuevo más tarde."
                       if request.user.rol == RolUsuario.SOLICITANTE
                       else f"ERROR al analizar: {exc}")
            return JsonResponse({"ok": False, "retryable": False, "message": mensaje}, status=400)
        if request.user.rol == RolUsuario.SOLICITANTE:
            messages.error(request, "No se pudo generar el análisis. Intentá de nuevo más tarde.")
        else:
            mensaje = f"ERROR al analizar: {exc}" + f" ({time.monotonic() - inicio:.1f}s)"
            messages.error(request, mensaje)

    # Sólo llega acá en el fallback sin JS: los paths AJAX retornan antes.
    return redirect("ticket_detail", pk=ticket.pk)
