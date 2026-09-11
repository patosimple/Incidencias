# TP de entrega — Trabajo y decisiones (UTN)

> Documento de trabajo del TP de fin de ciclo. La **consigna oficial** está en
> [`ENTREGA_CONSIGNA.md`](ENTREGA_CONSIGNA.md) (dentro de esta carpeta `ENTREGA/`).
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

## 3. Artifactos generados (carpeta `ENTREGA/`)
| Archivo | Qué es | Estado |
|---|---|---|
| `ENTREGA_CONSIGNA.md` | Consigna oficial completa (no tocar) | ✅ guardada |
| `Entrega_Final_TP.docx` | Informe del TP en Word (Parte 1 + Parte 2) | ✅ esqueleto completo con `[COMPLETAR]` |
| `generar_entrega.py` | Script que construye el `.docx` con `python-docx` (reproducible) | ✅ |
| `diagramas/*.mmd` | 5 diagramas Mermaid por separado (arquitectura, clases, casos de uso, secuencia IA, estados del ticket) | ✅ (ver §4) |
| `capturas/` | PNG de pantallas (réplicas o reales según §6) | ⏳ pendiente |
| `presentacion_ppt.pptx` | Walkthrough/deck de pantallas | ⏳ pendiente (no hacer todavía) |
| `manual_uso.html` / `manual.html` (app) | Manual de uso consultable | ⏳ pendiente (no hacer todavía) |

### Cómo regenerar el Word
```bash
venv\Scripts\python.exe ENTREGA\generar_entrega.py
```
- Requiere `python-docx` instalado en el venv (ya instalado: 1.2.0).
- Los textos editables van en el script (no editar el `.docx` a mano, se pisa al
  regenerar).

---

## 4. Diagramas (Mermaid, separados a propósito)
Los diagramas **van como IMAGEN (PNG)** en el Word. `generar_entrega.py` incrusta
automáticamente `diagramas/<base>.png` si existe; si no, deja un **espacio
reservado** etiquetado "DIAGRAMA IMAGEN" con la referencia al `.mmd` fuente
(la imagen se genera aparte, p.ej. pegando el `.mmd` en <https://mermaid.live>
y exportando PNG con el mismo nombre base).

| Diagrama | Archivo `.mmd` | PNG esperado |
|---|---|---|
| Arquitectura general | `diagramas/arquitectura.mmd` | `diagramas/arquitectura.png` |
| Flujo de agentes (metodología de desarrollo) | `diagramas/agentes_desarrollo.mmd` | `diagramas/agentes_desarrollo.png` |
| Flujo de estados del ticket | `diagramas/estados_ticket.mmd` | `diagramas/estados_ticket.png` |
| UML Clases | `diagramas/clases.mmd` | `diagramas/clases.png` |
| UML Casos de uso | `diagramas/casos_de_uso.mmd` | `diagramas/casos_de_uso.png` |
| UML Secuencia del análisis IA | `diagramas/secuencia_analisis_ia.mmd` | `diagramas/secuencia_analisis_ia.png` |

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

### Pendientes del usuario
- [ ] Listar qué partes/features se hicieron con cada esquema (Antigravity/Gemini
      multi-agente vs opencode manual).
- [ ] **Pasar con qué modelos se trabajó** en el multi-agente (el usuario dijo
      que los va a detallar; hoy el diagrama lo deja como
      `[COMPLETAR: modelos]`).
- [x] Diagrama de flujo de agentes del desarrollo agregado (sección 2 del Word) —
      `agentes_desarrollo.mmd`.

---

## 6. Contenido del Word: qué está y qué falta completar
El `.docx` tiene **todo el esqueleto** de Parte 1 y Parte 2. Los placeholders
`[COMPLETAR ...]` están en:
- Portada: integrantes.
- Links obligatorios: URL de la app en producción y video.
- Sección 4: capturas reales, video, log de sesión real (exportar de la DB).
- Sección 5: prueba con usuario real (feedback de decisiones de UX).
- Sección 7: reflexión final.
- Parte 2: respuesta de las 4 preguntas (hay borradores) y captura de Ollama.

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

### Todavía NO hacer (pendientes explícitos del usuario)
- ❌ NO construir aún el **Manual de uso**.
- ❌ NO construir aún el **PPTX**.
- Solo documentamos la decisión aquí para que no se pierda.

---

## 7. PPTX de pantallas (plan, NO implementado aún)
- Necesita `python-pptx` (instalar en el venv cuando se haga).
- Formato: 1 slide por pantalla (título + captura/réplica PNG + anotación breve).
- Nace de las réplicas del Enfoque A (o capturas reales si se prefiere).
- Pantallas típicas: login, listado (desktop/móvil/dark), crear ticket (Quill),
  detalle con análisis IA expandido/colapsado, admin de usuarios, modal Swal.

---

## 8. Parte 2 / IA local — estado y plan pendiente
- La app ya tiene **Ollama como proveedor** (`OllamaProvider`, formato NATIVO,
  sin key, `localhost:11434`); registrado en BD (`gemma2:2b`, NATIVO). NO es el
  modelo activo (Groq sigue activo).
- El usuario busca/descarga `qwen2.5:3b` (recomendado para su equipo: Xeon
  W3680, 10 GB DDR3, sin GPU útil → modelos ~3B, ~8–15 tok/s).
- **RAG v1 pendiente** (manuales de uso por sistema embebidos localmente con
  `nomic-embed-text`; diseño dual por flag `RAG_MANUAL`). Detalle completo en
  `AGENTS.md` (sección "PENDIENTE — Contexto IA de manuales de uso (RAG v1)").
- Para el entregable opcional de captura: `ollama run qwen2.5:3b` + pregunta del
  dominio (ej. ventajas/riesgos de LLM local vs nube en Financiamiento político).

---

## 9. Referencias de archivos útiles
- Templates reales (fuente de las réplicas): `core/templates/core/*.html` y
  `partials/*.html`.
- Datos demo (para las réplicas): seed en `core/management/commands/seed_init.py`
  y `seed_tickets.py` (solicitantes `maria.lopez`/`carlos.gonzalez`/... password
  `soli`).
- Paleta brand: ver `core/templates/core/base.html` (tailwind.config inline).
- Hardware del usuario (justifica modelos 3B): `C:\Users\Patricio\Desktop\P.xml`.