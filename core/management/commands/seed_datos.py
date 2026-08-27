"""
Carga datos base para poder trabajar sin tener que cargarlos a mano desde
el admin cada vez que se resetea la base.

Uso: python manage.py seed_datos
"""

from django.core.management.base import BaseCommand

from core.models import Sistema, ModeloIA, ConfiguracionIA


class Command(BaseCommand):
    help = "Carga los datos iniciales del sistema (sistemas y catálogo de modelos de IA)."

    def handle(self, *args, **options):
        self._seed_sistemas()
        self._seed_modelos_ia()
        self.stdout.write(self.style.SUCCESS("Seed completo."))

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
        # Catálogo de los 3 proveedores gratuitos evaluados (Fase 2).
        # Ajustar el string de "modelo" al que efectivamente se use de cada proveedor.
        modelos = [
            {"proveedor": "Groq", "modelo": "llama-3.3-70b-versatile"},
            {"proveedor": "Gemini", "modelo": "gemini-2.0-flash"},
            {"proveedor": "OpenRouter", "modelo": "meta-llama/llama-3.3-70b-instruct:free"},
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
