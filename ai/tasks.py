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

import logging

from core.models import Ticket, AnalisisIA, TipoAnalisis
from .providers import (
    get_active_provider,
    VERSION_PROMPT,
    html_a_texto_plano,
    _leer_manual_sistema,
    _leer_manual_resumido,
    _es_contexto_demasiado_grande,
    ProviderError,
    OllamaProvider,
)

logger = logging.getLogger(__name__)


def _ejecutar_analisis(ticket_id: int, usar_manual: bool = True):
    """Lógica pura: genera el análisis TÉCNICO y lo guarda en la DB.

    Separa la lógica del wrapper de Huey para que la vista pueda llamarla
    directamente (sin que @task capture las excepciones).

    `usar_manual` permite (TEMPORAL, para testear) excluir el manual de uso del
    prompt; por defecto True (comportamiento actual).

    **Escalera de degradación silenciosa** (ante 413 / context_length_exceeded):
    1. Intento con manual completo
    2. Intento con manual resumido (si existe y difiere del completo)
    3. Intento sin manual
    Si los 3 fallan con el mismo error de contexto → ProviderError (error duro,
    el cliente muestra etiqueta roja sin reintentos). Si un intento intermedio
    falla con un error NO de contexto (503, timeout), se propaga como
    RetryableProviderError y el cliente reintenta normalmente.
    """
    ticket = Ticket.objects.select_related("sistema").get(pk=ticket_id)
    provider = get_active_provider()

    # Ollama local: SIEMPRE sin manual (solo Sistema.prompt). Los manuales (completo
    # y resumido) pueden no caber en el contexto del modelo local y degradan la
    # experiencia; la escalera silenciosa queda reservada para los providers cloud.
    if isinstance(provider, OllamaProvider):
        usar_manual = False

    # La descripción se guarda como HTML (Quill). Al modelo le mandamos el
    # texto plano: sin tags/entidades, ese texto es SOLO el dato a analizar.
    texto_plano = html_a_texto_plano(ticket.descripcion_original)

    # --- Construir la escalera de manuales ---
    manual_completo = _leer_manual_sistema(ticket.sistema) if usar_manual else ""
    manual_resumido = _leer_manual_resumido(ticket.sistema) if usar_manual else ""

    nivel_manual = []  # cada tupla: (manual_para_prompt, etiqueta_para_log)
    if manual_completo:
        nivel_manual.append((manual_completo, "completo"))
    if manual_resumido and manual_resumido != manual_completo:
        nivel_manual.append((manual_resumido, "resumido"))
    nivel_manual.append(("", "vacío"))  # siempre terminar sin manual

    resultado = None
    for manual, etiqueta in nivel_manual:
        try:
            logger.info(
                "Análisis ticket %s: intento con manual=%s (%d caracteres)",
                ticket_id, etiqueta, len(manual),
            )
            resultado = provider.generar_analisis(
                texto_plano,
                TipoAnalisis.TECNICO,
                titulo=ticket.titulo,
                sistema_nombre=ticket.sistema.nombre,
                prompt_sistema=ticket.sistema.prompt or "",
                manual_sistema=manual,
            )
            if etiqueta != "completo" and len(nivel_manual) > 1:
                # Éxito recién después de degradar: clave para que el usuario vea
                # el intento silencioso en la consola sin cambiar la UI.
                logger.warning(
                    "Análisis ticket %s: OK SOLO tras degradar a manual=%s (%d caracteres)",
                    ticket_id, etiqueta, len(manual),
                )
            break  # éxito
        except Exception as exc:
            if _es_contexto_demasiado_grande(exc):
                logger.warning(
                    "Análisis ticket %s: error de contexto (%s) con manual=%s — "
                    "degradando silenciosamente al siguiente nivel",
                    ticket_id, exc, etiqueta,
                )
                continue  # degradar silenciosamente al siguiente nivel
            raise  # error no relacionado con contexto: propagar tal cual

    if resultado is None:
        # Todos los niveles agotaron con 413 / context_length_exceeded
        logger.error("Análisis ticket %s: agotó los %d niveles de la escalera de contexto", ticket_id, len(nivel_manual))
        raise ProviderError(
            "El prompt es demasiado grande para el modelo activo "
            f"(incluso sin manual de uso del sistema '{ticket.sistema.nombre}'). "
            "Probá con un modelo de mayor contexto o reducí la descripción del ticket."
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
