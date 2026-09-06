# BITACORA — Interacción con el modelo (opencode)

> Documento para el trabajo práctico: registro cronológico de la construcción del sistema de tickets, con énfasis en **incidencias** (bugs / comportamientos inesperados) y **cómo se corrigieron**, mapeadas a commits y fechas.
> Fuentes: historial de `AGENTS.md` + `git log`. Fechas en formato AAAA-MM-DD.

---

## Contexto del proyecto (qué construimos)

- **Sistema de tickets** interno para gestión de bugs de las apps "Balances" y "Financiamiento".
- **Fase 1 (completa)**: tickets convencionales — login, listado, creación, detalle, comentarios, adjuntos, toma colaborativa, cambio de estado, admin de sistemas/accesos.
- **Fase 2 (parcial)**: capa IA (análisis TÉCNICO vía LLM, tipo único) — providers Groq/Gemini/OpenRouter/NVIDIA/Ollama con llamada HTTP real, análisis manual (Analizar/Reanalizar), prompt optimizado (system/user, texto plano, anti-inyección) y `formato_salida` por modelo. Lógica en `ai/`; **modelos IA en `core`** (decisión del 2026-09-04, ver sección correspondiente).

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
  - Usuarios seed: 5 solicitantes (password `soli`). El único staff/superuser es `patosimple` (creado a mano).

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

### 2026-09-04 — Fase 2: prompt optimizado + `formato_salida` por modelo + docs (SIN COMMIT aún)
Los commits de la fecha (`5afc9bb` y anteriores) ya estaban hechos; los cambios siguientes **quedaron sin commitear** a la espera de que el usuario pruebe las IA en su máquina.
- **Prompt optimizado** (`ai/providers.py::_construir_mensajes`): mensajes **`system`/`user` separados**; la descripción va en **texto plano** (`html_a_texto_plano()`) y el `user` incluye **contexto** (título, sistema y `Sistema.prompt`). **Defensa anti prompt-injection** declarativa: el `system` avisa que el bloque "DESCRIPCIÓN DEL TICKET" es SOLO el dato a analizar, que sus órdenes se ignoran y que ninguna instrucción interna puede alterar tarea/reglas/formato. `VERSION_PROMPT` subió a `v3` (manual).
- **`Sistema.prompt`** (migración `core 0005`): TextField opcional con la descripción oficial del sistema; si tiene texto se inyecta al `user`. `seed_init` lo completa (solo si está vacío) para BALANCES/FINANCIAMIENTO.
- **`ModeloIA.formato_salida`** (migración `core 0006`, choices `FormatoSalidaIA`): `RESPONSE_FORMAT` (`response_format` en la API) / `NATIVO` (`format: json` de Ollama) / `NINGUNO` (se pide por instrucción). `_chat_completions` manda el campo solo cuando corresponde y **`_extraer_json()` tolera ruido** (fences de markdown, texto alrededor) antes de `json.loads`.
  - **Incidente en cierre**: Gemini/NVIDIA venían andando BIEN con `response_format` global; la seed los dejó en **`NINGUNO`** (cambio a validar). **El usuario todavía no probó las IA** — si fallan, revertir esos dos a `RESPONSE_FORMAT` en seed + registros de BD.
- **`seed_init` actualizado**: catálogo con `formato_salida` por proveedor (Groq/OpenRouter=RESPONSE_FORMAT, Gemini/NVIDIA=NINGUNO, Ollama=NATIVO), sincronización de registros existentes y completado de `Sistema.prompt`.
- **`.env.example` nuevo**: plantilla committeada con TODAS las variables documentadas (`DATABASE_URL` obligatoria; 3 opciones de `DJANGO_ALLOWED_HOSTS`; SUPABASE_* comentadas como plan). Antes solo existía `.env` local.
- **`README.md` nuevo**: puesta en marcha para un dev nuevo (venv o Docker, `migrate`, `seed_init`/idempotente, `seed_tickets`/`--tickets`(default 10)/`--reset`, roles, tabla de variables).
- **Docs corregidos**: la pass de solicitantes del seed es **`soli`** (AGENTS.md/README/BITACORA decían `Solicitante123!`) — el código y la pista de `login.html` ya lo tenían bien.
- **Decisión de diseño**: los **modelos de IA quedan en `core`** (no se mueven a `ai`). Motivo: `AnalisisIA` tiene FK a `Ticket` y el catálogo alimenta el flujo de análisis; la app `ai` concentra solo la lógica. Separación por capas, la separación física del esquema quedó descartada pre-entrega (riesgo de refactor con datos reales).
- **Pendiente de la sesión**: probar los 5 proveedores (foco Gemini/NVIDIA con `NINGUNO`) en una máquina con las 4 API keys en `.env` + Ollama local; según resultado revertir o no, y **commitear** todo lo de arriba.

### 2026-09-04 — Bloqueo de tickets cerrados + UI header/sidebar (commits `0b854d1` y siguiente)
- **`0b854d1`** ticket cerrado inmodificable + solo colaboradores analizan + giro del icono Analizar (detalle completo en el mensaje del commit).
  - **Ticket CERRADO = inmodificable**: no se puede re-analizar IA (403), no se pueden agregar/editar/eliminar comentarios (403 + botones ocultos vía `puede_gestionar_comentarios`), se muestra "· Ticket cerrado (análisis inamovible)" en la tarjeta IA. Checklist de diseño aprobado por el usuario.
  - **Analizar IA restringido a colaboradores** (igual que comentar/editar): `puede_analizar` ahora usa `_es_participante_activo` + estado != CERRADO (`views.py:268`); `analizar_ticket` lanza 403 "Solo colaboradores activos del ticket pueden analizar". Un dev que no tomó el ticket ve la tarjeta pero sin botón Analizar.
  - **`README.claude.md`** incluido en el commit (archivo de configuración para Claude Code del usuario).
  - **Chevron de colapso de la tarjeta IA**: se movió FUERA del `if (formAnalizar)` (así funciona también en tickets cerrados, donde el form no existe) y la key de `localStorage` pasó a `analisis-colapsado-<pk>` (por ticket).
  - **Giro del icono del botón Analizar/Reanalizar**: `animate-spin` (horario) hacía que las flechas quedaran "de cola" (parecían girar hacia atrás). **Corrección**: keyframes propios `spin-reverse` (antihorario) en `extra_head` → `.animate-spin-reverse`.
- **UI header del detalle (pull de mini-botones)**: se eliminó la tarjeta blanca de acciones. Los botones pasaron a **mini-botones `px-2.5 py-1 text-xs` con color relleno** (Tomar/Reabrir=brand-600, **Cerrar=rojo**, **Liberar=gris oscuro**), ubicados **dentro de la tarjeta del ticket, en la fila del autor** (arriba a la derecha), solo si `puede_actuar`. Evolution en sesión: tarjeta propia → ghost en header → relleno en línea del título → dentro de la fila del autor.
- **Metadatos del detalle**: el `dl` (Sistema/Solicitante/Creado/Estado) desapareció. **Estado** → badge arriba a la derecha; **Sistema** → badge `bg-brand-950` uppercase en la línea del título (mismo color que la sidebar); **solicitante + fecha** → arriba del texto, estilo comentario: circulito de color por rol + nombre (bold) y fecha/hora en italic `text-xs` sin bold a continuación (alineación de baseline resuelta: se abandonó el flex `items-center` por texto inline con `align-middle` en el circulito).
- **Sidebar (base.html)**: el botón de colapsar quedó **solo ícono** (sin label "Colapsar"), **sin hover** (`hover:bg-brand-800` removido) y alineado con los íconos de los links (`px-3`; `justify-center px-0` al colapsar via JS). **Incidente (iconos saltaban al centro al colapsar/abrir)**: al colapsar, los íconos se re-centraban al instante mientras el ancho animaba. **Corrección**: se quitó el re-centrado (los íconos quedan SIEMPRE en posición izquierda, solo anima el ancho) + `whitespace-nowrap` en los textos (el wrap al abrir con sidebar angosta hacía saltar el ícono hacia abajo). **Apertura asimétrica**: al cerrar, el texto desaparece primero y luego anima el ancho; al abrir, primero anima y el texto aparece a los 200ms (`setTimeout` cancelable con `setSidebarTexts`).
- **Ícono de "Análisis IA"**: se probaron sparkles (izquierda/derecha), lamparita FA solid y robot FA solid; quedó **✨ sparkles (Heroicons outline)** a la derecha del título (`w-4 h-4`, brand-600/brand-400).

### 2026-09-06 — Detalle de ticket 100% HTMX + prompt v4 (título anti-inyección) + seed_init sincronizado (commits pendientes, 2 partes)
- **Detalle 100% HTMX** (nuevo partial `core/templates/core/partials/ticket_pagina.html`, wrapper `#ticket-pagina` con `hx-post` + `hx-target="#ticket-pagina"` + `hx-swap="outerHTML"` en tomar / liberar / cambiar estado / comentar / editar / eliminar). Cada vista de acción responde el partial si llega `HX-Request`; el detalle (non-HX) hace redirect normal. Helpers `_contexto_detalle()` y `_render_ticket_pagina()` en `core/views.py`; re-bind del JS client (Quill, bindings, Swal) en `htmx:afterSettle` vía `initPagina()`. **`TicketDetailHtmxTest`** en `core/tests.py` (6 tests; total **20 OK**). `MODO_FILTRO_CLIENTE` solo afecta al listado, no al detalle.
  - **Incidente (textarea "común" tras editar un comentario)**: HTMX copia transitoriamente `class/style` del nodo viejo al nuevo (**attribute settle**, `attributesToSettle=["class","style","width","height"]`) → el `#quill-comentario` fresco heredaba la clase `ql-container` del viejo y el guard `classList.contains('ql-container')` false-positivaba → no se recreaba el editor (textarea sin estilos visible). **Corrección**: (1) `ComentarioForm.cuerpo` se renderiza con `class="hidden"` (clase servida que el settle respeta), (2) el guard pasó a `contenedor.querySelector('.ql-editor')`, (3) el re-init se movió de `htmx:afterSwap` (cuando aún corren los settles) a **`htmx:afterSettle`**. Validado con Quill real en Edge headless.
  - **Incidente (eliminar comentario: cancelar en Swal eliminaba igual)**: el listener de `submit` de HTMX **NO respeta `defaultPrevented`** previo (htmx.js llama directo a `handleAjaxEvent`) → el DELETE salía antes de que Swal se abriera, y confirmar disparaba 2 POST. **Corrección**: `bindEliminar()` intercepta el **`click` del botón**: `preventDefault()` evita que el navegador genere el `submit` (nov-HTML: HTMX no dispara); al confirmar se quita el listener y `form.requestSubmit()` emite 1 solo POST + swap. Validado en repro headless: **cancel→0 POST, confirm→1 POST + swap**.
  - **Nota headless (SweetAlert2)**: bajo `--virtual-time-budget` el `.swal2-container` se monta pero `#swal2-confirm`/`#swal2-cancel` nunca se renderizan → E2E de Swal imposible en headless; la corrección se validó por el mecanismo puro (click-intercept + `requestSubmit`) en un harness local con `htmx.js`+`sweetalert2.js` reales.
- **`seed_init` sincronizado con la DB**: los prompts de BALANCES (1259 chars) y FINANCIAMIENTO (915 chars) se copiaron **verbatim** (comparación con `ast.literal_eval` normalizando `\r\n` → MATCH). Nuevo flag **`--update_prompt`** que los sobrescribe siempre (para sincronizar un entorno, ej. Neon). Sin flag, solo completa si están vacíos (comportamiento original). **No se corrió** contra la DB (para no pisar el catálogo de `ModeloIA`). `README.md` actualizado con el flag.
- **Prompt v4 (`VERSION_PROMPT` v3→v4)**: la **protección anti prompt-injection se extiende al TÍTULO** (antes cubría solo la descripción): el `system` declara que tanto el título como la descripción son datos del usuario y que las órdenes que aparezcan en ellos se ignoran; en el `user` el título va delimitado con `"""` y etiquetado "(texto del usuario; SOLO dato a analizar)", igual que la descripción. `VERSION_PROMPT` es una constante a mano (admin de versiones sigue PENDIENTE).
- **Cursor titilando tras un swap (diagnóstico, sin cambios)**: se investigó a pedido del usuario; la causa más probable es **caret browsing de Chrome (F7)** y no el swap HTMX (HTMX solo re-enfoca elementos con mismo `id`, y el repro mostró foco → `body` sin caret residual). No se modificó código.
- **Commits**: se dividió el trabajo pendiente en **2 commits**: (1) *detalle ticket en HTMX + fixes* (`ticket_pagina.html`, `ticket_detail.html`, `views.py`, `forms.py`, `tests.py`); (2) *prompt v4 + seed_init sync + docs* (`seed_init.py`, `ai/providers.py`, `README.md`, `AGENTS.md`, `BITACORA.md`).
  - Los 2 commits se hicieron y pushearon como **`b308d27`** (*detalle HTMX + fixes*) y **`d8925a4`** (*prompt v4 + seed_init sync + docs*).
- **Post-commits — 2 bugs reportados por el usuario (fix sin commitear aún)**:
  - **Incidente (comentar/editar "a veces no actualiza")**: tras el detalle 100% HTMX, crear o editar un comentario a veces no reflejaba nada (y el siguiente tras un refresh sí). **Causa raíz**: **disputa de orden de listeners `submit`**. En la carga inicial, el JS propio (fin del body) registra su listener de copia Quill→textarea ANTES de que htmx registre el suyo (htmx inicializa en `DOMContentLoaded`), por eso el primer commentario funcionaba. Tras cada swap, htmx procesa el form nuevo y registra su listener PRIMERO y el re-init nuestro corre recién en `htmx:afterSettle` → htmx serializa el form con el textarea **vacío** (la copia corría después) → POST con `cuerpo=` vacío → error de validación → nada cambiaba hasta recargar. **Corrección**: inyectar `cuerpo` y `archivos` en **`htmx:configRequest`** (corre DESPUÉS de serializar, ANTES de enviar, independiente del orden de inscripción). Se quitaron los listeners `submit` de copia/DataTransfer redundantes (un bloque de copia quedó duplicado por error al hacer la edición y se eliminó). **Detalle clave de htmx 1.9.10 (leído del source)**: `evt.detail.parameters` es un **objeto plano** (no FormData); htmx lo convierte a FormData al enviar vía `pr(n)` — un valor que sea **Array** se convierte en múltiples entries → los archivos se inyectan como `params['archivos'] = [f1, f2]` (no llamando a `params.append`). Validado con simulación en Node (4 casos: con/sin fix × carga-inicial/tras-swap → con fix ambos envían el cuerpo; sin fix el post-swap envía vacío) + validación de 2 archivos → 2 entries.
  - **Incidente (flash messages acumulados "etiquetas azules" arriba desde que se introdujo HTMX)**: `editar_comentario`/`eliminar_comentario` hacen `messages.success()`, pero las respuestas HTMX solo swapean `#ticket-pagina` y el bloque de mensajes vive en `base.html` → los mensajes quedaban **sin consumir en la sesión** y se apilaban hasta el próximo render completo. **Corrección**: nuevo partial **`core/templates/core/partials/mensajes.html`** (loop con el mismo estilo de base: rojo/ambar/brand) incluido en `base.html` (como hoy) y **al inicio de `ticket_pagina.html`** (dentro de `#ticket-pagina`), de modo que cada swap HTMX renderiza y CONSUME los mensajes.

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
| Textarea "común" (sin estilos) tras editar un comentario | Attribute settle de HTMX copia `class/style` del nodo viejo al nuevo (`attributesToSettle`) y el guard false-positivaba | textarea servido con `class="hidden"`, guard por `.ql-editor`, re-init en `htmx:afterSettle` |
| Cancelar en Swal igual eliminaba el comentario | HTMX ignora `defaultPrevented` en el listener de `submit` (llama a `handleAjaxEvent` directo) | Interceptar el `click` del botón (`preventDefault` evita el submit) + `form.requestSubmit()` al confirmar |
| Comentar/editar "a veces no actualiza" (tras HTMX) | Orden de listeners `submit`: tras un swap, htmx serializa el form (con el textarea vacío) ANTES de que corra nuestra copia Quill→textarea (que se re-registra en `afterSettle`) | Inyectar `cuerpo` y `archivos` en `htmx:configRequest` (corre tras serializar, antes de enviar; independiente del orden) |
| Flash messages acumulados ("etiquetas azules" arriba) | `messages.success()` de editar/eliminar comentario nunca se renderiza en las respuestas HTMX (target = `#ticket-pagina`), quedan sin consumir en sesión | Partial `mensajes.html` incluido en `base.html` y en `ticket_pagina.html` (cada swap renderiza y consume) |

---

## Decisiones de diseño relevantes (para la sección "decisiones del trabajo")

1. **Feature-flag `MODO_FILTRO_CLIENTE`**: filtrado y paginado **client-side** en el navegador (feel de Angular Material, 0 round-trips a Neon, ideal para la demo) con switch a **server-side** en producción cambiando una variable de `.env` y reiniciando. Es el punto destacado del trabajo práctico.
2. **`is_superuser` como bypass global** de visibilidad (separado del `rol` de negocio y de `is_staff` para /admin/).
3. **Permisos por rol y por contexto**: Solicitante ve sus tickets; Desarrollador ve los de sus sistemas; comentar requiere ser creador/superuser/tomador y ticket no cerrado.
4. **`is_staff`/`is_superuser` desacoplados del `rol`**: `rol` es permiso de negocio (vistas); `is_staff`/`is_superuser` es acceso a `/admin/`.
5. **Paleta `brand` (#007AC3)** y **responsive obligatorio** en toda vista (normas en AGENTS.md).
6. **Adjuntos**: un solo input multiple (no formset) + descarga vía `FileResponse(as_attachment=True)` con visibilidad por rol.
7. **Prompt IA optimizado**: `system`/`user` separados, descripción en texto plano, contexto de sistema (`Sistema.prompt`), defensa anti prompt-injection declarativa en el `system`.
8. **`formato_salida` por modelo**: cada proveedor define cómo pedir el JSON (`response_format` / `format: json` / instrucción) en lugar de una constante global idéntica para todos.
9. **Modelos IA en `core`** (no en `ai`): separación por capas — `ai` es solo lógica; el esquema (con `AnalisisIA.ticket` FK a `Ticket`) vive con el dominio. Refactor futuro post-entrega si se busca autocontención total de la app `ai`.

---

## Pendientes conocidos (estado abierto) — MUY UTILES para la sección de "trabajo a futuro"

- ~~**XSS (IMPORTANTE)**~~ **RESUELTO** con `nh3.clean()` al guardar (`TicketForm`/`ComentarioForm`, whitelist de tags/atributos Quill), verificado con vectores reales. Pendiente: tests automatizados de XSS en `core/tests.py`.
- Acceso desde red local (móvil/WiFi): `ALLOWED_HOSTS=[]` lo bloquea (probar con IP local en `DJANGO_ALLOWED_HOSTS`).
- Migrar Tailwind a build compilado (reemplazar CDN).
- Cola real de tareas: `settings.HUEY` YA está configurado con `immediate=True` (síncrono, demo). Para cola async: `AI_IMMEDIATE=False` en `.env` + worker `manage.py run_huey`.
- ✅ **HTMX partials para interacciones en detalle** — resuelto 2026-09-06 con `partials/ticket_pagina.html` (ver sección de ese día).
- `core/tests.py` pendiente (tests de vistas modo cliente + server + permisos por rol + XSS).
- **Fase 2 pendiente**: auto-análisis al crear ticket, rotación de modelos/API keys, admin de versiones de prompt (`VERSION_PROMPT` sigue manual), mostrar `informacion_faltante`, flujo de aprobación del análisis por el solicitante, límite de tamaño de adjuntos + subidas pesadas sin progreso, adjuntos efímeros en Render (Supabase Storage pendiente).
- **AUDITORÍA IA (04-09, pendiente)**: probar Groq/Gemini/OpenRouter/NVIDIA/Ollama; si Gemini/NVIDIA fallan con `NINGUNO`, revertir a `RESPONSE_FORMAT` en seed + BD.

---

## Cómo se verificó el trabajo

- `manage.py check` sin issues; `makemigrations --check --dry-run` sin migraciones pendientes.
- **Test client de Django** (no ejecuta JS): creación con adjuntos múltiples, permisos de comentar (CERRADO → oculto + 403; dev no-tomador → oculto + 403; dev-tomador/creador → visible + 200), descarga de adjuntos.
- **Lógica client-side validada con Node + DOM mock** (45 tickets): paginación de a 20, última página parcial, disabled de botones, filtro que resetea y recalcula (PASS 9/9).
- **Fase 2 (04-09)**: `manage.py check` OK; migraciones `0005`/`0006` aplicadas y `seed_init` corrido; `html_a_texto_plano()`, `_extraer_json()` (con fences markdown y ruido), roles de mensajes y payloads RESPONSE_FORMAT/NINGUNO/NATIVO probados vía shell. **NO** corren pruebas E2E contra las APIs reales (sin keys en `.env` local → 401); queda la auditoría de proveedores pendiente en la máquina del usuario.
- **Fase detalle HTMX (06-09)**: `manage.py check` OK; **20 tests OK** (`TicketDetailHtmxTest` + suite previa); `node --check` del JS del detalle OK; repros de las 2 incidencias (attribute settle del textarea y eliminar/cancelar de Swal) validados en **Edge headless** con `htmx.js`/`quill.js`/`sweetalert2.js` reales (cancel→0 POST, confirm→1 POST + swap); prompts de `seed_init` verificados contra DB con `ast.literal_eval` (MATCH); `py_compile` + `manage.py seed_init --help` del flag `--update_prompt`; prompt v4 regenerado y revisado.
- **Post-commits (2 bugs)**: `node --check` del JS OK; `manage.py check` OK; **20 tests OK**; simulación en Node del orden de serialización de htmx (sin fix: post-swap envía `cuerpo` vacío [bug reproducido]; con fix: envía el HTML en AMBOS órdenes) + validación de que `params['archivos']=[f1,f2]` (objeto plano de htmx 1.9.10) produce 2 entries al convertir a FormData; lectura del source de htmx.js 1.9.10 para confirmar el flujo `parameters`(objeto plano) → `pr()`(FormData) → `send`.
