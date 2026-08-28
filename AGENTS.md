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
- ✅ `core/management/commands/seed_init.py`: seed base aplicado (Sistemas: BALANCES, FINANCIAMIENTO; ModeloIA: Groq/Gemini/OpenRouter; ConfiguracionIA activa: Groq)
- ✅ `core/management/commands/seed_tickets.py`: seed demo (5 solicitantes espanol + N tickets lorem, contables)
- ✅ `core/templates/core/base.html`: layout general (sidebar, header, badges), Tailwind CDN + HTMX, **dark mode con toggle sol/luna**, `{% block extra_js %}` al final
- ✅ `core/templates/core/ticket_list.html`: tabla con **filtrado client-side switcheable** (ver PLAN abajo), badges de estado, empty state, clases `dark:` aplicadas
- ✅ `core/templates/core/partials/ticket_table.html`: partial (tabla + paginacion), target `#tabla-tickets`, cada `<tr>` con `data-sistema`/`data-estado`
- ✅ `TicketListView.get_template_names()`: devuelve partial si `HX-Request` header presente
- ✅ `TicketListView.get_queryset()`: superuser ve todos los tickets sin filtro de rol/sistema; en modo cliente aplica SOLO visibilidad por rol (+ `paginate_by=500`), en modo server filtra/pagina
- ✅ **Bug filtro de sistemas resuelto**: `get_context_data()` — superuser ve `Sistema.objects.all()` en el dropdown (consistente con bypass de `get_queryset`); no-superuser ve `_sistemas_visibles()`
- ✅ `core/context_processors.py` (nuevo): expone `MODO_FILTRO_CLIENTE` en todos los templates (leído de settings)
- ✅ **Admin**: `UsuarioSistemaInline` (tabular) dentro de `UsuarioAdmin` para asignar sistemas desde el form del usuario. Duplicados los valida el formset nativo antes de guardar (con `unique_together` de BD como respaldo)
- ✅ **Flag desde .env**: `MODO_FILTRO_CLIENTE` = `env.bool(...)` en `settings.py`, default `True`. Definido en `.env`. Debounce 200ms client y server
- ❌ Pendiente: `ticket_form.html`, `ticket_detail.html`, `login.html` (dan TemplateDoesNotExist)
- ❌ Pendiente: migrar Tailwind a build compilado
- ❌ Pendiente: `settings.HUEY` para activar cola de tareas

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
- **Antes de commitear**: preguntar SIEMPRE al usuario si quiere actualizar `AGENTS.md` (el usuario no lo pide solo; el agente debe ofrecerlo). Se trabaja en varias maquinas y este archivo es el contexto compartido.

## Archivos clave
```
config/
  settings.py      # DB via env('DATABASE_URL'), AUTH_USER_MODEL="core.Usuario"
  urls.py          # Solo admin por ahora
core/
  models.py        # Modelos completos (258 lineas)
  admin.py         # Admin completo con inlines (UsuarioSistemaInline en UsuarioAdmin)
  views.py         # CBVs/FBVs con permisos por rol + bypass superuser + get_template_names HTMX + modo cliente/server
  forms.py         # TicketForm, ComentarioForm, AdjuntoForm/AdjuntoFormSet
  context_processors.py  # Expone MODO_FILTRO_CLIENTE a templates
  urls.py          # Rutas app (listado, creacion, detalle, acciones, login/logout)
  management/commands/seed_init.py     # Carga sistemas y ModeloIA
  management/commands/seed_tickets.py  # Seed demo: solicitantes + tickets lorem
  templates/core/
    base.html                        # Layout con Tailwind CDN + HTMX 1.9.10 + dark mode + block extra_js
    ticket_list.html                 # Lista con filtros client-side switcheable + JS + include partial
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

# Filtrado client-side (demo) vs server-side (produccion)
MODO_FILTRO_CLIENTE=True
```
En `settings.py`: `DATABASES = {'default': env.db_url('DATABASE_URL')}`
- `MODO_FILTRO_CLIENTE` = `env.bool('MODO_FILTRO_CLIENTE', default=True)` — cambiar a False y reiniciar el proceso para server-side.

## Comandos utiles
```bash
.\venv\Scripts\python.exe manage.py runserver
.\venv\Scripts\python.exe manage.py createsuperuser
.\venv\Scripts\python.exe manage.py makemigrations
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py shell
.\venv\Scripts\python.exe manage.py seed_init      # sistemas + catalogos IA (base)
.\venv\Scripts\python.exe manage.py seed_tickets    # solicitantes + tickets demo (opcional --reset, --tickets N)
# seed_tickets --reset borra SOLO los tickets de los 5 solicitantes del seed + esos 5 usuarios (no toca otros usuarios)
# on_delete de Ticket.solicitante -> Usuario es PROTECT: no se puede borrar un usuario con tickets asociados
```

## Proximos pasos (Fase 1)
1. ✅ Bug filtro de sistemas resuelto (superuser ve todos en dropdown vía `is_superuser` en `get_context_data`)
2. ✅ Filtrado client-side implementado (PLAN abajo) — con switch a server-side vía flag `.env`
3. Templates: `ticket_form.html`, `ticket_detail.html`, `login.html` (referencia Figma)
4. HTMX partials para interacciones en detalle (tomar ticket, cambiar estado, comentar)
5. **Menu desplegable en el icono de usuario** (header): opcion "Cambiar password" + mover ahi el boton "Salir", ambos con iconos amigables
6. Tailwind config + build compilado (reemplazar CDN)
7. `settings.HUEY` para activar cola de tareas

## Notas para proxima sesion
- No tocar modelos ni admin (estan cerrados)
- Fase 2 **no** se implementa hasta cerrar Fase 1 completo
- Huey ya configurado en tasks.py, falta settings.HUEY
- `ai/models.py` vacio intencionalmente (modelos IA en core)
- **Settings y .env**: `DATABASE_URL` y `MODO_FILTRO_CLIENTE` se leen SOLO al arrancar el proceso. Cambiarlos (en `.env` o `settings.py`) requiere reiniciar/redeploy (Gunicorn/Render). No cambian en caliente.
- **Accesos a sistemas en admin**: `UsuarioSistemaInline` dentro de `UsuarioAdmin`. Duplicados los valida el formset nativo de Django antes de guardar (el `unique_together` de BD es respaldo). No hace falta `related_name` en `UsuarioSistema` por ahora.
- El carrusel multiMCP tuvo problemas en sesion anterior: Groq/Cerebras con modelos deprecados, Kimi/SambaNova sin saldo, NVIDIA con funcion no encontrada, Gemini modelo deprecado. Revisar IDs de modelos.
- **Dark mode**: Templates futuros (`ticket_form.html`, `ticket_detail.html`, `login.html`) deben crearse con clases `dark:` listas. Toggle implementado en `base.html` con `localStorage` + `prefers-color-scheme`, transición suave (`transition-colors duration-200` en body), iconos SVG inline sol/luna. Paleta de fondo dark: sidebar `slate-900`, fondo `#172233` (tono intermedio), tarjetas/inputs `slate-800`/`slate-700`. Light: fondo `gray-100`, tarjetas `white`.
  - **Comportamiento del toggle**: default SIEMPRE light en primera visita (ignora pref del OS); el toggle guarda la eleccion en `localStorage` (`theme` = `'dark'`/`'light'`) y la aplica en futuras cargas. Script init: agregar clase `dark` solo si `localStorage.theme === 'dark'`. Toggle (vanilla JS, no HTMX): `document.documentElement.classList.toggle('dark')` + guardar valor.
- **Links/titulos teal en modo light**: usar `text-teal-700 hover:text-teal-900` (NO `text-teal-400`, contrasta mal sobre fondo claro), con `dark:text-teal-400 dark:hover:text-teal-300` en modo oscuro. Ejemplo en el titulo del ticket en `partials/ticket_table.html`.

---

## ✅ PLAN: Filtrado client-side (demo) con switch a server-side (produccion)

**Estado: IMPLEMENTADO (commit `bf80dd2`).** Objetivo: reproducir el feel de Angular Material (`mat-table` + `filterPredicate`): filtrado **instantaneo en el navegador** (0 round-trips a Neon) para la demo del curso. Diseñado con **feature-flag** para volver a server-side en produccion sin reescribir.

### Arquitectura: feature-flag
- Flag en `config/settings.py`: `MODO_FILTRO_CLIENTE = env.bool('MODO_FILTRO_CLIENTE', default=True)` — leído de `.env`. `True` (demo) / `False` (produccion).
- `core/context_processors.py` lo expone como `MODO_FILTRO_CLIENTE` en todos los templates.
- `True` → client-side; `False` → vuelve a funcionar HTMX server-side usando el `get_queryset()` que se conservo.
- Debounce configurado a **200ms** tanto en client (JS) como en server (HTMX).
- Para produccion: cambiar a `MODO_FILTRO_CLIENTE=False` en `.env` (o `settings.py`) y reiniciar el proceso.

### Pasos de implementacion (resuelto)

**1. `core/views.py — TicketListView.get_queryset()`** ✅
- Modo cliente: aplica SOLO visibilidad por rol (superuser/solicitante/desarrollador) y via `get_paginate_by()` sube a 500 (trae todo).
- Modo server (flag False): comportamiento completo (filtros sistema/estado/q + paginacion 20).

**2. `core/templates/core/partials/ticket_table.html`** ✅
- Cada `<tr>` tiene `data-sistema` y `data-estado`. Inofensivo en modo server.

**3. `core/templates/core/ticket_list.html`** ✅
- HTMX del form envuelto en `{% if not MODO_FILTRO_CLIENTE %}`; contador `<span id="filtro-contador">`; en modo server aparece el enlace "Limpiar".

**4. JS client-side (`{% block extra_js %}`)** ✅
- Se incluye solo si `MODO_FILTRO_CLIENTE` (el `{% if %}` va DENTRO del block, no afuera — envolver un `{% block %}` en `{% if %}` no funciona en Django).
- Escucha: `input` en `[name=q]` (debounce 200ms) + `change` en `[name=sistema]` y `[name=estado]`. Filtra por substring en titulo (case-insensitive) + match exacto sistema/estado. Ocultar/mostrar filas + actualizar contador.

**5. Paginacion (demo)** ✅
- Ocultada en modo cliente: `{% if page_obj.has_other_pages and not MODO_FILTRO_CLIENTE %}`.

**6. Migracion a produccion (futuro)** ✅
- Poner `MODO_FILTRO_CLIENTE=False`. El form recupera `hx-get`, el queryset vuelve a filtrar/paginar en server, el JS client-side deja de cargar. Volumen alto (>~miles por usuario) → server-side.

### Verificacion
- ✅ Verificado con test client: modo cliente trae todo + contador/JS sin `hx-get`; modo server filtra (`estado=PENDIENTE` → 1 fila) + `hx-get` activo. Partial HTMX OK en ambos modos.

### Recordatorios
- Encoding templates: PowerShell `[System.IO.File]::WriteAllText(..., UTF8)`, NUNCA `Set-Content`.
- Los selects de sistema y estado usan la MISMA metodologia client-side que `q` (los 3 disparan el filtrado en el navegador sin recargar).
- **Django `{% if %}` no soporta parentesis** para agrupar condiciones (dio TemplateSyntaxError). Usar ifs anidados.
- **Django venv**: hay que instalar `django-environ` (no venia instalado aunque settings lo importa).