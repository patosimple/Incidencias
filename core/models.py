"""
Modelos del sistema de tickets, traducidos directamente del diagrama UML
(Trabajo Práctico - Unidad 1). No hay decisiones de diseño pendientes acá:
todo lo que sigue ya fue discutido y cerrado.

Ubicación sugerida: core/models.py (ajustar el nombre de la app si usás otro).
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Usuario y roles
# ---------------------------------------------------------------------------

class RolUsuario(models.TextChoices):
    SOLICITANTE = "SOLICITANTE", "Solicitante"
    DESARROLLADOR = "DESARROLLADOR", "Desarrollador"
    COORDINADOR = "COORDINADOR", "Coordinador"  # reservado a futuro, hoy sin uso


class Usuario(AbstractUser):
    """
    Extiende el User de Django. is_staff/is_superuser (ya provistos por
    AbstractUser) son los que habilitan el acceso al panel admin -- separado
    del rol de negocio (RolUsuario), que es otra cosa.
    Recordar en settings.py: AUTH_USER_MODEL = "core.Usuario"
    (definir esto ANTES de la primera migración).
    """
    rol = models.CharField(max_length=20, choices=RolUsuario.choices)

    def __str__(self):
        return self.get_full_name() or self.username


# ---------------------------------------------------------------------------
# Sistema (catálogo de aplicaciones sobre las que se reporta)
# ---------------------------------------------------------------------------

class Sistema(models.Model):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=20, unique=True)

    class Meta:
        verbose_name = "Sistema"
        verbose_name_plural = "Sistemas"

    def __str__(self):
        return self.nombre


class UsuarioSistema(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    sistema = models.ForeignKey(Sistema, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("usuario", "sistema")
        verbose_name = "Acceso a sistema"
        verbose_name_plural = "Accesos a sistemas"


# ---------------------------------------------------------------------------
# Ticket
# ---------------------------------------------------------------------------

class EstadoTicket(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    EN_PROCESO = "EN_PROCESO", "En proceso"
    CERRADO = "CERRADO", "Cerrado"
    REABIERTO = "REABIERTO", "Reabierto"


class Ticket(models.Model):
    titulo = models.CharField(max_length=200)
    sistema = models.ForeignKey(Sistema, on_delete=models.PROTECT, related_name="tickets")
    solicitante = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name="tickets_reportados"
    )
    descripcion_original = models.TextField(help_text="Texto enriquecido (HTML/Markdown)")
    estado = models.CharField(
        max_length=20, choices=EstadoTicket.choices, default=EstadoTicket.PENDIENTE
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)

    # Colaboración sin asignado único
    desarrolladores = models.ManyToManyField(
        Usuario, through="TicketDesarrollador", related_name="tickets_tomados"
    )

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"#{self.pk} - {self.titulo}"


class TicketDesarrollador(models.Model):
    """Relación muchos-a-muchos: modela que varios devs trabajen el mismo
    ticket a la vez, sin asignado único."""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    tomado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("ticket", "usuario")
        verbose_name = "Desarrollador de ticket"
        verbose_name_plural = "Desarrolladores de ticket"


# ---------------------------------------------------------------------------
# Comentario
# ---------------------------------------------------------------------------

class Comentario(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comentarios")
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    cuerpo = models.TextField(help_text="Texto enriquecido (HTML/Markdown)")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Comentario"
        verbose_name_plural = "Comentarios"
        ordering = ["creado_en"]


# ---------------------------------------------------------------------------
# Adjunto (FKs directas + CHECK, no relación polimórfica)
# ---------------------------------------------------------------------------

class TipoAdjunto(models.TextChoices):
    IMAGEN = "IMAGEN", "Imagen"
    DOCUMENTO = "DOCUMENTO", "Documento"


class Adjunto(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="adjuntos", null=True, blank=True
    )
    comentario = models.ForeignKey(
        Comentario, on_delete=models.CASCADE, related_name="adjuntos", null=True, blank=True
    )
    nombre_archivo = models.CharField(max_length=255)
    tipo_archivo = models.CharField(max_length=20, choices=TipoAdjunto.choices)
    archivo = models.FileField(upload_to="adjuntos/%Y/%m/")
    subido_por = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    subido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Adjunto"
        verbose_name_plural = "Adjuntos"
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(ticket__isnull=False, comentario__isnull=True)
                    | models.Q(ticket__isnull=True, comentario__isnull=False)
                ),
                name="chk_pertenece_a_uno",
            )
        ]

    def clean(self):
        # Defensa a nivel de aplicación además del CHECK de la base
        if bool(self.ticket_id) == bool(self.comentario_id):
            raise ValidationError(
                "El adjunto debe pertenecer exactamente a un ticket o a un comentario, no a ambos ni a ninguno."
            )


# ---------------------------------------------------------------------------
# Modelo de IA (catálogo abierto) y configuración activa
# ---------------------------------------------------------------------------

class ModeloIA(models.Model):
    """Catálogo abierto de proveedores/modelos de IA. No guarda API keys --
    esas viven en variables de entorno, mapeadas por el campo `proveedor`
    (ver ai/providers.py)."""
    proveedor = models.CharField(max_length=50, help_text="Ej: Groq, Gemini, OpenRouter")
    modelo = models.CharField(max_length=100, help_text="Ej: llama-3.3-70b, gemini-2.0-flash")
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Modelo de IA"
        verbose_name_plural = "Modelos de IA"

    def __str__(self):
        return f"{self.proveedor} / {self.modelo}"


class ConfiguracionIA(models.Model):
    """Tabla de una sola fila: cambiar modelo_activo desde el admin cambia
    el proveedor usado en producción, sin tocar código ni redeployar."""
    modelo_activo = models.ForeignKey(ModeloIA, on_delete=models.PROTECT)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de IA"
        verbose_name_plural = "Configuración de IA"

    def save(self, *args, **kwargs):
        self.pk = 1  # fuerza singleton
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # no se borra, es singleton

    @classmethod
    def activo(cls) -> "ModeloIA":
        config, _ = cls.objects.get_or_create(pk=1, defaults={"modelo_activo_id": None})
        return config.modelo_activo


# ---------------------------------------------------------------------------
# AnalisisIA (salida estructurada, con metadata para comparar proveedores)
# ---------------------------------------------------------------------------

class TipoAnalisis(models.TextChoices):
    CONCEPTUAL = "CONCEPTUAL", "Conceptual"
    TECNICO = "TECNICO", "Técnico"


class EstadoAprobacion(models.TextChoices):
    PENDIENTE_REVISION = "PENDIENTE_REVISION", "Pendiente de revisión"
    ACEPTADO = "ACEPTADO", "Aceptado"
    OBJETADO = "OBJETADO", "Objetado"
    NO_APLICA = "NO_APLICA", "No aplica"  # el análisis Técnico no requiere aprobación


class AnalisisIA(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="analisis")
    tipo = models.CharField(max_length=20, choices=TipoAnalisis.choices)

    # Salida estructurada (sugerencia de GPT en la etapa de análisis)
    problema = models.TextField(blank=True)
    comportamiento_esperado = models.TextField(blank=True)
    comportamiento_observado = models.TextField(blank=True)
    pasos_reproducir = models.TextField(blank=True)
    datos_relevantes = models.TextField(blank=True)
    informacion_faltante = models.TextField(blank=True)

    estado_aprobacion = models.CharField(
        max_length=20, choices=EstadoAprobacion.choices, default=EstadoAprobacion.PENDIENTE_REVISION
    )
    observacion_solicitante = models.TextField(blank=True)

    # Metadata para poder comparar resultados entre proveedores
    modelo_ia = models.ForeignKey(ModeloIA, on_delete=models.PROTECT, related_name="analisis_generados")
    version_prompt = models.CharField(max_length=50, default="v1")
    generado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Análisis de IA"
        verbose_name_plural = "Análisis de IA"
        ordering = ["-generado_en"]
