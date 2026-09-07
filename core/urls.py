from django.urls import path

from . import views

urlpatterns = [
    path("tickets/", views.TicketListView.as_view(), name="ticket_list"),
    path("tickets/nuevo/", views.TicketCreateView.as_view(), name="ticket_create"),
    path("tickets/<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
    path("tickets/<int:pk>/analizar/", views.analizar_ticket, name="ticket_analizar"),
    path("tickets/<int:pk>/tomar/", views.tomar_ticket, name="ticket_tomar"),
    path("tickets/<int:pk>/liberar/", views.liberar_ticket, name="ticket_liberar"),
    path("tickets/<int:pk>/editar/", views.editar_ticket, name="ticket_editar"),
    path("tickets/<int:pk>/eliminar/", views.eliminar_ticket, name="ticket_eliminar"),
    path("tickets/<int:pk>/estado/", views.cambiar_estado_ticket, name="ticket_cambiar_estado"),
    path("tickets/<int:pk>/comentar/", views.agregar_comentario, name="ticket_comentar"),
    path("comentarios/<int:pk>/editar/", views.editar_comentario, name="comentario_editar"),
    path("comentarios/<int:pk>/eliminar/", views.eliminar_comentario, name="comentario_eliminar"),
    path("adjuntos/<int:pk>/descargar/", views.descargar_adjunto, name="adjunto_descargar"),
    path("cambiar-password/", views.CambiarPasswordView.as_view(), name="cambiar_password"),
]
