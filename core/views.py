import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView

from .forms import CambioPasswordForm, ComentarioForm, TicketForm
from .models import (
    Adjunto,
    EstadoTicket,
    RolUsuario,
    Sistema,
    Ticket,
    TicketDesarrollador,
    TipoAdjunto,
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


def _puede_comentar(usuario, ticket):
    """Solo el creador del ticket y quienes lo tomaron pueden comentar, y solo
    si el ticket no está cerrado."""
    if ticket.estado == EstadoTicket.CERRADO:
        return False
    if usuario.is_superuser:
        return True
    if ticket.solicitante_id == usuario.pk:
        return True
    return ticket.desarrolladores.filter(pk=usuario.pk).exists()


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
        qs = Ticket.objects.select_related("sistema", "solicitante")

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
            "comentarios", "adjuntos", "desarrolladores"
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
        return ctx

    @staticmethod
    def _puede_actuar(usuario, ticket):
        """El usuario ve la tarjeta de acciones si tiene al menos un botón disponible
        para el estado actual del ticket."""
        if ticket.estado == EstadoTicket.CERRADO:
            return True  # cualquiera puede reabrir
        es_dev_coor = usuario.rol in (RolUsuario.DESARROLLADOR, RolUsuario.COORDINADOR)
        if ticket.estado == EstadoTicket.EN_PROCESO:
            return es_dev_coor
        if ticket.estado in (EstadoTicket.PENDIENTE, EstadoTicket.REABIERTO):
            return usuario.rol == RolUsuario.DESARROLLADOR
        return False


@login_required
def tomar_ticket(request, pk):
    """Un desarrollador se suma como colaborador del ticket (sin sacar a los demás).
    Al tomar un ticket PENDIENTE o REABIERTO, este pasa automáticamente a EN_PROCESO."""
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.user.rol != RolUsuario.DESARROLLADOR:
        raise PermissionDenied("Solo un desarrollador puede tomar un ticket.")
    TicketDesarrollador.objects.get_or_create(ticket=ticket, usuario=request.user)
    if ticket.estado in (EstadoTicket.PENDIENTE, EstadoTicket.REABIERTO):
        ticket.estado = EstadoTicket.EN_PROCESO
        ticket.save(update_fields=["estado"])
    return redirect("ticket_detail", pk=pk)


@login_required
def cambiar_estado_ticket(request, pk):
    """Cambio de estado por transicion, acotado por rol (sin select genérico).
    - EN_PROCESO -> CERRADO / PENDIENTE: solo Desarrollador/Coordinador.
    - CERRADO    -> REABIERTO: cualquier usuario autenticado."""
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    nuevo_estado = request.POST.get("estado")
    es_dev_coor = request.user.rol in (RolUsuario.DESARROLLADOR, RolUsuario.COORDINADOR)

    permitido = False
    if (
        ticket.estado == EstadoTicket.EN_PROCESO
        and nuevo_estado in (EstadoTicket.CERRADO, EstadoTicket.PENDIENTE)
        and es_dev_coor
    ):
        permitido = True
    elif (
        ticket.estado == EstadoTicket.CERRADO
        and nuevo_estado == EstadoTicket.REABIERTO
    ):
        permitido = True

    if permitido:
        ticket.estado = nuevo_estado
        if nuevo_estado == EstadoTicket.CERRADO:
            ticket.cerrado_en = timezone.now()
        else:
            ticket.cerrado_en = None
        ticket.save(update_fields=["estado", "cerrado_en"])
    else:
        raise PermissionDenied("Transición de estado no permitida.")
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
