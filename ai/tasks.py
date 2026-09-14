"""
Tarea en segundo plano (Huey) para generar el análisis técnico de un ticket.

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
from .providers import (
    get_active_provider,
    VERSION_PROMPT,
    html_a_texto_plano,
    _leer_manual_sistema,
)


def _ejecutar_analisis(ticket_id: int, usar_manual: bool = True):
    """Lógica pura: genera el análisis TÉCNICO y lo guarda en la DB.

    Separa la lógica del wrapper de Huey para que la vista pueda llamarla
    directamente (sin que @task capture las excepciones).

    `usar_manual` permite (TEMPORAL, para testear) excluir el manual de uso del
    prompt; por defecto True (comportamiento actual).
    """
    ticket = Ticket.objects.select_related("sistema").get(pk=ticket_id)
    provider = get_active_provider()

    # La descripción se guarda como HTML (Quill). Al modelo le mandamos el
    # texto plano: sin tags/entidades, ese texto es SOLO el dato a analizar.
    texto_plano = html_a_texto_plano(ticket.descripcion_original)
    # Manual de uso del sistema (manuales_rag/<codigo>/*.txt): entra como
    # referencia documental junto a Sistema.prompt (se complementan: el manual
    # describe "cómo se usa", el prompt "qué es"). "" si no hay manual -> el
    # flujo queda idéntico al anterior (solo Sistema.prompt).
    manual_sistema = _leer_manual_sistema(ticket.sistema) if usar_manual else ""
    resultado = provider.generar_analisis(
        texto_plano,
        TipoAnalisis.TECNICO,
        titulo=ticket.titulo,
        sistema_nombre=ticket.sistema.nombre,
        prompt_sistema=ticket.sistema.prompt or "",
        manual_sistema=manual_sistema,
    )

    # Borra los análisis previos del ticket (reanalizar => reemplaza).
    AnalisisIA.objects.filter(ticket=ticket, tipo=TipoAnalisis.TECNICO).delete()

    AnalisisIA.objects.create(
        ticket=ticket,
        tipo=TipoAnalisis.TECNICO,
        problema=resultado.problema,
        comportamiento_esperado=resultado.comportamiento_esperado,
        comportamiento_observado=resultado.comportamiento_observado,
        pasos_reproducir=resultado.pasos_reproducir,
        datos_relevantes=resultado.datos_relevantes,
        informacion_faltante=resultado.informacion_faltante,
        modelo_ia=provider.modelo_ia,
        version_prompt=VERSION_PROMPT,
    )


@task()
def generar_analisis_ticket(ticket_id: int):
    """Wrapper Huey: delega a _ejecutar_analisis. En modo immediate, la vista
    llama directamente a _ejecutar_analisis (para que las excepciones
    propaguen). Con un worker async, esta función es la que se encola."""
    _ejecutar_analisis(ticket_id)
