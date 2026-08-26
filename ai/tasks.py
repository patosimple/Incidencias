"""
Tarea en segundo plano (Huey) para generar los análisis de un ticket.
Se dispara al crear el ticket (o al pedir "reanalizar"), y no bloquea la
respuesta al usuario que carga el reporte.

Requiere en settings.py:
    HUEY = {
        "huey_class": "huey.PostgresHuey",
        "name": "tickets",
        "connection": {
            "database": config("POSTGRES_DB"),
            "user": config("POSTGRES_USER"),
            "password": config("POSTGRES_PASSWORD"),
            "host": config("POSTGRES_HOST"),
            "port": config("POSTGRES_PORT", cast=int),
        },
        "immediate": config("DJANGO_DEBUG", cast=bool),  # corre sync en dev, sin correr huey aparte
    }
"""

from huey.contrib.djhuey import task

from core.models import Ticket, AnalisisIA, TipoAnalisis
from .providers import get_active_provider


@task()
def generar_analisis_ticket(ticket_id: int):
    ticket = Ticket.objects.get(pk=ticket_id)
    provider = get_active_provider()

    for tipo in (TipoAnalisis.CONCEPTUAL, TipoAnalisis.TECNICO):
        resultado = provider.generar_analisis(ticket.descripcion_original, tipo)
        AnalisisIA.objects.create(
            ticket=ticket,
            tipo=tipo,
            problema=resultado.problema,
            comportamiento_esperado=resultado.comportamiento_esperado,
            comportamiento_observado=resultado.comportamiento_observado,
            pasos_reproducir=resultado.pasos_reproducir,
            datos_relevantes=resultado.datos_relevantes,
            informacion_faltante=resultado.informacion_faltante,
            modelo_ia=provider.modelo_ia,
        )
