from django.urls import path

from . import views

urlpatterns = [
    path("tickets/", views.TicketListView.as_view(), name="ticket_list"),
    path("tickets/nuevo/", views.TicketCreateView.as_view(), name="ticket_create"),
    path("tickets/<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
    path("tickets/<int:pk>/tomar/", views.tomar_ticket, name="ticket_tomar"),
    path("tickets/<int:pk>/estado/", views.cambiar_estado_ticket, name="ticket_cambiar_estado"),
    path("tickets/<int:pk>/comentar/", views.agregar_comentario, name="ticket_comentar"),
]
