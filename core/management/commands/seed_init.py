"""
Carga los datos base: sistemas y catalogo de modelos de IA.

Uso: python manage.py seed_init
"""

from django.core.management.base import BaseCommand

from core.models import Sistema, ModeloIA, ConfiguracionIA, AnalisisIA


class Command(BaseCommand):
    help = "Carga los datos iniciales del sistema (sistemas y catálogo de modelos de IA)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--update_prompt",
            action="store_true",
            help="Actualiza el prompt existente de los sistemas aunque ya tengan "
                 "uno (por defecto solo se escribe si el sistema es nuevo o está vacío).",
        )

    def handle(self, *args, **options):
        self.update_prompt = options["update_prompt"]
        self._seed_sistemas()
        self._seed_modelos_ia()
        self.stdout.write(self.style.SUCCESS("Seed init completo."))

    def _seed_sistemas(self):
        # El campo `prompt` es contexto opcional para la IA: describe qué hace
        # el sistema y qué datos conoce el usuario final. Por defecto solo se
        # escribe si el sistema es nuevo o no tiene prompt todavía (no pisa
        # ediciones del admin). Con --update_prompt se sobrescribe siempre con la
        # versión del seed (útil para sincronizar un entorno, ej. Neon).
        sistemas = [
            # Los prompts reflejan la descripción que el usuario setea desde el
            # admin (se sincronizaron con la DB el 06/09/2026).
            {
                "codigo": "BALANCES",
                "nombre": "Balances",
                "prompt": (
                    "Aplicación web destinada a la gestión y presentación de "
                    "estados contables anuales de agrupaciones políticas. Permite "
                    "a los usuarios registrados crear, completar, administrar, "
                    "controlar, presentar y rectificar estados contables "
                    "correspondientes a distintos ejercicios económicos. El "
                    "usuario puede referirse al estado contable como balance "
                    "tambien. Permite: gestión de estados contables, carga de "
                    "saldos de cuentas patrimoniales y de resultados, carga de "
                    "información mediante registros detallados, incorporación de "
                    "notas y aportes privados, importación de información desde "
                    "archivos externos, control del balanceo contable, generación "
                    "y visualización de reportes, carga del Estado de Flujo de "
                    "Efectivo, incorporación de anexos voluntarios, notas y Anexo "
                    "de Capacitación, carga del Informe del Auditor y presentación "
                    "de los estados contables. Los estados pueden encontrarse en "
                    "estado Borrador, ser presentados y posteriormente recibidos "
                    "por la Secretaría Electoral. Una vez presentados dejan de ser "
                    "editables, salvo que sean rechazados por la Secretaría "
                    "Electoral y devueltos a estado borrador. También permite "
                    "realizar rectificaciones de estados contables previamente "
                    "recibidos. Los reportes pueden descargarse en formato PDF "
                    "para su control, impresión y firma."
                ),
            },
            {
                "codigo": "FINANCIAMIENTO",
                "nombre": "Financiamiento",
                "prompt": (
                    "Aplicación web destinada a la gestión y presentación de "
                    "informes vinculados al financiamiento de campañas de actos "
                    "electorales. Permite a los usuarios registrados generar, "
                    "completar, administrar, presentar y consultar informes "
                    "correspondientes a distintas elecciones, etapas y tipos de "
                    "informe.\n"
                    "Permite: Gestion básica de usuarios, Generacion de informes "
                    "de distintos tipos segun la etapa de la cada eleccion. El "
                    "user puede editar sus informes en estado BORRADOR, y los "
                    "puede presentar (estado PREPARADO), los puede volver a pasar "
                    "a estado BORRADOR, y la secretaría electoral puede recibirlos "
                    "(etado RECIBIDO). Los informes RECIBIDOS pueden ser "
                    "RECTIFICADOS por usuario. El user puede importar información "
                    "desde archivos externos, cuando el tipo de informe lo "
                    "permite. Se pueden generar vistas previas del informe "
                    "completo y de cada seccion. Los informes pueden ser impresos "
                    "y exportados/descargados en formato PDF."
                ),
            },
        ]
        for datos in sistemas:
            sistema, creado = Sistema.objects.get_or_create(
                codigo=datos["codigo"], defaults={"nombre": datos["nombre"]}
            )
            if creado or not sistema.prompt or self.update_prompt:
                sistema.prompt = datos["prompt"]
                sistema.save(update_fields=["prompt"])
            estado = "creado" if creado else "ya existía"
            if self.update_prompt and not creado:
                estado += " · prompt actualizado"
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
