# AGENTS.md - Contexto persistente para sesiones de desarrollo

## Resumen del proyecto
**Sistema de tickets** - Gestion interna de bugs para apps "Balances" y "Financiamiento" (financiamiento politico).
- **Fase 1 (actual)**: Tickets convencional - login, listado, creacion, detalle, comentarios, adjuntos, toma colaborativa, cambio de estado, admin de sistemas/accesos. **Sin IA**.
- **Fase 2 (futura)**: Capa IA - analisis Conceptual/Tecnico automaticos via LLM (esqueleto ya existe en `ai/`).

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
- ✅ `core/urls.py` y `config/urls.py`: listado, creacion, detalle, tomar ticket, cambiar estado, comentar, login/logout
- ✅ `core/forms.py`: `TicketForm`, `ComentarioForm`, `AdjuntoForm`/`AdjuntoFormSet`
- ✅ `core/views.py`: `TicketListView`, `TicketCreateView`, `TicketDetailView`, `tomar_ticket`, `cambiar_estado_ticket`, `agregar_comentario` (permisos por rol aplicados)
- ✅ `core/management/commands/seed_datos.py`: seed aplicado (Sistemas: BALANCES, FINANCIAMIENTO; ModeloIA: Groq/Gemini/OpenRouter; ConfiguracionIA activa: Groq)
- ✅ `core/templates/core/base.html`: layout general (sidebar, header, badges), Tailwind CDN + HTMX
- ✅ `core/templates/core/ticket_list.html`: tabla con filtros HTMX (sin recarga), badges de estado, paginacion, empty state
- ✅ `core/templates/core/partials/ticket_table.html`: partial HTMX (tabla + paginacion), target `#tabla-tickets`
- ✅ `TicketListView.get_template_names()`: devuelve partial si `HX-Request` header presente
- ✅ `TicketListView.get_queryset()`: superuser ve todos los tickets sin filtro de rol/sistema
- ❌ Pendiente: `ticket_form.html`, `ticket_detail.html`, `login.html` (dan TemplateDoesNotExist)
- ❌ Pendiente: migrar Tailwind a build compilado
- ❌ Pendiente: `settings.HUEY` para activar cola de tareas
- ⚠️ Bug conocido: filtro de sistemas no muestra opciones (investigar `sistemas_disponibles` en context)
- ⚠️ Pendiente: agregar `hx-get`/`hx-trigger` a los 2 selects del filtro (sistema y estado) para que disparen individualmente sin depender del form

## Modelo de datos (no modificar sin confirmar)
| Modelo | Clave |
|--------|-------|
| `Usuario` | Extiende `AbstractUser`, campo `rol` (SOLICITANTE/DESARROLLADOR/COORDINADOR) |
| `Sistema` | Catalogo (Balances, Financiamiento) |
| `UsuarioSistema` | M2M usuario-sistema (accesos) |
| `Ticket` | titulo, sistema, solicitante, descripcion_original, estado, desarrolladores (M2M through `TicketDesarrollador`) |
| `Comentario` | ticket, usuario, cuerpo |
| `Adjunto` | ticket XOR comentario (CheckConstraint), archivo, tipo (IMAGEN/DOCUMENTO) |
| `ModeloIA` | Catalogo proveedores/modelos (Fase 2) |
| `ConfiguracionIA` | Singleton, `modelo_activo` FK a ModeloIA (Fase 2) |
| `AnalisisIA` | ticket, tipo (CONCEPTUAL/TECNICO), salida estructurada, estado_aprobacion, modelo_ia, version_prompt (Fase 2) |

## Convenciones criticas
- **Nombres en espanol**, snake_case: `descripcion_original`, `estado_aprobacion`, `creado_en`
- `is_staff`/`is_superuser` = acceso admin (separado de `rol` de negocio)
- `is_superuser` = ve todos los tickets sin restriccion de rol (bypass en `get_queryset`)
- Templates siguen prototipo Figma (sidebar, badges, cards IA)
- Permisos por rol: Solicitante ve sus tickets + analisis Conceptual; Desarrollador ve tickets de sus sistemas + ambos analisis
- **Encoding**: SIEMPRE escribir templates con `[System.IO.File]::WriteAllText(..., UTF8)` en PowerShell. Nunca usar `Set-Content` (produce Windows-1252 y rompe Django con UnicodeDecodeError)
- Correr manage.py con `.\venv\Scripts\python.exe manage.py <comando>` (el activate.bat no persiste en PowerShell)

## Archivos clave
```
config/
  settings.py      # DB via env('DATABASE_URL'), AUTH_USER_MODEL="core.Usuario"
  urls.py          # Solo admin por ahora
core/
  models.py        # Modelos completos (258 lineas)
  admin.py         # Admin completo con inlines
  views.py         # CBVs/FBVs con permisos por rol + bypass superuser + get_template_names HTMX
  forms.py         # TicketForm, ComentarioForm, AdjuntoForm/AdjuntoFormSet
  urls.py          # Rutas app (listado, creacion, detalle, acciones, login/logout)
  management/commands/seed_datos.py  # Carga sistemas y ModeloIA
  templates/core/
    base.html                        # Layout con Tailwind CDN + HTMX 1.9.10
    ticket_list.html                 # Lista con filtros HTMX + include partial
    partials/ticket_table.html       # Partial: tabla + paginacion (target #tabla-tickets)
ai/
  providers.py     # AIProvider abstracto + Groq/Gemini/OpenRouter (NotImplementedError)
  tasks.py         # Huey task generar_analisis_ticket (Fase 2)
  models.py        # Vacio (modelos IA estan en core/models.py)
```

## Configuracion DB (.env)
```bash
# Solo una activa, comentar/descomentar:
DATABASE_URL=postgresql://neondb_owner:...@ep-...neon.tech/incidencias?sslmode=require
# DATABASE_URL=postgresql://postgres@localhost/incidencias
```
En `settings.py`: `DATABASES = {'default': env.db_url('DATABASE_URL')}`

## Comandos utiles
```bash
.\venv\Scripts\python.exe manage.py runserver
.\venv\Scripts\python.exe manage.py createsuperuser
.\venv\Scripts\python.exe manage.py makemigrations
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py shell
.\venv\Scripts\python.exe manage.py seed_datos
```

## Proximos pasos (Fase 1)
1. ⚠️ Bug: investigar por que `sistemas_disponibles` no muestra opciones en el filtro de ticket_list
2. ⚠️ Agregar `hx-get`/`hx-trigger` individuales a los selects de sistema y estado en ticket_list
3. Templates: `ticket_form.html`, `ticket_detail.html`, `login.html` (referencia Figma)
4. HTMX partials para interacciones en detalle (tomar ticket, cambiar estado, comentar)
5. Tailwind config + build compilado (reemplazar CDN)
6. `settings.HUEY` para activar cola de tareas

## Notas para proxima sesion
- No tocar modelos ni admin (estan cerrados)
- Fase 2 **no** se implementa hasta cerrar Fase 1 completo
- Huey ya configurado en tasks.py, falta settings.HUEY
- `ai/models.py` vacio intencionalmente (modelos IA en core)
- El carrusel multiMCP tuvo problemas en sesion anterior: Groq/Cerebras con modelos deprecados, Kimi/SambaNova sin saldo, NVIDIA con funcion no encontrada, Gemini modelo deprecado. Revisar IDs de modelos.