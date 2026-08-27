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
- ❌ Pendiente: `urls.py`, `forms.py`, `views.py`, templates, HTMX/Tailwind

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
  views.py         # Vacío
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
1. `urls.py` - rutas app (login, tickets, etc.)
2. `forms.py` - forms para Ticket, Comentario, Adjunto, Usuario
3. `views.py` - CBVs/FBVs con permisos por rol
4. Templates base + partials HTMX
5. Tailwind config + estilos
6. Login/logout + middleware de autenticación

## Notas para próxima sesión
- No tocar modelos ni admin (están cerrados)
- Fase 2 **no** se implementa hasta cerrar Fase 1 completo
- Huey ya configurado en tasks.py, falta settings.HUEY
- `ai/models.py` vacío intencionalmente (modelos IA en core)