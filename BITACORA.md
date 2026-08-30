# BITACORA — Interacción con el modelo (opencode)

> Documento para el trabajo práctico: registro cronológico de la construcción del sistema de tickets, con énfasis en **incidencias** (bugs / comportamientos inesperados) y **cómo se corrigieron**, mapeadas a commits y fechas.
> Fuentes: historial de `AGENTS.md` + `git log`. Fechas en formato AAAA-MM-DD.

---

## Contexto del proyecto (qué construimos)

- **Sistema de tickets** interno para gestión de bugs de las apps "Balances" y "Financiamiento".
- **Fase 1 (actual)**: tickets convencionales — login, listado, creación, detalle, comentarios, adjuntos, toma colaborativa, cambio de estado, admin de sistemas/accesos. Sin IA.
- **Fase 2 (futura)**: capa IA (análisis Conceptual/Técnico vía LLM). Esqueleto ya existe en `ai/`.

**Stack**: Django 5.2 + PostgreSQL (Neon, remota), Huey (sin Redis), Templates + HTMX + Tailwind (CDN), Whitenoise + Gunicorn para deploy.

---

## Línea de tiempo (commits + incidencias)

### 2026-08-26 — Inicialización
- **`3000973`** init proyecto + models + migrations + db neon settings.
- Models (`core/models.py`) y Admin (`core/admin.py`) completos. Migraciones aplicadas.

### 2026-08-27 — Base del listado + filtros + modos dark/light
- **`84fe2bd`** multiDB local + neon.
- **`faa4c4e`** fix `.env` + `settings.py` multiDB.
  - **Incidente**: `django-environ` no estaba instalado aunque `settings.py` lo importa → había que instalar la dependencia para que Django arranque.
- **`64f8e8c`** urls + views + forms + base.html + seed IAs/sistemas + fake index para test template.
- **`1690665`** template ticket_list + HTMX filtro búsqueda por nombre.
- **`d788e2b`** modos dark/light + actualización de pendientes.
  - Comportamiento decidido con el usuario: **default SIEMPRE light** en primera visita (ignora pref del OS); el toggle guarda la elección en `localStorage`.
- **`b6ac2f5`** update AGENTS.md con el plan de filtro dual client/server.
- **`bf80dd2`** client-server filter + selects switcheable + fix inline usuario-sistema en admin + fix is_superuser para dropdown.
  - **Incidente (filtro de sistemas en dropdown)**: un superuser con rol DESARROLLADOR veía SOLO sus sistemas visibles en el dropdown de filtrar, inconsistente con su bypass en el listado. **Corrección**: `TicketListView.get_context_data()` — superuser ve `Sistema.objects.all()`; consistent como el bypass de `get_queryset`.
  - **Incidente (inline admin)**: faltaba asignar sistemas al usuario en el admin → se agregó `UsuarioSistemaInline` (tabular) dentro de `UsuarioAdmin`. Duplicados valida el formset nativo (el `unique_together` de BD es respaldo).

### 2026-08-28 — Seeds
- **`cdbc0e4`** seed_init para IAs y Sistemas + seed_tickets para users y tickets random (con `--reset` y `--tickets N`).
  - **Decisión**: `on_delete` de `Ticket.solicitante → Usuario` es **PROTECT**: no se puede borrar un usuario con tickets asociados. El seed `--reset` borra solo los tickets + los 5 usuarios del seed, sin tocar otros.
  - Usuarios seed: 5 solicitantes (password `Solicitante123!`). El único staff/superuser es `patosimple` (creado a mano).

### 2026-08-29 — Responsive, login, password, user menu
- **`02ab11c`** responsive + fix contador y paginado en client-side (estilo Angular Material).
  - **Incidente (contador/paginador)**: cada ticket aparecía 2 veces en el DOM (tabla + cards móvil) → el filtro/paginador contaba de más. **Corrección**: agrupar los nodos por `data-ticket-id` único para contar/paginar tickets únicos.
- **`31a4445`** paleta blue (brand) + login + cambiar password + user menu.
  - **Incidente (logout 405)**: el enlace "Salir" era un `<a href>` (GET), pero Django `LogoutView` solo acepta **POST** → daba **405** y no cerraba sesión. **Corrección**: convertirlo a `<form method="post">` con CSRF.
  - **Incidente (login anónimo)**: sin `LOGIN_URL`/`LOGIN_REDIRECT_URL`, un usuario anónimo era redirigido a `/accounts/login/` que no existía. **Corrección**: `LOGIN_URL='login'`, `LOGIN_REDIRECT_URL='ticket_list'` en settings.

### Fase de afinado (sin commit aún: CRUD de detalle/creación, Quill, adjuntos, permisos)
- **Incidente (bypass superuser en detalle)**: `TicketDetailView.get_queryset()` NO tenía el bypass `is_superuser` que sí tiene el listado → un superuser con rol DESARROLLADOR y sin sistemas visibles recibía **404 en todos los tickets**. **Corrección**: `is_superuser` ve cualquier ticket (consistente con `TicketListView`).
- **Incidente (Quill: barra sin área de escritura)**: pasar el textarea directamente a `new Quill(textarea)` dejaba la barra de herramientas pero sin área editable visible. **Corrección**: usar un `<div>` contenedor (`#quill-descripcion` / `#quill-comentario`), ocultar el textarea (`style.display='none'`) y en submit copiar `quill.root.innerHTML` de vuelta al textarea.
- **Incidente (3 inputs de adjuntos)**: se intentó primero un `AdjuntoFormSet` con 3 slots "seleccionar archivo" → el usuario lo rechazó. **Corrección**: se eliminó el formset y se pasó a **un único** `<input type="file" name="archivos" multiple>` manejado con `request.FILES.getlist("archivos")` → `_guardar_adjuntos(...)` (crea un `Adjunto` por archivo). Con lista en vivo de archivos seleccionados (JS).
- **Permisos de comentar implementados** (`_puede_comentar` en views): `False` si el ticket está **CERRADO**; `True` para superuser, el creador (`solicitante_id`) y los desarrolladores que **tomaron** el ticket. El form se oculta con `{% if puede_comentar %}` y `agregar_comentario` lanza `PermissionDenied` (403) si no aplica.
- **Transiciones de estado por botones (sin select)**: `tomar_ticket` pasa PENDIENTE/REABIERTO → EN_PROCESO; `cambiar_estado_ticket` permite EN_PROCESO→CERRADO/PENDIENTE (dev/coor) y CERRADO→REABIERTO (cualquiera); setea/limpia `cerrado_en`. Tarjeta de acciones contextual oculta si no hay acciones (`_puede_actuar`).
- **Colaboradores visibles**: la sección del detalle lista quiénes tomaron el ticket (`ticket.ticketdesarrollador_set`).

---

## Incidencias recurrentes (cross-cutting) y lecciones

| Incidencia | Causa raíz | Corrección |
|---|---|---|
| Logout daba 405 | `LogoutView` solo acepta POST; el link era GET (`<a>`) | Cambiar a `<form method="post">` + CSRF |
| Superuser con 404 en detalle | `get_queryset` del detalle sin bypass `is_superuser` | Agregar bypass en detalle (consistencia con listado) |
| Superuser no veía todos los sistemas en dropdown | `get_context_data` aplicaba visibilidad por rol al dropdown | Superuser ve `Sistema.objects.all()` |
| Filtro/paginador client contaban de más | Cada ticket duplicado en DOM (tabla + cards) | Agrupar por `data-ticket-id` |
| Quill sin área editable | Pasar el textarea a `new Quill(textarea)` | Usar `<div>` contenedor + ocultar textarea |
| Encoding rompía templates | `Set-Content` en PowerShell produce Windows-1252 | **Regla**: escribir templates con UTF-8 (`[System.IO.File]::WriteAllText`) |
| Login redirigía a `/accounts/login/` | Faltaban `LOGIN_URL`/`LOGIN_REDIRECT_URL` | Setear ambos en settings |
| `django-environ` no instalado | settings lo importaba pero no estaba en el venv | Instalar la dependencia |
| `{% if %}` con paréntesis → TemplateSyntaxError | Django no soporta paréntesis para agrupar en `{% if %}` | Usar ifs anidados |

---

## Decisiones de diseño relevantes (para la sección "decisiones del trabajo")

1. **Feature-flag `MODO_FILTRO_CLIENTE`**: filtrado y paginado **client-side** en el navegador (feel de Angular Material, 0 round-trips a Neon, ideal para la demo) con switch a **server-side** en producción cambiando una variable de `.env` y reiniciando. Es el punto destacado del trabajo práctico.
2. **`is_superuser` como bypass global** de visibilidad (separado del `rol` de negocio y de `is_staff` para /admin/).
3. **Permisos por rol y por contexto**: Solicitante ve sus tickets; Desarrollador ve los de sus sistemas; comentar requiere ser creador/superuser/tomador y ticket no cerrado.
4. **`is_staff`/`is_superuser` desacoplados del `rol`**: `rol` es permiso de negocio (vistas); `is_staff`/`is_superuser` es acceso a `/admin/`.
5. **Paleta `brand` (#007AC3)** y **responsive obligatorio** en toda vista (normas en AGENTS.md).
6. **Adjuntos**: un solo input multiple (no formset) + descarga vía `FileResponse(as_attachment=True)` con visibilidad por rol.

---

## Pendientes conocidos (estado abierto) — MUY UTILES para la sección de "trabajo a futuro"

- ⚠️ **XSS (IMPORTANTE)**: `ticket_detail.html` renderiza `descripcion_original` y `cuerpo` con `|safe` (HTML de Quill) **sin sanitizar**. No desplegar a producción sin resolverlo (sanear con `bleach`/`nh3` al guardar o renderizar).
- Acceso desde red local (móvil/WiFi): `ALLOWED_HOSTS=[]` lo bloquea (probar con IP local).
- Migrar Tailwind a build compilado (reemplazar CDN).
- Activar `settings.HUEY` para la cola de tareas (Fase 2).
- HTMX partials para interacciones en detalle (hoy submit normal con redirect).
- `core/tests.py` pendiente (tests de vistas modo cliente + server + permisos por rol).

---

## Cómo se verificó el trabajo

- `manage.py check` sin issues; `makemigrations --check --dry-run` sin migraciones pendientes.
- **Test client de Django** (no ejecuta JS): creación con adjuntos múltiples, permisos de comentar (CERRADO → oculto + 403; dev no-tomador → oculto + 403; dev-tomador/creador → visible + 200), descarga de adjuntos.
- **Lógica client-side validada con Node + DOM mock** (45 tickets): paginación de a 20, última página parcial, disabled de botones, filtro que resetea y recalcula (PASS 9/9).
