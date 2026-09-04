"""
Abstracción de proveedor de IA. El resto de la app le pide un análisis a
`get_active_provider()` sin saber ni importarle si detrás hay Groq, Gemini,
OpenRouter u Ollama -- eso lo resuelve esta capa.

Todos los proveedores de nube se llaman por HTTP con el formato
OpenAI-compatible (`POST /v1/chat/completions`, header `Authorization: Bearer`).
Solo cambia el `base_url`; el modelo concreto se toma del registro `ModeloIA`
activo (editable desde el admin, sin tocar código).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import os

import requests

from core.models import ModeloIA, ConfiguracionIA

TIMEOUT = 60  # segundos: margen para el peor caso (OpenRouter free es lento)

# Códigos HTTP considerados transitorios (429/5xx) que se pueden reintentar.
# Los tiers free de NVIDIA/OpenRouter/Gemini son inestables; el cliente los
# reintenta mostrando "Reintento N" en el botón Analizar.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class RetryableProviderError(Exception):
    """Error transitorio (429/5xx/timeout) que el cliente puede reintentar."""


@dataclass
class AnalisisGenerado:
    """Salida estructurada de un análisis conceptual (resumen técnico depurado).

    `problema` es el resumen principal. El resto conserva la estructura del
    modelo `AnalisisIA` y se rellena con lo relevante depurado (o vacío).
    """
    problema: str
    comportamiento_esperado: str
    comportamiento_observado: str
    pasos_reproducir: str
    datos_relevantes: str
    informacion_faltante: str


# Mapeo proveedor -> variable de entorno donde vive su API key.
# Las keys NUNCA se guardan en la base (ver ModeloIA en core/models.py).
# Ollama no usa key (corre localmente): aparece mapeado a None adrede.
API_KEY_ENV_VARS = {
    "Groq": "GROQ_API_KEY",
    "Gemini": "GOOGLE_AI_API_KEY",
    "OpenRouter": "OPENROUTER_API_KEY",
    "NVIDIA": "NVIDIA_API_KEY",
    "Ollama": None,
}

# Base URL del endpoint OpenAI-compatible de cada proveedor.
_BASE_URLS = {
    "Groq": "https://api.groq.com/openai/v1",
    "OpenRouter": "https://openrouter.ai/api/v1",
    "Gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "NVIDIA": "https://integrate.api.nvidia.com/v1",
}


class AIProvider(ABC):
    def __init__(self, modelo_ia: ModeloIA):
        self.modelo_ia = modelo_ia
        env_var = API_KEY_ENV_VARS.get(modelo_ia.proveedor)
        self.api_key = os.environ.get(env_var, "") if env_var else ""

    @abstractmethod
    def generar_analisis(self, texto_ticket: str, tipo: str) -> AnalisisGenerado:
        """tipo: "CONCEPTUAL" (hoy solo este). Devuelve los campos ya separados,
        pidiéndole al modelo salida estructurada (JSON) y parseándola acá."""
        raise NotImplementedError

    def _prompt_conceptual(self, texto_ticket: str) -> str:
        """Prompt del análisis conceptual: resume la descripción, elimina
        información irrelevante (ejemplos, datos contables que no aportan al
        entendimiento del problema) y entrega una orientación más técnica, de
        desarrollador. Pide salida en JSON con la estructura de AnalisisIA."""
        return (
            "Eres un analista técnico senior de un equipo de IT. Se te da la "
            "descripción de un ticket/incidencia reportado por un usuario.\n\n"
            "Tarea: producir UN análisis conceptual (un único resumen) con "
            "orientación de desarrollador. Reglas:\n"
            "- Eliminá información irrelevante o que no aporta (ejemplos largos, "
            "datos contables que no ayudan a entender el problema, relleno, "
            "tono informal).\n"
            "- Redactá el contexto en lenguaje técnico conciso (como lo haría un "
            "dev al describir el bug).\n"
            "- No inventes información que no esté en la descripción.\n\n"
            "Respondé SOLO con un objeto JSON válido con estas claves "
            "(usa strings, vacíos si no aplica):\n"
            "{\n"
            '  "problema": "resumen técnico del problema, conciso",\n'
            '  "comportamiento_esperado": "qué debería pasar",\n'
            '  "comportamiento_observado": "qué pasa realmente",\n'
            '  "pasos_reproducir": "cómo reproducirlo, si se puede inferir",\n'
            '  "datos_relevantes": "datos/contexto que SÍ aportan",\n'
            '  "informacion_faltante": "qué falta para entenderlo mejor"\n'
            "}\n\n"
            f"DESCRIPCIÓN DEL TICKET:\n{texto_ticket}"
        )

    def _chat_completions(self, prompt: str) -> str:
        """POST al endpoint OpenAI-compatible del proveedor activo.
        Devuelve el texto del primer mensaje de respuesta.

        Ante un error transitorio (429/5xx/timeout) lanza `RetryableProviderError`
        para que el cliente decida reintentar (y mostrar el progreso). No reintenta
        acá: el reintento lo maneja la UI para verlo en el botón.
        """
        url = f"{_BASE_URLS[self.modelo_ia.proveedor]}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.modelo_ia.modelo,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},  # Groq/OpenRouter lo aceptan
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
            if resp.status_code in RETRYABLE_STATUS:
                raise RetryableProviderError(f"{resp.status_code} del proveedor {self.modelo_ia.proveedor}")
            resp.raise_for_status()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            raise RetryableProviderError(f"timeout/conexión con {self.modelo_ia.proveedor}") from exc

        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _analisis_desde_json(self, raw: str) -> AnalisisGenerado:
        datos = json.loads(raw)
        return AnalisisGenerado(
            problema=str(datos.get("problema", "")),
            comportamiento_esperado=str(datos.get("comportamiento_esperado", "")),
            comportamiento_observado=str(datos.get("comportamiento_observado", "")),
            pasos_reproducir=str(datos.get("pasos_reproducir", "")),
            datos_relevantes=str(datos.get("datos_relevantes", "")),
            informacion_faltante=str(datos.get("informacion_faltante", "")),
        )


class GroqProvider(AIProvider):
    def generar_analisis(self, texto_ticket: str, tipo: str) -> AnalisisGenerado:
        raw = self._chat_completions(self._prompt_conceptual(texto_ticket))
        return self._analisis_desde_json(raw)


class GeminiProvider(AIProvider):
    def generar_analisis(self, texto_ticket: str, tipo: str) -> AnalisisGenerado:
        # Gemini expone /v1beta/openai/chat/completions (OpenAI-compatible).
        if not self.api_key.startswith("Bearer"):
            pass  # la key se manda igual en el header Authorization: Bearer
        raw = self._chat_completions(self._prompt_conceptual(texto_ticket))
        return self._analisis_desde_json(raw)


class OpenRouterProvider(AIProvider):
    def generar_analisis(self, texto_ticket: str, tipo: str) -> AnalisisGenerado:
        raw = self._chat_completions(self._prompt_conceptual(texto_ticket))
        return self._analisis_desde_json(raw)


class NVIDIAProvider(AIProvider):
    def generar_analisis(self, texto_ticket: str, tipo: str) -> AnalisisGenerado:
        raw = self._chat_completions(self._prompt_conceptual(texto_ticket))
        return self._analisis_desde_json(raw)


class OllamaProvider(AIProvider):
    def __init__(self, modelo_ia: ModeloIA):
        super().__init__(modelo_ia)
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def generar_analisis(self, texto_ticket: str, tipo: str) -> AnalisisGenerado:
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.modelo_ia.modelo,
            "messages": [{"role": "user", "content": self._prompt_conceptual(texto_ticket)}],
            "stream": False,
            "format": "json",
        }
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        raw = data["message"]["content"]
        return self._analisis_desde_json(raw)


_PROVIDER_CLASSES = {
    "Groq": GroqProvider,
    "Gemini": GeminiProvider,
    "OpenRouter": OpenRouterProvider,
    "NVIDIA": NVIDIAProvider,
    "Ollama": OllamaProvider,
}


def get_active_provider() -> AIProvider:
    """Punto de entrada único: devuelve una instancia del proveedor que esté
    marcado como activo en ConfiguracionIA (editable desde el admin)."""
    modelo_activo = ConfiguracionIA.activo()
    if modelo_activo is None:
        raise RuntimeError(
            "No hay un ModeloIA activo configurado. Cargar uno en el admin (ConfiguracionIA)."
        )
    provider_class = _PROVIDER_CLASSES.get(modelo_activo.proveedor)
    if provider_class is None:
        raise RuntimeError(f"No hay implementación de AIProvider para '{modelo_activo.proveedor}'.")
    return provider_class(modelo_activo)
