from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import CreateView, DetailView, ListView

from .forms import ComentarioForm, TicketForm
from .models import EstadoTicket, RolUsuario, Sistema, Ticket, TicketDesarrollador


def _sistemas_visibles(usuario):
    """Sistemas a los que el usuario tiene acceso (vía UsuarioSistema)."""
    return Sistema.objects.filter(usuariosistema__usuario=usuario)


class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "core/ticket_list.html"
    context_object_name = "tickets"
    paginate_by = 20

    def get_queryset(self):
        usuario = self.request.user
        qs = Ticket.objects.select_related("sistema", "solicitante")

        if usuario.rol == RolUsuario.SOLICITANTE:
            qs = qs.filter(solicitante=usuario)
        else:
            # Desarrollador (o Coordinador a futuro): ve tickets de sus sistemas
            qs = qs.filter(sistema__in=_sistemas_visibles(usuario))

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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        usuario = self.request.user
        if usuario.rol == RolUsuario.SOLICITANTE:
            ctx["sistemas_disponibles"] = _sistemas_visibles(usuario)
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
        # Acá, en Fase 2, se dispara generar_analisis_ticket.delay(self.object.id)
        return response

    def get_success_url(self):
        return f"/tickets/{self.object.pk}/"


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = "core/ticket_detail.html"
    context_object_name = "ticket"

    def get_queryset(self):
        # Mismo criterio de visibilidad que el listado
        usuario = self.request.user
        qs = Ticket.objects.select_related("sistema", "solicitante").prefetch_related(
            "comentarios", "adjuntos", "desarrolladores"
        )
        if usuario.rol == RolUsuario.SOLICITANTE:
            return qs.filter(solicitante=usuario)
        return qs.filter(sistema__in=_sistemas_visibles(usuario))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["comentario_form"] = ComentarioForm()
        ctx["estados_disponibles"] = EstadoTicket.choices
        return ctx


@login_required
def tomar_ticket(request, pk):
    """Un desarrollador se suma como colaborador del ticket (sin sacar a los demás)."""
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.user.rol != RolUsuario.DESARROLLADOR:
        raise PermissionDenied("Solo un desarrollador puede tomar un ticket.")
    TicketDesarrollador.objects.get_or_create(ticket=ticket, usuario=request.user)
    return redirect("ticket_detail", pk=pk)


@login_required
def cambiar_estado_ticket(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    nuevo_estado = request.POST.get("estado")
    if nuevo_estado in EstadoTicket.values:
        ticket.estado = nuevo_estado
        ticket.save(update_fields=["estado"])
    return redirect("ticket_detail", pk=pk)


@login_required
def agregar_comentario(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    form = ComentarioForm(request.POST)
    if form.is_valid():
        comentario = form.save(commit=False)
        comentario.ticket = ticket
        comentario.usuario = request.user
        comentario.save()
    return redirect("ticket_detail", pk=pk)
