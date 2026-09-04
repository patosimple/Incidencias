"""
Tarea en segundo plano (Huey) para generar el análisis conceptual de un ticket.

Se dispara al crear el ticket o al pedir "analizar" desde el detalle, y no
bloquea la respuesta al usuario que carga el reporte cuando Huey corre con un
worker. En la demo (Render free) se usa `immediate=True`, que ejecuta la tarea
en el mismo request (síncrono) y no requiere un worker aparte.

Requisito en settings.py (ver config/settings.py -> HUEY):
    HUEY = {
        "huey_class": "huey.PostgresHuey",
        "name": "incidencias",
        "immediate": <bool>,  # True => sincrono (demo). Mismo proceso.
        "utc": True,
        "connection": {...}  # lo arma PostgresHuey desde DATABASE_URL
    }

Ojo: PostgresHuey usa la DB de Neon como broker (no hace falta Redis), pero con
un worker hay que correr un proceso aparte; `immediate` lo evita.
"""

from huey.contrib.djhuey import task

from core.models import Ticket, AnalisisIA, TipoAnalisis
from .providers import get_active_provider


def _ejecutar_analisis(ticket_id: int):
    """Lógica pura: genera el análisis CONCEPTUAL y lo guarda en la DB.

    Separa la lógica del wrapper de Huey para que la vista pueda llamarla
    directamente (sin que @task capture las excepciones).
    """
    ticket = Ticket.objects.get(pk=ticket_id)
    provider = get_active_provider()

    resultado = provider.generar_analisis(ticket.descripcion_original, TipoAnalisis.CONCEPTUAL)

    # Borra los análisis conceptuales previos del ticket (reanalizar => reemplaza).
    AnalisisIA.objects.filter(ticket=ticket, tipo=TipoAnalisis.CONCEPTUAL).delete()

    AnalisisIA.objects.create(
        ticket=ticket,
        tipo=TipoAnalisis.CONCEPTUAL,
        problema=resultado.problema,
        comportamiento_esperado=resultado.comportamiento_esperado,
        comportamiento_observado=resultado.comportamiento_observado,
        pasos_reproducir=resultado.pasos_reproducir,
        datos_relevantes=resultado.datos_relevantes,
        informacion_faltante=resultado.informacion_faltante,
        modelo_ia=provider.modelo_ia,
    )


@task()
def generar_analisis_ticket(ticket_id: int):
    """Wrapper Huey: delega a _ejecutar_analisis. En modo immediate, la vista
    llama directamente a _ejecutar_analisis (para que las excepciones
    propaguen). Con un worker async, esta función es la que se encola."""
    _ejecutar_analisis(ticket_id)
