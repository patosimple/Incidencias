"""
Carga los datos base: sistemas y catalogo de modelos de IA.

Uso: python manage.py seed_init
"""

from django.core.management.base import BaseCommand

from core.models import Sistema, ModeloIA, ConfiguracionIA, AnalisisIA


class Command(BaseCommand):
    help = "Carga los datos iniciales del sistema (sistemas y catálogo de modelos de IA)."

    def handle(self, *args, **options):
        self._seed_sistemas()
        self._seed_modelos_ia()
        self.stdout.write(self.style.SUCCESS("Seed init completo."))

    def _seed_sistemas(self):
        # El campo `prompt` es contexto opcional para la IA: describe qué hace
        # el sistema y qué datos conoce el usuario final. Solo se escribe si el
        # sistema es nuevo o no tiene prompt todavía (no pisa ediciones del admin).
        sistemas = [
            {
                "codigo": "BALANCES",
                "nombre": "Balances",
                "prompt": (
                    "Aplicación web de contabilidad donde los usuarios cargan y "
                    "consultan balances e informes contables. El usuario final "
                    "conoce qué pantalla/módulo usa (carga de asientos, consulta "
                    "de balances, listados), qué período o ejercicio reporta y "
                    "qué datos de entrada cargó."
                ),
            },
            {
                "codigo": "FINANCIAMIENTO",
                "nombre": "Financiamiento",
                "prompt": (
                    "Aplicación web de gestión de financiamiento político: los "
                    "usuarios cargan y consultan aportes, financiadores y "
                    "reportes de financiamiento. El usuario final conoce qué "
                    "pantalla/módulo usa (carga de aportes, consultas, informes), "
                    "a qué campaña o período corresponde y qué datos cargó."
                ),
            },
        ]
        for datos in sistemas:
            sistema, creado = Sistema.objects.get_or_create(
                codigo=datos["codigo"], defaults={"nombre": datos["nombre"]}
            )
            if creado or not sistema.prompt:
                sistema.prompt = datos["prompt"]
                sistema.save(update_fields=["prompt"])
            estado = "creado" if creado else "ya existía"
            self.stdout.write(f"  Sistema {sistema.codigo}: {estado}")

    def _seed_modelos_ia(self):
        # Catálogo de los proveedores elegibles (Fase 2). El primero de la lista
        # queda como activo si todavía no hay ConfiguracionIA.
        # Ajustar el string de "modelo" al que efectivamente se use de cada proveedor.
        # Ollama es local (sin API key): solo funciona en desarrollo, no en Render.
        #
        # formato_salida: cómo pedirle el JSON al modelo:
        #   RESPONSE_FORMAT -> response_format json_object (Groq/OpenRouter lo soportan)
        #   NATIVO          -> format: json nativo (Ollama)
        #   NINGUNO         -> sin campo de formato: se pide JSON por instrucción y se
        #                     tolera el ruido en el parsing (Gemini/NVIDIA lo ignoran)
        modelos = [
            {"proveedor": "Groq", "modelo": "qwen/qwen3.8-27b", "formato_salida": "RESPONSE_FORMAT"},
            {"proveedor": "Gemini", "modelo": "gemini-3.6-flash", "formato_salida": "NINGUNO"},
            {"proveedor": "OpenRouter", "modelo": "google/gemma-4-31b-it:free", "formato_salida": "RESPONSE_FORMAT"},
            {"proveedor": "NVIDIA", "modelo": "openai/gpt-oss-20b", "formato_salida": "NINGUNO"},
            {"proveedor": "Ollama", "modelo": "gemma2:2b", "formato_salida": "NATIVO"},
        ]
        primero = None
        deseados = set()
        config = ConfiguracionIA.objects.first()
        activo_id = config.modelo_activo_id if config else None

        def _borrable(m):
            """Un modelo socarrable si no es el activo ni tiene análisis históricos."""
            return m.pk != activo_id and not AnalisisIA.objects.filter(modelo_ia=m).exists()

        for datos in modelos:
            proveedor = datos["proveedor"]
            deseados.add(proveedor)
            candidatos = list(ModeloIA.objects.filter(proveedor=proveedor).order_by("pk"))

            # Preferir el registro que ya es el activo, si existe; si no, el primero.
            objetivo = next((m for m in candidatos if m.pk == activo_id), None)
            if objetivo is None and candidatos:
                objetivo = candidatos[0]

            if objetivo is None:
                objetivo = ModeloIA.objects.create(
                    proveedor=proveedor,
                    modelo=datos["modelo"],
                    formato_salida=datos["formato_salida"],
                )
                self.stdout.write(f"  ModeloIA {objetivo}: creado")
            else:
                # Eliminar duplicados del mismo proveedor (heredados de seeds viejos
                # que con get_or_create acumulaban en vez de reemplazar).
                for dup in candidatos:
                    if dup.pk == objetivo.pk:
                        continue
                    if _borrable(dup):
                        dup.delete()
                        self.stdout.write(f"  ModeloIA {dup}: eliminado (duplicado de {proveedor})")
                    else:
                        self.stdout.write(self.style.WARNING(
                            f"  ModeloIA {dup} (duplicado de {proveedor}): no se elimina "
                            "(activo o con análisis)"))

                cambios = []
                if objetivo.modelo != datos["modelo"]:
                    cambios.append(f"modelo {objetivo.modelo} -> {datos['modelo']}")
                    objetivo.modelo = datos["modelo"]
                if objetivo.formato_salida != datos["formato_salida"]:
                    cambios.append(f"formato_salida {objetivo.formato_salida} -> {datos['formato_salida']}")
                    objetivo.formato_salida = datos["formato_salida"]

                if cambios:
                    objetivo.save()
                    self.stdout.write(f"  ModeloIA {objetivo.proveedor}: actualizado ({', '.join(cambios)})")
                else:
                    self.stdout.write(f"  ModeloIA {objetivo}: ya existía")

            if primero is None:
                primero = objetivo

        # Eliminar proveedores que ya no están en el catálogo (modelos deprecados),
        # siempre que no sean el activo ni tengan análisis históricos asociados.
        obsoletos = ModeloIA.objects.exclude(proveedor__in=deseados)
        for obsoleto in obsoletos:
            if _borrable(obsoleto):
                obsoleto.delete()
                self.stdout.write(f"  ModeloIA {obsoleto}: eliminado (fuera de catálogo)")
            else:
                motivo = "es el ACTIVO" if obsoleto.pk == activo_id else "tiene análisis históricos"
                self.stdout.write(self.style.WARNING(
                    f"  ModeloIA {obsoleto} no se elimina ({motivo}; cambiar en admin)"))

        # Deja activo el primero de la lista si todavía no hay configuración.
        if primero and not ConfiguracionIA.objects.exists():
            ConfiguracionIA.objects.create(modelo_activo=primero)
            self.stdout.write(f"  ConfiguracionIA: activado {primero}")
