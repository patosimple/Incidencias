from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Usuario, Sistema, UsuarioSistema, Ticket, TicketDesarrollador,
    Comentario, Adjunto, ModeloIA, ConfiguracionIA, AnalisisIA,
)


class UsuarioSistemaInline(admin.TabularInline):
    model = UsuarioSistema
    extra = 1
    verbose_name = "Acceso a sistema"
    verbose_name_plural = "Accesos a sistemas"


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    # Alta de usuarios y gestión de contraseñas ya vienen resueltas por
    # UserAdmin (hasheo seguro incluido). Se agrega el campo `rol` propio y
    # el inline de accesos a sistemas (relación N a N vía UsuarioSistema).
    fieldsets = UserAdmin.fieldsets + (
        ("Rol de negocio", {"fields": ("rol",)}),
    )
    inlines = [UsuarioSistemaInline]
    list_display = ("username", "email", "rol", "is_staff", "is_active")
    list_filter = ("rol", "is_staff", "is_active")


@admin.register(Sistema)
class SistemaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre")
    search_fields = ("codigo", "nombre")


@admin.register(UsuarioSistema)
class UsuarioSistemaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "sistema")
    list_filter = ("sistema",)


class ComentarioInline(admin.TabularInline):
    model = Comentario
    extra = 0


class AdjuntoInline(admin.TabularInline):
    model = Adjunto
    fk_name = "ticket"
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "titulo", "sistema", "estado", "solicitante", "creado_en")
    list_filter = ("sistema", "estado")
    search_fields = ("titulo", "descripcion_original")
    inlines = [ComentarioInline, AdjuntoInline]


@admin.register(TicketDesarrollador)
class TicketDesarrolladorAdmin(admin.ModelAdmin):
    list_display = ("ticket", "usuario", "tomado_en")


@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ("ticket", "usuario", "creado_en")


@admin.register(Adjunto)
class AdjuntoAdmin(admin.ModelAdmin):
    list_display = ("nombre_archivo", "tipo_archivo", "ticket", "comentario", "subido_por")


@admin.register(ModeloIA)
class ModeloIAAdmin(admin.ModelAdmin):
    list_display = ("proveedor", "modelo", "actualizado_en")


@admin.register(ConfiguracionIA)
class ConfiguracionIAAdmin(admin.ModelAdmin):
    # Solo debería existir una fila; esto lo refuerza en la UI del admin.
    list_display = ("modelo_activo", "actualizado_en")

    def has_add_permission(self, request):
        return not ConfiguracionIA.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AnalisisIA)
class AnalisisIAAdmin(admin.ModelAdmin):
    list_display = ("ticket", "tipo", "modelo_ia", "estado_aprobacion", "generado_en")
    list_filter = ("tipo", "estado_aprobacion", "modelo_ia")
