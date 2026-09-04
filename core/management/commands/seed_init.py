"""
Carga los datos base: sistemas y catalogo de modelos de IA.

Uso: python manage.py seed_init
"""

from django.core.management.base import BaseCommand

from core.models import Sistema, ModeloIA, ConfiguracionIA


class Command(BaseCommand):
    help = "Carga los datos iniciales del sistema (sistemas y catálogo de modelos de IA)."

    def handle(self, *args, **options):
        self._seed_sistemas()
        self._seed_modelos_ia()
        self.stdout.write(self.style.SUCCESS("Seed init completo."))

    def _seed_sistemas(self):
        sistemas = [
            {"codigo": "BALANCES", "nombre": "Balances"},
            {"codigo": "FINANCIAMIENTO", "nombre": "Financiamiento"},
        ]
        for datos in sistemas:
            sistema, creado = Sistema.objects.get_or_create(
                codigo=datos["codigo"], defaults={"nombre": datos["nombre"]}
            )
            estado = "creado" if creado else "ya existía"
            self.stdout.write(f"  Sistema {sistema.codigo}: {estado}")

    def _seed_modelos_ia(self):
        # Catálogo de los proveedores elegibles (Fase 2). El primero de la lista
        # queda como activo si todavía no hay ConfiguracionIA.
        # Ajustar el string de "modelo" al que efectivamente se use de cada proveedor.
        # Ollama es local (sin API key): solo funciona en desarrollo, no en Render.
        modelos = [
            {"proveedor": "Groq", "modelo": "qwen/qwen3.8-27b"},
            {"proveedor": "Gemini", "modelo": "gemini-2.0-flash"},
            {"proveedor": "OpenRouter", "modelo": "meta-llama/llama-3.3-70b-instruct:free"},
            {"proveedor": "Ollama", "modelo": "gemma2:2b"},
        ]
        primero = None
        for datos in modelos:
            modelo_ia, creado = ModeloIA.objects.get_or_create(
                proveedor=datos["proveedor"], modelo=datos["modelo"]
            )
            if primero is None:
                primero = modelo_ia
            estado = "creado" if creado else "ya existía"
            self.stdout.write(f"  ModeloIA {modelo_ia}: {estado}")

        # Deja activo el primero de la lista si todavía no hay configuración.
        if primero and not ConfiguracionIA.objects.exists():
            ConfiguracionIA.objects.create(modelo_activo=primero)
            self.stdout.write(f"  ConfiguracionIA: activado {primero}")
