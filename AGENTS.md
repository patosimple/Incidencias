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
- ✅ `core/urls.py` y `config/urls.py`: listado, creacion, detalle, tomar ticket, cambiar estado, comentar, **login/logout + cambiar-password** (`auth_views` + `CambiarPasswordView`)
- ✅ `config/settings.py`: `LOGIN_URL='login'`, `LOGIN_REDIRECT_URL='ticket_list'` (sin esto, anon iba a `/accounts/login/` que no existe)
- ✅ `core/forms.py`: `TicketForm`, `ComentarioForm`, **`CambioPasswordForm`** (labels espanol + estilos Tailwind/dark en inputs). ~~`AdjuntoForm`/`AdjuntoFormSet`~~ **ELIMINADOS** — ya no hay formset; los adjuntos se suben con un único `<input type="file" name="archivos" multiple>` manejado con `request.FILES.getlist("archivos")` en `core/views.py`)
- ✅ `core/views.py`: `TicketListView`, `TicketCreateView`, `TicketDetailView`, `tomar_ticket`, `cambiar_estado_ticket`, `agregar_comentario` (permisos por rol aplicados) + **`CambiarPasswordView`** (`LoginRequiredMixin` + `PasswordChangeView`, success_url a `ticket_list` con mensaje flash)
- ✅ `core/management/commands/seed_init.py`: seed base aplicado (Sistemas: BALANCES, FINANCIAMIENTO; ModeloIA: Groq/Gemini/OpenRouter; ConfiguracionIA activa: Groq)
- ✅ `core/management/commands/seed_tickets.py`: seed demo (5 solicitantes espanol + N tickets lorem, contables). **Password de los solicitantes: `Solicitante123!`** (usuarios: maria.lopez, carlos.gonzalez, lucia.fernandez, joaquin.rodriguez, valentina.martinez — todos con acceso a BALANCES + FINANCIAMIENTO)
- ✅ `core/templates/core/base.html`: layout general responsive (sidebar desktop colapsable a iconos + off-canvas movil), Tailwind CDN + HTMX, **dark mode con toggle sol/luna**, **paleta de marca `brand` (base #007AC3)** en `tailwind.config` inline, `{% block extra_js %}` al final, **menu desplegable de usuario en el avatar** (nombre, email, rol, Administración, Cambiar contraseña, Salir; cierra con click afuera/Escape). El badge flotante de breakpoint fue ELIMINADO
- ✅ `core/templates/core/login.html` (nuevo): pantalla de login que hereda el shell de base (dark mode + paleta brand), error en español ("Usuario o contraseña incorrectos."), pista de password demo
- ✅ `core/templates/core/password_change.html` (nuevo): cambio de password (card responsive, hereda shell, dark ready)
- ✅ `core/templates/core/partials/rol_badge.html` (nuevo): badge de rol reutilizable (Solicitante=brand-600, Desarrollador=emerald-600, Coordinador=purple-600). **HOY SIN USO** (se reemplazó por la barra vertical de color en el menu de usuario)
- ✅ `core/templates/core/ticket_list.html`: tabla con **filtrado client-side switcheable** (ver PLAN abajo) + **paginacion client-side de a 20 estilo Angular Material**, badges de estado, empty state, clases `dark:` aplicadas
- ✅ `core/templates/core/partials/ticket_table.html`: partial (tabla `md+` / cards movil + barra inferior con contador y paginador), target `#tabla-tickets`, cada `<tr>`/`<li>` con `data-ticket-id` (unico para contar/paginar), `data-sistema`/`data-estado`
- ✅ `core/templates/core/partials/estado_badge.html` (nuevo): badge de estado reutilizable (`{% include ... with estado=ticket.estado %}`)
- ✅ `TicketListView.get_template_names()`: devuelve partial si `HX-Request` header presente
- ✅ `TicketListView.get_queryset()`: superuser ve todos los tickets sin filtro de rol/sistema; en modo cliente aplica SOLO visibilidad por rol + `get_paginate_by()` devuelve `None` (trae todo; filtrado/paginacion en navegador); en modo server filtra/pagina (20)
- ✅ **Bug filtro de sistemas resuelto**: `get_context_data()` — superuser ve `Sistema.objects.all()` en el dropdown (consistente con bypass de `get_queryset`); no-superuser ve `_sistemas_visibles()`
- ✅ `core/context_processors.py` (nuevo): expone `MODO_FILTRO_CLIENTE` en todos los templates (leído de settings)
- ✅ **Admin**: `UsuarioSistemaInline` (tabular) dentro de `UsuarioAdmin` para asignar sistemas desde el form del usuario. Duplicados los valida el formset nativo antes de guardar (con `unique_together` de BD como respaldo). **Alta de usuario con TODOS los campos (igual que editar)**: nuevo `UsuarioCreationForm` en `core/forms.py` (hereda `UserCreationForm`; `Meta.fields` incluye `username, rol, first_name, last_name, email, is_staff, is_active, is_superuser, groups, user_permissions` — se **excluyen** los automáticos `password` (modelo)/`date_joined`/`last_login` que con `fields='__all__'` rompían el guardado con `KeyError`/errores). En `core/admin.py`: `add_form = UsuarioCreationForm` + `add_fieldsets` (None→username/password1/password2, "Rol de negocio", "Información personal", "Permisos"). El campo `rol` se genera **desde el modelo** (como en editar): **opción vacía `-----` por defecto + obligatorio** (`initial=None`; guardar sin rol → "Este campo es obligatorio."; NOTA: NO redefinir `rol` como `ChoiceField` custom — `ChoiceField` no acepta `empty_value` y al redefinirlo arrancaba en el primer choice (SOLICITANTE) en vez del `-----`). `password1`/`password2` se ocultan con puntitos (comportamiento normal del admin). Verificado: render `/admin/core/usuario/add/` 200 con todos los campos + inline, guardar sin rol falla, con rol crea. Editar user: intacto (UserAdmin default + `fieldsets` con rol).
- ✅ **Flag desde .env**: `MODO_FILTRO_CLIENTE` = `env.bool(...)` en `settings.py`, default `True`. Definido en `.env`. Debounce 200ms client y server
- ✅ **Responsive shell implementado** (CDN): sidebar desktop colapsable a iconos (`localStorage 'sidebar'`), off-canvas movil con overlay, header compacto, tabla↔cards en listados (`estado_badge.html` extraido), `<main>` padding responsive — ver seccion **Responsive** abajo
- ✅ `core/templates/core/ticket_form.html` (nuevo): form de nuevo ticket (max-w-2xl, hereda shell, dark + brand, errores por campo, botones Cancelar/Crear; JS en `extra_js` aplica clases CSS a inputs/selects/textarea del form)
- ✅ `core/templates/core/ticket_detail.html` (nuevo): detalle (header con estado, `dl` de metadatos, descripción `linebreaksbr`, colaboradores vía `ticket.ticketdesarrollador_set`, acciones tomar/cambiar-estado, comentarios con form, adjuntos). Hereda shell, dark + brand
- ✅ **Logout arreglado**: el enlace "Salir" en `base.html` era `<a href>` (GET) pero `LogoutView` solo acepta POST → daba 405 y no cerraba sesión. Cambiado a `<form method="post">` con CSRF. La ruta `logout/` ya existía en `config/urls.py:10` (`auth_views.LogoutView(next_page="login")`)
- ✅ **Bug bypass superuser en detalle resuelto**: `TicketDetailView.get_queryset()` NO tenía el bypass `is_superuser` que sí tiene el listado → un superuser con rol DESARROLLADOR y sin sistemas visibles recibía 404 en todos los tickets. Ahora `is_superuser` ve cualquier ticket (consistente con `TicketListView`)
- ✅ Pendiente: HTMX partials para interacciones en detalle (tomar ticket, cambiar estado, comentar) — por ahora los forms del detalle hacen submit normal (redirect)
- ✅ **Transiciones de estado por botones (sin select)**: `tomar_ticket` pasa PENDIENTE/REABIERTO → EN_PROCESO y guarda el estado previo en `Ticket.estado_previo`; **`liberar_ticket`**: un dev/coor marca su `TicketDesarrollador.activo=False` (conservando histórico); si era el último colaborador activo, el ticket vuelve a `estado_previo` (PENDIENTE o REABIERTO) y lo limpia. **`cambiar_estado_ticket` (generalizado por rol)**: **cualquier estado abierto (EN_PROCESO/PENDIENTE/REABIERTO) → CERRADO** y **CERRADO → REABIERTO** lo pueden realizar el **dueño (solicitante), desarrollador o coordinador** (`_puede_cerrar`/`_puede_reabrir` en el context + verificación server-side en `cambiar_estado_ticket`). **Regla clave**: si un **desarrollador** reabre un CERRADO y **no era colaborador**, queda como **colaborador activo** (se auto-toma, `TicketDesarrollador.get_or_create` + `activo=True`; el ticket queda REABIERTO, NO se fuerza a EN_PROCESO). Un solicitante que no es dueño del ticket: ni lo ve (404 por visibilidad del detalle) ni puede cerrar/reabrir (403). Al cerrar limpia `cerrado_en`/`estado_previo`; al reabrir resetea `cerrado_en`. Modelo: `Ticket.estado_previo` + `TicketDesarrollador.activo` (migración `0003`). En el detalle la tarjeta de acciones (`ticket_detail.html`) muestra según estado: **CERRADO** → botón **Reabrir** (`puede_reabrir`); estados abiertos → **Tomar ticket** (dev que NO colabora activamente), **Cerrar** (`puede_cerrar`), **Liberar** (`puede_liberar`, colaborador activo). La sección Colaboradores tacha/marca "Liberado" a los `activo=False`. Colores de estado (`estado_badge.html`): PENDIENTE=rojo, EN_PROCESO=verde, CERRADO=gris oscuro, **REABIERTO=texto siempre "Reabierto", color verde (emerald) si "tomado" (≥1 colaborador activo) o rojo si "sin tomar"** (visual, no cambia la lógica de estado)
- ✅ **Crear ticket select de sistemas**: `TicketForm` deja de filtrar sistemas para superuser (ve todos, mismo bypass que listado/detalle)
- ✅ **Branding/home**: `config/urls.py` home con `name="home"`; "Reporte de Incidencias" (header) y los logos de sidebar (desktop + drawer móvil) ahora son links a home. `base.html`
- ✅ **Texto enriquecido con Quill** (CDN `quill@2.0.2`): editor en crear ticket (`descripcion_original`) y en comentarios (`cuerpo`). Se renderiza con `|safe` en detalle. Seguro: sanitizado con `nh3` al guardar (ver **XSS RESUELTO** abajo)
- ✅ **Adjuntos (subir + descargar, sin visualizar)**: `MEDIA_URL`/`MEDIA_ROOT` en settings; media servido en DEBUG; `core/urls.py` ruta `adjuntos/<pk>/descargar/` → `descargar_adjunto` (FileResponse `as_attachment=True`, con visibilidad por rol); tipo se deduce por extensión vía `_tipo_por_nombre`; `Adjunto.clean()` permite FK vacía al subir (se asigna al guardar; el CHECK de BD exige exactamente uno). **Un único `<input type="file" name="archivos" multiple>`** (crear ticket y comentarios), manejado con `request.FILES.getlist("archivos")` → `_guardar_adjuntos(...)` en `core/views.py` (crea un `Adjunto` por archivo). En crear ticket y comentario nuevo, cada archivo pendiente (no subido) lleva una **X para quitarlo** antes del submit (JS: lista acumulada + DataTransfer reconstruido). **Editar comentario** ahora permite **agregar archivos nuevos Y quitar los existentes**: el form de edición tiene `enctype="multipart/form-data"`, input `archivos` + botón adjuntar, la lista de adjuntos existentes con X que los marca en un hidden `adjuntos_eliminar` (pks separados por coma, los tacha), y `editar_comentario` procesa `request.FILES.getlist("archivos")` (nuevos) + `_eliminar_adjuntos(...)` (existentes marcados → borra registro Y archivo físico vía `adj.archivo.delete(save=False)`). El detalle lista adjuntos del ticket y de cada comentario como links de descarga. El editor Quill usa un `<div>` contenedor (#quill-xxx) y el textarea se oculta (`style.display='none'`), no se pasa el textarea a `new Quill` (evita el bug de "barra de herramientas sin area de escritura"); en submit se copia `quill.root.innerHTML` al textarea
- ✅ **Permisos de comentar** (`_puede_comentar` en views): `False` si el ticket está CERRADO; `True` SOLO para el creador (`solicitante_id`) y los desarrolladores que tomaron el ticket (`ticket.desarrolladores`). **Sin bypass para superuser** (queda sujeto a las mismas reglas). El form de comentario se oculta con `{% if puede_comentar %}` y `agregar_comentario` lanza `PermissionDenied` (403) si no aplica. La sección "Colaboradores" siempre visible en el detalle lista quiénes tomaron el ticket (`ticket.ticketdesarrollador_set`)
- ✅ **XSS RESUELTO (mitigado con nh3)**: `_sanear_html()` en `core/forms.py` usa `nh3.clean()` con whitelist (`_QUILL_TAGS`/`_QUILL_ATTRIBUTES`). Se aplica en `ComentarioForm.clean_cuerpo()` y `TicketForm.clean_descripcion_original()` **al guardar**. El render con `|safe` es seguro porque el input ya fue saneado antes de persistir. **Verificado** con vectores reales (POST HTTP directo, sin Quill): `<script>`, `<img onerror>`, `<a href="javascript:">`, `<svg onload>` → todos neutralizados (eliminados o evento/URL peligrosa quitados). NINGÚN `<script>` llega a la BD. Nota: si se escribe literal `<b>hola</b><script>` como TEXTO en Quill, Quill lo escapa (se guarda `&lt;b&gt;...`) y se muestra como texto plano — comportamiento esperado del editor, no un vector de ataque. `nh3` es paquete del venv (no del Python global). Para producción opcional: añadir tests automatizados de XSS en `core/tests.py` (hoy PENDIENTE)
- ⚠️ **PENDIENTE IMPORTANTE — Subidas pesadas sin progreso**: hoy la subida de adjuntos es un **POST síncrono** del form: el navegador espera sin feedback (solo spinner nativo) y `FILE_UPLOAD_MAX_MEMORY_SIZE` es 2.5MB (memoria!). Un adjunto pesado puede colgar la request, superar el timeout de Gunicorn (30s default) y fallar opaco. **PLAN (mediano)**: subida vía **XMLHttpRequest** (`xhr.upload.onprogress` → barra de progreso; `xhr.abort()` → cancelar), con límite de tamaño por usuario y validación de tipo. Alternativa: subida fragmentada/resumible (chunks) o directo a object storage (S3/R2 presigned). Mientras tanto, validar tamaño en `_guardar_adjuntos` (rechazar > N MB) para no romper la demo
- ❌ Pendiente: **definir tamaño máximo de adjunto** (mismo tema del punto anterior): definir un límite (p.ej. N MB) y rechazar en `_guardar_adjuntos` con mensaje claro al usuario (hoy no hay límite: un archivo gigante llena `MEDIA_ROOT` y puede tumbar el server)
- ❌ Pendiente: **adjuntos en producción (MEDIA_ROOT local)**: los adjuntos se guardan en `media/adjuntos/AAAA/MM/` (disco local de `MEDIA_ROOT`). En Render/Neon el disco es **ephemeral** (se pierde en redeploy; el backup de la DB no los incluye) y no escala a N instancias. Para producción real: `django-storages` + S3/R2, o volumen persistente. **Configuración condicional por entorno en `settings.py`** (el modelo no cambia; el FileField escribe al bucket en vez del disco):
  ```python
  if DEBUG:   # desarrollo local
      STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}}
  else:       # producción (Render)
      STORAGES = {"default": {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": {"bucket_name": env("S3_BUCKET"), ...}}}
  ```
- ✅ **Editar/eliminar comentarios (solo autor + participante activo)**: `Comentario.modificado_en` (NULL hasta la 1ra edición, se setea con `timezone.now()` al guardar la edición) y **`eliminado_en` (soft delete, migración `0004`)**: eliminar = `comentario.soft_delete()` (setea `eliminado_en`, NO `delete()` físico; el registro y sus adjuntos se conservan). `Comentario.objects` (default manager) oculta los `eliminado_en__isnull=False` → el detalle/count y `get_object_or_404` no los ven; **`Comentario.all_objects`** los ve (usado en `ComentarioAdmin` para ver el histórico). Vistas `editar_comentario` y `eliminar_comentario` en `core/views.py` (ambas lanzan `PermissionDenied` si `comentario.usuario != request.user` O si el autor ya no participa activamente — `_es_participante_activo`: dueño o colaborador activo, un dev liberado pierde editar/eliminar; eliminar solo POST con **SweetAlert2** (CDN `sweetalert2@11`) en vez del `confirm()` nativo). Rutas `comentarios/<pk>/editar/` y `comentarios/<pk>/eliminar/` en `core/urls.py`. En `ticket_detail.html`: botones de **icono lápiz** (Editar) / **cesto** (Eliminar) visibles SOLO para el autor Y si `puede_gestionar_comentarios` (`{% if user.is_authenticated and comentario.usuario == user and puede_gestionar_comentarios %}`), indicador `· editado <fecha>` junto a la fecha cuando `modificado_en`, y form inline de edición con editor Quill (toggle client-side, inicializa con el contenido previo vía `quill.clipboard.dangerouslyPasteHTML`, al submit copia `quill.root.innerHTML` al textarea) + manejo de adjuntos (ver sección "Adjuntos" más arriba). **Verificado** con test client: autor activo edita/elimina OK (incluyendo agregar adjunto nuevo + borrar uno existente con su archivo físico), dev liberado recibe 403 y no ve los botones, no-autor recibe 403 y no modifica. Nota: este flow usa submit normal (redirect), igual que los forms del detalle. ~Editar conserva los adjuntos del comentario~ (ya NO: puede quitarlos).
- ✅ **Regla de toma + `_puede_actuar` generalizado**: escenario PENDIENTE → tomar → cerrar → reabrir. Un dev que ya es colaborador activo (lo tiene tomado) **NO vuelve a "tomar"** y **NO ve el botón Tomar** (sería contradictorio con que aparece también Liberar). `_puede_actuar` (hoy): el usuario ve la tarjeta de acciones si tiene rol de gestión — dev/coor siempre, o es el dueño (`solicitante_id`) — en cualquier estado (cerrar, reabrir, tomar/liberar). Un solicitante que no es dueño no la ve. El botón **Tomar ticket** solo aparece para un dev que NO colabora activamente; en REABIERTO/EN_PROCESO/PENDIENTE el dev que ya colabora activamente ve Cerrar + Liberar (no Tomar). Verificado con test client (dueño/dev/coor cierran desde cualquier estado abierto; dev/coor/dueño reabren; dev no-colaborador que reabre queda como colaborador activo; solicitante no dueño → 404/403).
- ✅ **Filtro "tomado" en el listado (solo desarrolladores, relativo al logueado)**: select `tomado` visible SOLO si `rol == DESARROLLADOR` (`ctx["es_desarrollador"]` en `get_context_data`), con opciones **Tomados por mí / Tomados por otros / Sin tomar / Todos** (default Todos). "Tomado" = ticket con ≥1 colaborador activo (`TicketDesarrollador.activo=True`), y "por mí" depende de si el usuario logueado es ese colaborador. **Server-side** (`get_queryset`, solo dev): `por_mi` → el usuario es colaborador activo; `por_otros` → tomado pero NO por el usuario; `sin_tomar` → sin colaborador activo (usa `filter`/`exclude` + `.distinct()` por las joins). **Client-side**: cada `<tr>`/`<li>` lleva `data-tomado` (global, ¿tiene colab activo?) y `data-tomado-mi` (¿el logueado es ese colab?); se computan en `get_context_data` como atributos `t.tomado` y `t.tomado_mi` (sobre el `Prefetch colabs_activos`). El JS filtra: `por_mi`→tomadoMi=1; `por_otros`→tomado=1 && tomadoMi!=1; `sin_tomar`→tomado=0. El HTMX server (`change from:select`) y el "Limpiar" consideran `request.GET.tomado`. Verificado con test client en ambos modos. NO afecta a solicitantes (sin select) ni cambia la visibilidad por rol.
- ❌ Pendiente: **citar/responder un comentario anterior** (botón "Responder" en cada comentario → pre-carga el editor con referencia/cita al comentario original, tipo quote/reply). Definir modelo de datos (¿campo `Comentario.responde_a` FK a otro comentario, o solo cita en el texto?) y render
- ❌ Pendiente: **resaltar tickets "no vistos" / con actividad nueva en el listado** (badge/estilo de "no leído"): que en la pantalla de tickets se destaque los que el usuario todavía NO vio, o los vistos pero que tuvieron un **comentario nuevo** o un **cambio de estado** desde la última visita del usuario. Ideas de diseño (sin implementar): nuevo modelo p.ej. `LecturaTicket` (usuario FK + ticket FK + `ultima_lectura_en`) con `unique_together(usuario, ticket)` y `related_name` en Usuario; al abrir un ticket se upserta la lectura (vía vista del detalle, no en el render del listado). Un ticket se marca "con novedades" si `creado_en > ultima_lectura_en` (no visto) o si el comentario/estado más reciente (`Comentario.creado_en` máximo o `creado_en`/`modificado_en`/`cerrado_en` del ticket) es posterior a `ultima_lectura_en`. En el listado (modo cliente `ticket_table.html` + modo server `get_queryset`), computar por ticket si hay novedad para `request.user` y aplicar un badge/acento (estilo brand) + opcional contador de comentarios nuevos. Definir si el "marcar como leído" al abrir aplica a todos los roles (solicitante, dev, coord) o solo a quienes participan (dueño + colaboradores activos). Consideración: evitar exponer `ultima_lectura` del otro; el resaltado es por-usuario.

- ❌ Pendiente: **editar cuerpo de tickets** (`descripcion_original`): hoy solo se crea el ticket y no se edita. Definir quién puede editar (¿el dueño? ¿colaboradores activos? ¿solo en ciertos estados?), si queda histórico de ediciones y UX (botón lápiz en el detalle + editor Quill como el de comentarios)
- ❌ Pendiente: acceso desde la red local (movil en la misma WiFi): `ALLOWED_HOSTS=[]` en `settings.py` bloquea. Para probar en local: agregar la IP local al `ALLOWED_HOSTS` (o `['*']` en dev) + `runserver 0.0.0.0:8000` + permitir puerto 8000 en firewall de Windows
- ❌ Pendiente: migrar Tailwind a build compilado
- ❌ Pendiente: `settings.HUEY` para activar cola de tareas

## Modelo de datos (no modificar sin confirmar)
| Modelo | Clave |
|--------|-------|
| `Usuario` | Extiende `AbstractUser`, campo `rol` (SOLICITANTE/DESARROLLADOR/COORDINADOR) |
| `Sistema` | Catalogo (Balances, Financiamiento) |
| `UsuarioSistema` | M2M usuario-sistema (accesos) |
| `Ticket` | titulo, sistema, solicitante, descripcion_original, estado, `estado_previo` (previo a sesión EN_PROCESO, para restaurar al liberar), desarrolladores (M2M through `TicketDesarrollador`) |
| `Comentario` | ticket, usuario, cuerpo, `modificado_en` (NULL hasta editar), `eliminado_en` (soft delete; `objects` oculta los borrados, `all_objects` los ve) |
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

## Responsive (NORMA OBLIGATORIA) — convenciones de layout
> **Regla**: TODA vista/template nueva debe ser responsive y heredar el shell de `base.html`. Los templates pendientes (`ticket_form.html`, `ticket_detail.html`) DEBEN cumplir estas normas.
- **Sidebar desktop**: `#sidebar-desktop` se muestra desde `md+` (`hidden md:flex`). Es **colapsable a solo iconos** (`w-56` ⇄ `w-16`) con el botón `#sidebar-desktop-toggle`. El estado manual se guarda en `localStorage` (`sidebar` = `'wide'`/`'collapsed'`). **Auto-comportamiento por breakpoint** (JS `applySidebarByBreakpoint()` en `resize` + al cargar): en `md` (768–1023) arranca SIEMPRE colapsado a iconos (expandible a mano pero re-colapsa al entrar en md); en `lg+` (≥1024) respeta la preferencia guardada (o wide por defecto). Los links usan `title` (tooltip nativo) que sirve cuando está colapsado.
- **Sidebar movil**: off-canvas drawer (`#sidebar-mobile`, `md:hidden`) con overlay oscuro. Se abre con la hamburguesa `#sidebar-mobile-toggle` (en el header, `md:hidden`) y se cierra al clickear el overlay o el `tilde`. Replicar los items de la sidebar desktop como `{% block nav_mobile_*_active %}` separados para marcar el activo en el drawer.
- **Header**: el email se esconde en `hidden md:block`, el badge de rol en `hidden sm:inline`, padding `px-3 sm:px-6`.
- **Tabla ↔ cards (listados)**: doble render en `#tabla-tickets`. Tabla `hidden md:table`, cards `md:hidden` (`<ul>`). AMBOS llevan `data-ticket-id` (unico por ticket), `data-sistema`/`data-estado` y el titulo con clase `font-medium`. El JS client-side agrupa los nodos por `data-ticket-id` (cada ticket aparece 2 veces: tr + li) para filtrar/paginar sobre tickets unicos.
- `<main>` usa padding responsive `p-4 sm:p-6`.
- **Custom components del CDN**: las variantes responsive (sm/md/lg) funcionan con el CDN actual y se conservan al migrar al build compilado (django-tailwind), porque las clases estan escritas estaticas en los templates. Nunca generar clases dinamicas por string en JS (el compilador no las detectaria).

## Paleta de marca (brand) — base #007AC3 (NORMA OBLIGATORIA)
> **Regla**: TODOS los templates (listos y futuros: `ticket_form.html`, `ticket_detail.html`, `login.html`) usan la paleta custom `brand` definida en `tailwind.config` de `base.html`. No usar otros azules/teal.
- Escala completa: `50 #E8F5FE`, `100 #D3EBFD`, `200 #A6D6FA`, `300 #70BCF0`, `400 #3FA0E4`, `500 #1488D3`, **`600 #007AC3` (base)**, `700 #00639E`, `800 #005080`, `900 #003E63`, `950 #00304F`.
- **Jerarquia de superficies**: header `bg-brand-800`, botones/acciones principales `bg-brand-600 hover:brand-700`, sidebar/drawer `bg-brand-950`, bordes de sidebar `brand-800`, hover/activo de nav `brand-800`, avatar `brand-500`, subtitulo sidebar `brand-300`.
- **Links en modo light**: `text-brand-700 hover:text-brand-900` (NO `brand-400`, contrasta mal sobre fondo claro), con `dark:text-brand-400 dark:hover:text-brand-300`. Ejemplo: titulo del ticket en `partials/ticket_table.html`.
- **Badge de rol texto/claro y elementos dark**: ver `base.html` (header `bg-brand-800` siempre, sin variante dark).
- Form en `ticket_list.html:` focus rings `focus:ring-brand-500`.
- **Al migrar a build compilado (django-tailwind)**: portar la escala `brand` exacta al `tailwind.config` del build. Los valores arbitrarios `bg-[#...]` solo se usan si no existe el escalon (evitar; preferir un escalon de la escala).

## Archivos clave
```
config/
  settings.py      # DB via env('DATABASE_URL'), AUTH_USER_MODEL="core.Usuario"
  urls.py          # Solo admin por ahora
core/
  models.py        # Modelos completos (258 lineas)
  admin.py         # Admin completo con inlines (UsuarioSistemaInline en UsuarioAdmin)
  views.py         # CBVs/FBVs con permisos por rol + bypass superuser + get_template_names HTMX + modo cliente/server
  forms.py         # TicketForm, ComentarioForm, CambioPasswordForm
  context_processors.py  # Expone MODO_FILTRO_CLIENTE a templates
  urls.py          # Rutas app (listado, creacion, detalle, acciones, cambiar-password, login/logout)
  management/commands/seed_init.py     # Carga sistemas y ModeloIA
  management/commands/seed_tickets.py  # Seed demo: solicitantes + tickets lorem
  templates/core/
    base.html                        # Layout con Tailwind CDN + HTMX 1.9.10 + dark mode + paleta brand + menu usuario
    login.html                       # Login (hereda shell, error espanol)
    password_change.html             # Cambio de password
    ticket_list.html                 # Lista con filtros client-side switcheable + JS + include partial
    ticket_form.html                 # Form de nuevo ticket (heredar shell + brand + dark)
    ticket_detail.html               # Detalle: metadatos, acciones, comentarios, adjuntos
    partials/ticket_table.html       # Partial: tabla + cards + paginacion (target #tabla-tickets)
    partials/estado_badge.html       # Badge de estado reutilizable
    partials/rol_badge.html          # Badge de rol (hoy sin uso)
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
3. ✅ Templates: `ticket_form.html`, `ticket_detail.html` (referencia Figma) — `login.html` ya hecho
4. ✅ HTMX partials para interacciones en detalle (tomar ticket, cambiar estado, comentar) — PENDIENTE (los forms del detalle hacen submit normal por ahora)
5. ✅ **Menu desplegable en el icono de usuario** (header): nombre, email, rol, **Administración** (solo superuser + rol DESARROLLADOR/COORDINADOR), **Cambiar contraseña** y **Salir**
6. Tailwind config + build compilado (reemplazar CDN)
7. `settings.HUEY` para activar cola de tareas

- **Notas para proxima sesion**
- No tocar modelos ni admin (estan cerrados)
- Fase 2 **no** se implementa hasta cerrar Fase 1 completo
- Huey ya configurado en tasks.py, falta settings.HUEY
- `ai/models.py` vacio intencionalmente (modelos IA en core)
- **Menu de usuario (header)**: avatar + chevron abre `#user-menu`. Bloque identidad con **barra vertical de color por rol** (`self-stretch w-1.5`, SOLICITANTE=brand-600 / DESARROLLADOR=emerald-600 / COORDINADOR=purple-600) + nombre, email y rol en texto debajo. Items: **Administración** (`gestionar` solo superuser o rol DEV/COOR; **el link NO sustenta `is_staff`** — si un DEV/COOR no es staff lo espera un 403/redirect en /admin/), **Cambiar contraseña**, **Salir**. JS: cierra con click afuera o Escape.
- **is_staff vs rol (desacoplados a proposito)**: `rol` = permiso de negocio (vistas); `is_staff`/`is_superuser` = acceso a /admin/. Los seeds crean SOLO solicitantes (pasword `Solicitante123!`), ninguno staff. El unico staff/superuser del entorno es `patosimple` (creado a mano). Si un DEV/COOR necesita /admin/, hay que marcarle `is_staff` en el admin.
- **Settings y .env**: `DATABASE_URL` y `MODO_FILTRO_CLIENTE` se leen SOLO al arrancar el proceso. Cambiarlos (en `.env` o `settings.py`) requiere reiniciar/redeploy (Gunicorn/Render). No cambian en caliente.
- **Zona horaria**: `config/settings.py` → `TIME_ZONE = 'America/Argentina/Buenos_Aires'` (UTC-3) + `USE_TZ = True`. Django guarda fechas en UTC y las renderiza en local vía el template filter `|date`. Si cambia el usuario principal, ajustar `TIME_ZONE`.
- **Accesos a sistemas en admin**: `UsuarioSistemaInline` dentro de `UsuarioAdmin`. Duplicados los valida el formset nativo de Django antes de guardar (el `unique_together` de BD es respaldo). No hace falta `related_name` en `UsuarioSistema` por ahora.
- El carrusel multiMCP tuvo problemas en sesion anterior: Groq/Cerebras con modelos deprecados, Kimi/SambaNova sin saldo, NVIDIA con funcion no encontrada, Gemini modelo deprecado. Revisar IDs de modelos.
- **Dark mode**: Templates futuros (`ticket_form.html`, `ticket_detail.html`) deben crearse con clases `dark:` listas. Toggle implementado en `base.html` con `localStorage` + `prefers-color-scheme`, transición suave (`transition-colors duration-200` en body), iconos SVG inline sol/luna. Paleta: header `bg-brand-800` fijo (funciona en ambos temas), sidebar `bg-brand-950`, fondos neutrales dark: body `#172233` (tono intermedio), tarjetas/inputs `slate-800`/`slate-700`. Light: fondo `gray-100`, tarjetas `white`.
  - **Comportamiento del toggle**: default SIEMPRE light en primera visita (ignora pref del OS); el toggle guarda la eleccion en `localStorage` (`theme` = `'dark'`/`'light'`) y la aplica en futuras cargas. Script init: agregar clase `dark` solo si `localStorage.theme === 'dark'`. Toggle (vanilla JS, no HTMX): `document.documentElement.classList.toggle('dark')` + guardar valor.
- **Links/titulos en modo light**: usar `text-brand-700 hover:text-brand-900` (NO `brand-400`, contrasta mal sobre fondo claro), con `dark:text-brand-400 dark:hover:text-brand-300` en modo oscuro. Ejemplo en el titulo del ticket en `partials/ticket_table.html`.
- **Paginacion client-side (modo cliente)**: `paginate_by=None` trae TODO el dataset (sin limite). Si el volumen crece y baja el rendimiento, pasar a server-side (`MODO_FILTRO_CLIENTE=False`). El paginador client-side usa `PAGE_SIZE=20` en el JS del listado.
- **`core/tests.py` PENDIENTE (lo vimos, se dejo para el final)**: tests de vistas (modo cliente + server + permisos por rol) con `TestCase`. Consideración: los tests usan DB temporal — con Neon externo habria que configurar una DB local de prueba o ajustar permisos. El test client de Django NO ejecuta JS; para la logica client-side hay que validar con Node + DOM mock (como se hizo manualmente en esta sesion).

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
- Modo cliente: aplica SOLO visibilidad por rol (superuser/solicitante/desarrollador) y via `get_paginate_by()` devuelve `None` (trae TODO el dataset; filtrado Y paginacion ocurren en el navegador).
- Modo server (flag False): comportamiento completo (filtros sistema/estado/q + paginacion 20).

**2. `core/templates/core/partials/ticket_table.html`** ✅
- Cada `<tr>` (tabla `md+`) y `<li>` (cards movil `<md`) tiene `data-ticket-id`, `data-sistema` y `data-estado`. Inofensivo en modo server.

**3. `core/templates/core/ticket_list.html`** ✅
- HTMX del form envuelto en `{% if not MODO_FILTRO_CLIENTE %}`; en modo server aparece el enlace "Limpiar".

**4. JS client-side (`{% block extra_js %}`)** ✅
- Se incluye solo si `MODO_FILTRO_CLIENTE` (el `{% if %}` va DENTRO del block, no afuera — envolver un `{% block %}` en `{% if %}` no funciona en Django).
- **Paginacion + filtrado estilo Angular Material**: mantiene el dataset completo en memoria (agrupa nodos por `data-ticket-id`), filtra sobre el TOTAL (substring titulo case-insensitive + match exacto sistema/estado), resetea a pagina 1, y pagina de a 20 (`PAGE_SIZE=20`) mostrando solo la pagina actual. Contador "Mostrando A-B de N" (N = resultados filtrados), "Pagina X de Y", botones anterior/siguiente con disabled. Debounce 200ms en `q`.

**5. Paginacion (demo)** ✅
- En modo cliente es **client-side** (de a 20 en el navegador sobre el dataset completo). La paginacion server-side solo se usa en modo server (`page_obj.has_other_pages and not MODO_FILTRO_CLIENTE`).

**6. Migracion a produccion (futuro)** ✅
- Poner `MODO_FILTRO_CLIENTE=False`. El form recupera `hx-get`, el queryset vuelve a filtrar/paginar en server (20), el JS client-side deja de cargar. **Cuando el volumen crezca y baje el rendimiento del modo cliente (trae todo el dataset), pasar a server-side.**

### Verificacion
- ✅ Verificado con test client: modo cliente trae todo + cargando JS/paginador client sin `hx-get`; modo server filtra (`estado=PENDIENTE` → 1 fila) + `hx-get` activo. Partial HTMX OK en ambos modos.
- ✅ Logica de paginacion client-side validada con test de Node + DOM mock (45 tickets): pagina de a 20, ultima pagina parcial, disabled de botones, filtro que resetea y recalcula paginas (PASS 9/9). El JS se probo con `node --check` + ejecucion con un DOM falso (el test client de Django no ejecuta JS).

### Recordatorios
- Encoding templates: PowerShell `[System.IO.File]::WriteAllText(..., UTF8)`, NUNCA `Set-Content`.
- Los selects de sistema y estado usan la MISMA metodologia client-side que `q` (los 3 disparan el filtrado en el navegador sin recargar).
- **Django `{% if %}` no soporta parentesis** para agrupar condiciones (dio TemplateSyntaxError). Usar ifs anidados.
- **Django venv**: hay que instalar `django-environ` (no venia instalado aunque settings lo importa).