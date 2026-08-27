# AGENTS.md - Contexto persistente para sesiones de desarrollo

## Resumen del proyecto
**Sistema de tickets** - Gestión interna de bugs para apps "Balances" y "Financiamiento" (financiamiento político).
- **Fase 1 (actual)**: Tickets convencional - login, listado, creación, detalle, comentarios, adjuntos, toma colaborativa, cambio de estado, admin de sistemas/accesos. **Sin IA**.
- **Fase 2 (futura)**: Capa IA - análisis Conceptual/Técnico automáticos via LLM (esqueleto ya existe en `ai/`).

## Stack
- Django 5.2 + PostgreSQL (psycopg)
- Huey + PostgresHuey (sin Redis)
- Templates Django + HTMX + Tailwind
- Whitenoise + Gunicorn para deploy (Render + Neon/Supabase)

## Estado actual
- ✅ Models (`core/models.py`) y Admin (`core/admin.py`) completos
- ✅ Migraciones aplicadas
- ✅ Admin funcionando en `/admin/`
- ✅ Esqueleto IA en `ai/providers.py`, `ai/tasks.py`, `ai/models.py`
- ✅ `core/urls.py` y `config/urls.py`: listado, creación, detalle, tomar ticket, cambiar estado, comentar, login/logout
- ✅ `core/forms.py`: `TicketForm`, `ComentarioForm`, `AdjuntoForm`/`AdjuntoFormSet`
- ✅ `core/views.py`: `TicketListView`, `TicketCreateView`, `TicketDetailView`, `tomar_ticket`, `cambiar_estado_ticket`, `agregar_comentario` (permisos por rol aplicados)
- ✅ `core/management/commands/seed_datos.py`: carga sistemas y catálogo ModeloIA
- ✅ `core/templates/core/base.html`: layout general (sidebar, header, badges), Tailwind CDN
- ✅ `core/templates/core/ticket_list.html`: versión mínima funcional
- ❌ Pendiente: `ticket_form.html`, `ticket_detail.html`, `login.html` (dan TemplateDoesNotExist)
- ❌ Pendiente: migrar Tailwind a build compilado, HTMX partials

## Modelo de datos (no modificar sin confirmar)
| Modelo | Clave |
|--------|-------|
| `Usuario` | Extiende `AbstractUser`, campo `rol` (SOLICITANTE/DESARROLLADOR/COORDINADOR) |
| `Sistema` | Catálogo (Balances, Financiamiento) |
| `UsuarioSistema` | M2M usuario-sistema (accesos) |
| `Ticket` | titulo, sistema, solicitante, descripcion_original, estado, desarrolladoes (M2M through `TicketDesarrollador`) |
| `Comentario` | ticket, usuario, cuerpo |
| `Adjunto` | ticket XOR comentario (CheckConstraint), archivo, tipo (IMAGEN/DOCUMENTO) |
| `ModeloIA` | Catálogo proveedores/modelos (Fase 2) |
| `ConfiguracionIA` | Singleton, `modelo_activo` FK a ModeloIA (Fase 2) |
| `AnalisisIA` | ticket, tipo (CONCEPTUAL/TECNICO), salida estructurada, estado_aprobacion, modelo_ia, version_prompt (Fase 2) |

## Convenciones críticas
- **Nombres en español**, snake_case: `descripcion_original`, `estado_aprobacion`, `creado_en`
- `is_staff`/`is_superuser` = acceso admin (separado de `rol` de negocio)
- Templates siguen prototipo Figma (sidebar, badges, cards IA)
- Permisos por rol: Solicitante ve sus tickets + análisis Conceptual; Desarrollador ve tickets de sus sistemas + ambos análisis

## Archivos clave
```
config/
  settings.py      # DB via env('DATABASE_URL'), AUTH_USER_MODEL="core.Usuario"
  urls.py          # Solo admin por ahora
core/
  models.py        # Modelos completos (258 líneas)
  admin.py         # Admin completo con inlines
  views.py         # CBVs/FBVs con permisos por rol
  forms.py         # TicketForm, ComentarioForm, AdjuntoForm/AdjuntoFormSet
  urls.py          # Rutas app (listado, creación, detalle, acciones, login/logout)
  management/commands/seed_datos.py  # Carga sistemas y ModeloIA
ai/
  providers.py     # AIProvider abstracto + Groq/Gemini/OpenRouter (NotImplementedError)
  tasks.py         # Huey task generar_analisis_ticket (Fase 2)
  models.py        # Vacío (modelos IA están en core/models.py)
```

## Configuración DB (.env)
```bash
# Solo una activa, comentar/descomentar:
DATABASE_URL=postgresql://neondb_owner:...@ep-...neon.tech/incidencias?sslmode=require
# DATABASE_URL=postgresql://postgres@localhost/incidencias
```
En `settings.py`: `DATABASES = {'default': env.db_url('DATABASE_URL')}`

## Comandos útiles
```bash
python manage.py runserver
python manage.py createsuperuser
python manage.py makemigrations
python manage.py migrate
python manage.py shell
```

## Próximos pasos (Fase 1)
1. Templates: `ticket_form.html`, `ticket_detail.html`, `login.html` (referencia Figma)
2. HTMX partials para interacciones (tomar ticket, cambiar estado, comentar)
3. Tailwind config + build compilado (reemplazar CDN)
4. `settings.HUEY` para activar cola de tareas

## Notas para próxima sesión
- No tocar modelos ni admin (están cerrados)
- Fase 2 **no** se implementa hasta cerrar Fase 1 completo
- Huey ya configurado en tasks.py, falta settings.HUEY
- `ai/models.py` vacío intencionalmente (modelos IA en core)