"""
Abstracción de proveedor de IA. La idea: el resto de la app le pide un
análisis a `get_active_provider()` sin saber ni importarle si detrás hay
Groq, Gemini, OpenRouter u Ollama -- eso lo resuelve esta capa.

Antigravity: acá es donde falta completar la llamada HTTP real a cada
proveedor (la firma del método `generar_analisis` ya está definida, solo
falta la implementación concreta de cada _call_api).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import os

from core.models import ModeloIA, ConfiguracionIA


@dataclass
class AnalisisGenerado:
    problema: str
    comportamiento_esperado: str
    comportamiento_observado: str
    pasos_reproducir: str
    datos_relevantes: str
    informacion_faltante: str


# Mapeo proveedor -> variable de entorno donde vive su API key.
# Las keys NUNCA se guardan en la base (ver ModeloIA en core/models.py).
API_KEY_ENV_VARS = {
    "Groq": "GROQ_API_KEY",
    "Gemini": "GOOGLE_AI_API_KEY",
    "OpenRouter": "OPENROUTER_API_KEY",
}


class AIProvider(ABC):
    def __init__(self, modelo_ia: ModeloIA):
        self.modelo_ia = modelo_ia
        env_var = API_KEY_ENV_VARS.get(modelo_ia.proveedor)
        self.api_key = os.environ.get(env_var, "") if env_var else ""

    @abstractmethod
    def generar_analisis(self, texto_ticket: str, tipo: str) -> AnalisisGenerado:
        """
        tipo: "CONCEPTUAL" o "TECNICO" -- cambia el prompt/tono pedido,
        no el proveedor. Debe devolver los campos ya separados (pedirle
        salida estructurada al modelo, ej. JSON, y parsearla acá).
        """
        raise NotImplementedError


class GroqProvider(AIProvider):
    def generar_analisis(self, texto_ticket: str, tipo: str) -> AnalisisGenerado:
        # TODO (Antigravity): llamada real a la API de Groq (compatible con
        # el formato de OpenAI). Usar self.api_key y self.modelo_ia.modelo.
        raise NotImplementedError


class GeminiProvider(AIProvider):
    def generar_analisis(self, texto_ticket: str, tipo: str) -> AnalisisGenerado:
        # TODO (Antigravity): llamada real a Google AI Studio / Gemini API.
        raise NotImplementedError


class OpenRouterProvider(AIProvider):
    def generar_analisis(self, texto_ticket: str, tipo: str) -> AnalisisGenerado:
        # TODO (Antigravity): llamada real a OpenRouter (formato OpenAI-compatible).
        raise NotImplementedError


_PROVIDER_CLASSES = {
    "Groq": GroqProvider,
    "Gemini": GeminiProvider,
    "OpenRouter": OpenRouterProvider,
}


def get_active_provider() -> AIProvider:
    """Punto de entrada único: devuelve una instancia del proveedor que
    esté marcado como activo en ConfiguracionIA (editable desde el admin,
    sin tocar código)."""
    modelo_activo = ConfiguracionIA.activo()
    if modelo_activo is None:
        raise RuntimeError(
            "No hay un ModeloIA activo configurado. Cargar uno en el admin (ConfiguracionIA)."
        )
    provider_class = _PROVIDER_CLASSES.get(modelo_activo.proveedor)
    if provider_class is None:
        raise RuntimeError(f"No hay implementación de AIProvider para '{modelo_activo.proveedor}'.")
    return provider_class(modelo_activo)
