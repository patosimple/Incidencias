# TP de entrega — Trabajo y decisiones (UTN)

> Documento de trabajo del TP de fin de ciclo. La **consigna oficial** está en
> [`ENTREGA_CONSIGNA.md`](ENTREGA_CONSIGNA.md) (dentro de esta carpeta `TP/`).
> Este MD registra el estado real del trabajo, las decisiones tomadas y lo que
> queda por hacer. Si el usuario pide trabajar en la entrega, **leer primero la
> consigna** y después este documento.
>
> Regla: NO commitear/pushear sin pedido explícito del usuario.

---

## 1. Estado actual del proyecto
- **Fase 1 completa**: tickets convencionales (login, listado, creación, detalle,
  comentarios, adjuntos, toma colaborativa, cambio de estado, admin).
- **Fase 2 parcial**: análisis IA vía LLM (manual, botón Analizar/Reanalizar).
  Providers Groq/Gemini/OpenRouter/NVIDIA/Ollama con llamada HTTP real.
  Pendiente: admin de versiones de prompt.
- **Adjuntos**: almacenamiento **permanente en la nube** (Supabase Storage S3,
  configurado 16/09/2026) para el deploy de producción (Render). En DEBUG local
  siguen en disco (`media/`).
- **Deploy en producción**: Render free + Neon + Supabase. **Ping keepalive con
  UptimeRobot (21/09/2026)**: monitor HTTP a `https://incidencias-bs9f.onrender.com/login/`
  cada 5 min para que la app **no duerma** durante la evaluación (sin cold start).
  **POR DEFECTO: monitor PAUSADO** (estado actual al 21/09/2026; verificado que funciona: UP constante ~377 ms) →
  **reanudarlo el día de la entrega** y **pausarlo al terminar** la evaluación
  (Render free = 750 hs/mes; despierta 24/7 consume ~744). Detalle en `AGENTS.md`.
- Detalle completo del estado en **`AGENTS.md`**.

---

## 2. Qué pide la consigna (resumen operativo)
Parte 1 (la app):
1. Presentación del equipo y proyecto.
2. Arquitectura + diagramas (arquitectura general, flujo de agentes, UML de
   clases, casos de uso y secuencia).
3. Stack tecnológico **obligatorio** (tabla: componente, tecnología, por qué).
4. Evidencia de funcionamiento (capturas reales + log de sesión real).
5. UX/UI: ≥5 heurísticas de Nielsen con evidencia.
6. Ciberseguridad: log de riesgos (categoría, medida implementada).
7. IAs usadas en el co-work + reflexión.

Parte 2 (IA local):
- 4 preguntas sobre LLM/SLM local en el proyecto.
- Entregable opcional: captura de Ollama local respondiendo una pregunta.

Criterios de evaluación (pesos): App 30%, Arquitectura 20%, UX/UI 20%,
Ciberseguridad 10%, Parte 2 20%.
Formato: PDF 10–20 páginas + anexos; en la **primera página** la tabla de links
obligatorios (repo, app en producción, video).

---

## 3. Artifactos generados (carpeta `TP/`)
| Archivo | Qué es | Estado |
|---|---|---|
| `ENTREGA_CONSIGNA.md` | Consigna oficial completa (no tocar) | ✅ guardada |
| `Entrega_Final_TP.html` + `.pdf` | **Informe principal del TP** (Parte 1 + Parte 2) en HTML/PDF, estilo manual (Tailwind + paleta brand) | ✅ **21 páginas, sin páginas en blanco, log completo, diagramas con su título (y los fullpage más grandes desde 20/09)** |
| `generar_entrega_html.py` | Script que genera el `.html` (y de ahí el `.pdf` con Edge headless) | ✅ |
| `Entrega_Final_TP.docx` | Informe del TP en Word (mismo contenido; **anexo/backup**) | ✅ esqueleto completo con `[COMPLETAR]` |
| `generar_entrega.py` | Script que construye el `.docx` con `python-docx` (reproducible) | ✅ |
| `log_sesion.txt` + `generar_log_sesion.py` | Log real de la sesión (línea de tiempo) extraído de la DB | ✅ |
| `diagramas/*.mmd` **+ `*.png`** | 6 diagramas Mermaid (arquitectura, agentes_desarrollo, estados_ticket, clases, casos de uso, secuencia IA). PNG rasterizados de los A4 a 200 dpi | ✅ (ver §4) |
| `diagramas render/` | PDFs A4 renderizados por el usuario (fuente de los PNG) | ✅ (¿commitear? decisión pendiente) |
| `capturas/` | PNG de pantallas (réplicas o reales según §6) | ✅ 22 capturas (hard links a `core/static/core/img/manual/`) |
| `presentacion_ppt.pptx` | Walkthrough/deck de pantallas | ⏳ pendiente (no hacer todavía) |
| `manual.html` (app) | Manual de uso consultable (`/manual/`) | ✅ 18 secciones (ver estado en AGENTS.md) |

### Cómo regenerar el informe
```bash
venv\Scripts\python.exe TP\generar_entrega_html.py         # genera el .html
# luego convertir a PDF con Edge headless (ver docstring del script)
venv\Scripts\python.exe TP\generar_entrega.py              # genera el .docx (anexo)
```
- Requiere `python-docx` (ya instalado: 1.2.0) y Edge headless para el PDF.
- Los textos editables van en los scripts (no editar `.html`/`.docx` a mano, se
  pisan al regenerar).
- **Fix de PDF aplicados en `generar_entrega_html.py`**: título de diagrama +
  diagrama en la misma página (`.caja-junta` + `max-height` de imagen), sin
  páginas en blanco entre secciones (salto sobre el `h2` con `page-before`, no
  div vacío), log completo fluyendo entre páginas (`pre-wrap`), tamaño de fuente
  normal (el `overflow-auto` del log ensanchaba la página y Edge escalaba todo a
  2/3).
- **Diagramas fullpage más grandes (20/09/2026)**: los 4 diagramas que van solos
  en su página (estados del ticket, UML clases, casos de uso, secuencia IA)
  pasaron de ~77% a ~93% de la hoja solo vía render: parámetro `max_height=640`
  en `_diagrama(...)` (inline style que gana al `520pt` del CSS). Los PNG ya
  estaban a 200 dpi (sin cambios de bytes). Ver detalle en AGENTS.md.

### `[COMPLETAR]` pendientes del informe (los prepara el usuario)
- ~~Mediciones IA local vs nube~~ — **RESUELTO 19/09/2026**: la Pregunta 4 ya NO usa tiempos
  (`[T_LOCAL]`/`[T_NUBE]` fuera); quedó **cualitativa** (decisión del usuario: limitación de
  hardware local, calidad local más pobre, mantenimiento manual de modelos).
- ~~Captura + respuesta de Ollama~~ — **RESUELTO 19/09/2026**: la "Captura de Ollama local"
  ya incorpora la **respuesta del modelo** transcrita en el informe (dejó de ser "entregable
  opcional"); figura `query_ollama.png` (captura real del usuario).

> Nota 18/09/2026: integrantes en portada y sección 1 ya están **sin roles** (trabajo
> conjunto); rol Coordinador no se nombra en el informe (la app lo conserva "a futuro");
> la fila "Otros recursos publicados" de los links se eliminó. El `.docx` quedó congelado.
>
> Nota 19/09/2026 (últimas correcciones del usuario): portada con subtítulo en 2 líneas;
> "Por qué" del stack en 1ra persona ("Elegimos..." / "elegimos Python porque..."); "Video de
> demostración" (sale "(opcional)" y "(max 3 min)"); tabla sección 7 con encabezados "Para qué
> la usamos / Qué nos aportó", **fila GitHub/Git eliminada**, Antigravity con Bien/Mal (se
> queda sin tokens en tareas grandes) y opencode con mención de la suite de tests; Reflexión
> reescrita en 3 párrafos sin números de tests; Parte 2 con nueva "Introducción" y Pregunta 3
> reescrita. **El informe quedó SIN `[COMPLETAR]` pendientes** (PDF sigue en 21 páginas). El
> `.docx` (`generar_entrega.py`) sigue congelado/desactualizado.

---

## 4. Diagramas (Mermaid, PNG incrustados)
Los diagramas **van como IMAGEN (PNG)** en el informe. Ambos generadores
(`generar_entrega.py` docx y `generar_entrega_html.py` html/pdf) incrustan
`diagramas/<base>.png` si existe. Los PNG se rasterizaron desde los
PDFs A4 renderizados por el usuario (`diagramas render/*_A4.pdf`) con
**pymupdf** a **200 dpi** (el 17/09/2026). Los 6 siguen a 200 dpi hoy (los
4 "fullpage" se re-probaron el 20/09/2026 y dieron bytes idénticos — el único
cambio que los agrandó en el PDF fue el `max_height=640` del generador, no el
PNG).

| Diagrama | Archivo `.mmd` | PNG |
|---|---|---|
| Arquitectura general | `diagramas/arquitectura.mmd` | ✅ `arquitectura.png` |
| Flujo de agentes (metodología de desarrollo) | `diagramas/agentes_desarrollo.mmd` | ✅ `agentes_desarrollo.png` |
| Flujo de estados del ticket | `diagramas/estados_ticket.mmd` | ✅ `estados_ticket.png` |
| UML Clases **(único clases+tablas)** | `diagramas/clases.mmd` | ✅ `clases.png` |
| UML Casos de uso | `diagramas/casos_de_uso.mmd` | ✅ `casos_de_uso.png` |
| UML Secuencia del análisis IA | `diagramas/secuencia_analisis_ia.mmd` | ✅ `secuencia_analisis_ia.png` |

> **Decisión 17/09/2026 — DER vs clases**: se consultó por un DER "basado en
> estructura DB" separado. Resultado: **no hace falta** — los modelos Django
> acarrean toda la metadata de BD (unique_together, on_delete, nullables, CHECK),
> así que `clases.mmd` (ya corregido contra el código real) cubre **clases y
> tablas a la vez**. El `der.mmd` que se había creado se eliminó (redundante).

**Sobre el "diagrama de flujo de agentes"**: la app en sí no usa orquestación
multi-agente (el análisis IA es un paso manual), pero el desarrollo sí se
realizó con esquemas de IA (ver sección 5). El diagrama que lo documenta es
`diagramas/agentes_desarrollo.mmd` (Gemini orquestador sobre multiMCP adaptado
con rotación de API keys/proveedores, alternado con opencode manual).

---

## 5. Metodología de desarrollo: multi-agente + opencode (info del usuario, 12/09/2026)
El desarrollo **no se hizo con una única herramienta**. El usuario documentó que se
trabajó en dos esquemas combinados:

### Base — Claude (claude.ai, chat): planificación + andamiaje inicial
- Desde el **chat de claude.ai** se hizo toda la **planificación y diseño del
  sistema** (entidades, flujos, esquema de datos), y **allí mismo** geró el
  **proyecto Django inicial** listo para trabajar: estructura del proyecto,
  modelos, urls y views iniciales, **archivos docker** y **requirements.txt**,
  entregados como **.zip** — que luego fue la base para trabajar con
  Antigravity (multi-agente) y opencode (agentes manuales). Verificado con el
  usuario (12/09/2026).

### Esquema 1 — Antigravity + Gemini como orquestador (multi-agente)
- **Antigravity** (IDE) con **Gemini como orquestador** generando/moviendo
  agentes, sobre un **multiMCP adaptado para usar rotación interna de API keys
  y proveedores** (el multiMCP base —carrusel de proveedores— se modificó con
  Antigravity/Gemini).
- Esto cubrió parte del desarrollo (a determinar qué secciones/features
  específicas — pendiente que el usuario indique cuáles).

### Esquema 2 — opencode con cambio de agente manual
- **opencode** (CLI) trabajando de a un agente a la vez, con **cambio de agente
  manual** según la tarea (ej. agente de código, agente de investigación,
  etc.).
- Cubrió el resto del desarrollo.

### Contexto compartido entre esquemas
- El **contexto del proyecto se comparte entre ambos esquemas vía `AGENTS.md`**
  (archivo del repositorio): tanto Antigravity como opencode lo leen y lo
  actualizan, de modo que alternar entre modalidades no pierde la memoria del
  desarrollo (conceptos, decisiones de diseño, pendientes).

### Pendientes del usuario (resueltos 16/09/2026)
- [x] **Features por esquema / modelos del multi-agente**: el usuario decidió que
      NO hace falta detallar qué features se hicieron con cada esquema ni con qué
      modelos: el informe solo deja **constancia de las 2 modalidades** (esquema
      1 = Antigravity/Gemini multi-agente; esquema 2 = opencode manual). Se edita
      la sección correspondiente del Word (sección 7 / `generar_entrega.py`) sin
      listar features ni modelos (`[COMPLETAR]` se reemplaza por la descripción
      genérica de ambas modalidades).
- [x] Diagrama de flujo de agentes del desarrollo agregado (sección 2 del Word) —
      `agentes_desarrollo.mmd`.

---

## 6. Contenido del informe (PDF principal, docx anexo): qué está y qué falta
El **PDF (`Entrega_Final_TP.pdf`, 21 páginas)** es el informe principal (Parte 1
y Parte 2 completas, con capturas reales, diagramas, log y tablas). El `.docx`
replica el mismo contenido como anexo editable (congelado/desactualizado desde
18/09). **Ya NO quedan placeholders `[COMPLETAR]`**: los últimos se resolvieron en
las correcciones del 19/09 (integrantes sin roles, URLs de repo/app/video, video
demo sin "(opcional)", Q4 cualitativa sin mediciones de tiempos, captura de Ollama
con la respuesta del modelo). Ver el detalle en §3.

---

## 6. Capturas de pantalla: enfoques decididos (10/09/2026 — decisión del usuario)
El usuario preguntó si podía "dibujar" las pantallas con HTML/CSS en lugar de
capturar. La respuesta: **sí** (réplicas con las mismas clases Tailwind de los
templates reales + Edge headless para exportar a PNG). Hay dos enfoques:

### Enfoque A — Réplicas estáticas (heredan el look real)
- Compatibles con el standard de `AGENTS.md`: *mismas clases Tailwind → misma
  apariencia garantizada* (es la base del Manual de uso).
- HTML standalone por pantalla que reutilizan las clases/paleta brand de los
  templates reales + datos de ejemplo (del seed) + SVG/íconos de `base.html`.
- Se capturan con **Edge headless** ya instalado:
  `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
  (flag `--headless --screenshot=... --window-size=...`).
- Requiere servir los HTML por HTTP (no `file://` con Tailwind CDN) o bajar el
  CSS de Tailwind a local. Las variantes dark se pueden forzar con la clase
  `dark`.
- **Limitación**: son maquetas con datos ficticios (no capturas reales).

### Enfoque B — Capturas reales (app corriendo + Edge headless)
- Levantar `runserver` con datos del seed y navegar con Edge headless a
  `http://localhost:8000` logueado como un seed user (cookie armada con el test
  client).
- Produce pantallas reales exactas (Quill, datos reales, HTMX).
- **Costoso/frágil**: requiere setup de sesión y que la app no esté rota.

### ✅ DECISIÓN TOMADA (el usuario)
| Uso | Enfoque |
|---|---|
| PPTX walkthrough | **A** (réplicas estáticas) |
| Manual de uso | **A** (réplicas estáticas) |
| Sección 4 "Evidencia de funcionamiento" | **B** (capturas reales) |

### ✅ Manual de uso Y PPTX: decisión de implementación
- **Manual de uso en la app: IMPLEMENTADO (15-16/09/2026)** — ruta `/manual/`,
  vista `ManualView`, 18 secciones colapsables, TOC de anclas dinámico
  (`toc_general`/`toc_desarrollo`/`toc_admin`), visibilidad por rol (solicitante:
  1-10; dev/coordinador: 1-15; staff: 1-18), réplicas Tailwind + 22 capturas en
  `core/static/core/img/manual/`. Detalle completo de contenido/ajustes en
  `AGENTS.md` (bullet "Manual de usuario HTML").
- ❌ NO construir aún el **PPTX** (sigue pendiente explícito).

---

## 7. PPTX de pantallas (plan, NO implementado aún)
- Necesita `python-pptx` (instalar en el venv cuando se haga).
- Formato: 1 slide por pantalla (título + captura/réplica PNG + anotación breve).
- Nace de las réplicas del Enfoque A (o capturas reales si se prefiere).
- Pantallas previstas (a confirmar al implementar): login, listado desktop,
  listado móvil (cards), crear ticket (Quill + adjuntos), detalle con análisis IA
  expandido/colapsado, comentario con cita, detalle CERRADO, menú de usuario,
  admin de usuarios, empty state, dark mode.

### 7.1 Manual de uso — TOC validado por el usuario (12/09/2026)
Manual = una sola página web heredando `base.html`, con TOC de anclas + secciones
colapsables, réplicas estáticas (las clases Tailwind reales). Estructura:

**Parte general (todos los roles)**
1. Roles y permisos (Solicitante/Desarrollador/Coordinador — `rol_badge`)
2. Primeros pasos (login, logout, cambiar contraseña)
3. Ciclo de vida del ticket (estados + transiciones con `estado_badge`)
4. Listado de tickets (filtros sistema/estado/colaborador/novedades, orden por
   columnas, paginación, indicador de novedades)
5. Crear un ticket (campos, editor Quill, adjuntos múltiples, detalle a incluir)
6. Detalle del ticket (metadatos, autor, colaboradores, adjuntos)
7. Comentarios (crear, responder/citar, editar/eliminar, adjuntos)
8. Editar/eliminar el propio ticket (solo dueño, mientras no esté CERRADO)
9. Adjuntos (subir/descargar, tipos permitidos, límite 10 MB, almacenamiento en Supabase)
10. Preguntas frecuentes (5-6 FAQs)

**Solo desarrollo (oculto a solicitantes)**
11. Toma y liberación (tomar → EN_PROCESO; liberar; REABIERTO)
12. Cierre y reapertura por gestión (dev que reabre sin colaborar queda auto-tomado)
13. Filtro "Colaborador" (tomado) — solo rol DESARROLLADOR
14. Análisis IA (Analizar/Reanalizar, qué devuelve, reintentos, proveedores)
15. Colores de badge según quién tomó (verde=yo / azul=otro / rojo=sin tomar)

**Administración (solo staff/superuser)**
16. Gestión de usuarios y accesos (UsuarioAdmin + UsuarioSistemaInline)
17. Configuración IA (ModeloIA / ConfiguracionIA)
18. Nota técnica (restauración de soft-deletes: `Ticket.restore()`/`Comentario.restore()`)

### 7.2 Capturas reales que DEBE entregar el usuario (para manual/PPTX)
Elementos puntuales van como réplicas; las vistas de página completa necesitan
capturas reales del usuario (`capturas/`, PNG ~1280px, datos del seed/demo, sin
info sensible):
1. Login
2. Listado desktop con filtros+orden activos y badge "tomado" (rol dev)
3. Listado móvil (cards)
4. Crear ticket (form + editor Quill + adjuntos)
5. Detalle EN_PROCESO tomado por el usuario (Tomar/Cerrar/Liberar + colaboradores)
6. Comentario con cita/blockquote (modo Responder)
7. Detalle CERRADO (badge gris + botón Reabrir)
8. Sección Análisis IA expandida (DEV/COORD)
9. `/admin/` (lista de usuarios o edición con inline de sistemas)
10. Menú de usuario desplegado (Administración/Cambiar contraseña/Salir)
11. *Opcional*: alguna de las anteriores en dark mode

---

## 8. Parte 2 / IA local — estado y plan pendiente
- La app ya tiene **Ollama como proveedor** (`OllamaProvider`, formato NATIVO,
  sin key, `localhost:11434`); registrado en BD (`gemma2:2b`, NATIVO). NO es el
  modelo activo (Groq sigue activo).
- para las mediciones se usa **`qwen2.5:3b-instruct-q4_K_M`** (ya pull, 1.9 GB).
  Medición de referencia local (11/09/2026): **~6 tok/s** de decode → un análisis
  completo ≈ **1.5-2 min** (equipo sin GPU; solo referencia, no va al informe).
  **El informe NO incluye detalle de equipos** (la implementación final irá a un
  servidor propio de la organización con recursos superiores a los equipos de
  desarrollo).
- ✅ **Decisión 19/09/2026 — las mediciones ya NO van al informe**: la Pregunta 4
  quedó **cualitativa** (limitación de hardware local, calidad local más pobre,
  mantenimiento manual) sin `[T_LOCAL]`/`[T_NUBE]`; se descartó el plan de medir
  tiempos para volcarlos al informe (plan 11/09/2026). La referencia local
  (~6 tok/s, análisis ≈1.5-2 min) queda solo como dato contextual en `AGENTS.md`.
- ✅ **Timeout por proveedor IMPLEMENTADO (13/09/2026)**: base 60s
  (`TIMEOUT`) en `ai/providers.py`; `OllamaProvider` pisa a `TIMEOUT_OLLAMA` =
  240s (decode local lento; el análisis completo va en un solo POST) y envuelve
  `ConnectionError`/`Timeout` y 5xx como `RetryableProviderError` (el cliente
  los reintenta con "Reintento N..."). ✅ **URL de Ollama normalizada**
  (`_normalizar_host_ollama`, 13/09/2026): `OLLAMA_HOST` de máquina viene como
  bind del daemon (`0.0.0.0`, sin esquema/puerto) → se convierte a
  `http://127.0.0.1:11434`. Prueba: una sola pestaña de Chrome (con muchas
  pestañas quedan ~0.8 GB libres → swap; 1 tab alcanza).
- **RAG v1 pendiente** (manuales de uso por sistema embebidos localmente con
  `nomic-embed-text`; diseño dual por flag `RAG_MANUAL`). Detalle completo en
  `AGENTS.md` (sección "PENDIENTE — Contexto IA de manuales de uso (RAG v1)").
- **Decisión 13/09/2026 — manual txt completo en el prompt, NO embeddings
  (para el informe: costos/beneficios de txt vs embedding)**: se decidió enviar
  el manual de uso **completo** en el prompt en lugar de implementar RAG
  vectorial, tras conversar con el agente IA los costos/beneficios de ambas
  variantes. Por qué conviene txt en este caso:
  - Los manuales son **chicos** (BALANCES 24.5 KB / FINANCIAMIENTO 16.4 KB ≈
    ~10-12K tokens): entran **enteros** en el contexto del modelo. El modelo ve
    **todo** el contenido (calidad ≥ RAG, sin riesgo de fragmentos mal
    elegidos por similitud).
  - El embedding aporta **escalabilidad** (manuales de cientos de páginas) y
    **ahorro de tokens/prefill**, dos cosas que no se necesitan a esta escala;
    no mejora la respuesta y agrega complejidad (pgvector, pipeline de
    indexado, `nomic-embed-text` a cargo en Ollama).
  - Además, el RAG exige **1 embedding local por análisis** (la query) y, si
    el chat corre en Ollama, alternar chat↔embeddings **re-swapea los modelos**
    (arranques extra). Con manual completo no hay nada de eso.
  - **Estado: IMPLEMENTADO (13/09/2026, `VERSION_PROMPT` = v6)**: la descripción
    del ticket se envía junto al **manual completo** (`_leer_manual_sistema`
    lee `manuales_rag/<codigo>/*.txt`, resolución por `Sistema.codigo`, tope
    `MAX_MANUAL_CARACTERES` = 30000) y **`Sistema.prompt` se envía también**
    (se complementan: el manual describe "cómo se usa", el prompt "qué es" —
    sin manual, el comportamiento queda como antes, prompt solo). Si más
    adelante se hace la versión embeddings, la variable `RAG_MANUAL` y el
    pipeline quedan planeados en `AGENTS.md`.
  - **Fix esquema JSON con modelos chicos (13/09/2026, v4→v5→v6)**: con el
    manual completo (~24K chars) el qwen2.5:3b local inventaba OTRO esquema de
    JSON (`{"ticket": {...}}`) → el análisis se guardaba con los campos vacíos.
    **Fix**: `_construir_mensajes` repite el esquema de salida OBLIGATORIO al
    FINAL del `user` (los últimos tokens pesan más). Verificado contra Ollama
    real con manual completo (las 6 claves correctas). Mientras dure la etapa
    de pruebas de AnalisisIA con Ollama hay TEMPORAL (ver `AGENTS.md`
    "TEMPORAL para testear"): un checkbox "manual" (hoy **oculto** en la UI —
    `<label class="hidden">` — pero checkeado y funcional, para poder
    comparar con/sin manual si hace falta) y el tiempo total del análisis
    (hoy **oculto en la card de éxito**, visible solo en los errores).
- **Escalera de degradación por contexto (13-14/09/2026, IMPLEMENTADO)**:
  cuando el prompt completo (con manual txt) devuelve **413** o **400 +
  `context_length_exceeded`/`reduce the length`**, `_ejecutar_analisis`
  re-intenta SOLO en server con el **manual resumido** (`*_resumido.txt`,
  generados para BALANCES y FINANCIAMIENTO) y, si sigue, **sin manual**.
  Si todos los niveles agotan → `ProviderError` (error duro, el cliente
  muestra etiqueta roja). **Ollama local: SIEMPRE sin manual** (solo
  `Sistema.prompt`), aunque el checkbox esté activo — `_ejecutar_analisis`
  fuerza `usar_manual=False` para `OllamaProvider` (los manuales no caben en
  el contexto del modelo local y degradaban el decode/JSON). La escalera
  silenciosa queda reservada a los providers cloud. Detalle técnico completo
  en `AGENTS.md` ("Escalera de degradación silenciosa por contexto").
- **`proxies` en Ollama (fix 14/09/2026)**: `OllamaProvider.generar_analisis`
  manda `proxies={"http": None, "https": None}` para que un proxy corporativo
  (`HTTP_PROXY`/`HTTPS_PROXY`) no intercepte la llamada a `127.0.0.1:11434`
  (daba 503). No-op en equipos sin proxy; afecta solo esa llamada.
- **Seed `seed_init` respeta el modelo Ollama local (14/09/2026)**: si existe
  un `ModeloIA` de Ollama con modelo, el seed NO lo pisa (ni `modelo` ni
  `formato_salida` — la configuración local depende del equipo); solo crea el
  registro con el modelo del seed si no existe, y actualiza la fila Ollama solo
  si quedó sin modelo. El resto de los proveedores conserva el comportamiento
  (se actualiza SIEMPRE al catálogo).
- ✅ **Captura de Ollama DONE (19/09/2026)**: `ollama run qwen2.5:3b` + pregunta del
  dominio (ventajas/riesgos de LLM local vs nube en Financiamiento político); la
  **respuesta del modelo ya está transcrita en el informe** (sección "Captura de
  Ollama local", con `query_ollama.png`).

---

## 9. Referencias de archivos útiles
- Templates reales (fuente de las réplicas): `core/templates/core/*.html` y
  `partials/*.html`.
- Datos demo (para las réplicas): seed en `core/management/commands/seed_init.py`
  y `seed_tickets.py` (solicitantes `maria.lopez`/`carlos.gonzalez`/... password
  `Solicitante1!`; desarrollador demo `dev.demo` password `Desarrollador1!`, con
  acceso al admin de usuarios/sistemas/modelos IA).
- Paleta brand: ver `core/templates/core/base.html` (tailwind.config inline).
- Entorno de implementación final: servidor propio de la organización (recursos
  superiores a los equipos de desarrollo); los tiempos locales son referenciales.