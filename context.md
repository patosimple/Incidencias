# Contexto del proyecto: Sistema de tickets

## Qué es

Sistema interno de gestión de tickets para reportar bugs de dos aplicaciones
de un sistema de financiamiento político (Balances y Financiamiento). Los
tickets los reportan usuarios "Solicitante" (auditores) y los resuelven
usuarios "Desarrollador", de forma colaborativa (varios devs pueden tomar y
trabajar el mismo ticket a la vez, sin asignado único).

## Alcance por fases

**Fase 1 (actual, cerrar primero):** sistema de tickets convencional —
login, listado con filtros, creación de ticket, detalle con comentarios y
adjuntos, toma colaborativa de tickets, cambio de estado, administración de
sistemas y accesos de usuario. Sin funcionalidad de IA todavía.

**Fase 2 (después de cerrar Fase 1):** capa de análisis con IA — al crear
un ticket, se generan en segundo plano dos análisis (Conceptual y Técnico)
usando un LLM, con salida estructurada. El modelo de datos y el esqueleto de
código de esta fase ya existen (`ai/providers.py`, `ai/tasks.py`,
`AnalisisIA`/`ModeloIA`/`ConfiguracionIA` en `core/models.py`), pero no se
conecta a las vistas ni se activa hasta terminar Fase 1. No implementar
lógica de Fase 2 todavía salvo que se indique explícitamente.

No están en el alcance de ninguna de las dos fases (quedan para más
adelante, fuera de este proyecto por ahora): migración del canal de
Discord, y relación entre tickets y código fuente real de los repositorios.

## Stack técnico

- **Backend:** Django, un único proyecto (sin microservicios).
- **Base de datos:** PostgreSQL (local o Neon), con `psycopg`.
- **Tareas en segundo plano:** Huey, backend `PostgresHuey` (sobre la misma
  base de datos, sin Redis).
- **Frontend:** sin SPA — Django templates + HTMX (interacciones sin
  recarga completa) + Tailwind (estilos).
- **Archivos estáticos en producción:** Whitenoise.
- **Deploy objetivo:** Render (app) + Neon o Supabase (base de datos).

## Estado actual del repo

- Entorno (venv) y proyecto Django creados.
- `core/models.py` y `core/admin.py` completos y funcionando.
- Migraciones corridas contra la base (Postgres local o Neon).
- Panel de admin funcionando (`/admin/`).
- `ai/providers.py` (abstracción `AIProvider`) y `ai/tasks.py` (tarea Huey)
  ya escritos como esqueleto para Fase 2, con `TODO`s marcados donde falta
  la implementación real de cada proveedor (Groq, Gemini, OpenRouter).
- Pendiente: `urls.py`, `forms.py`, `views.py`, templates, integración de
  HTMX/Tailwind. Nada de esto existe todavía.

## Modelo de datos (ya cerrado, no modificar el esquema sin confirmar)

- **Usuario** (extiende el modelo de auth de Django): campo `rol`
  (SOLICITANTE / DESARROLLADOR / COORDINADOR — este último reservado, sin
  uso todavía). `is_staff`/`is_superuser` controlan el acceso al admin,
  independiente del campo `rol`.
- **Sistema**: catálogo de aplicaciones sobre las que se reporta (hoy
  Balances y Financiamiento, extensible). Acceso de cada usuario a uno,
  otro o ambos vía `UsuarioSistema` (M2M).
- **Ticket**: `titulo`, `sistema` (FK), `solicitante` (FK),
  `descripcion_original` (texto enriquecido), `estado` (PENDIENTE /
  EN_PROCESO / CERRADO / REABIERTO), `creado_en`, `cerrado_en`.
  Colaboración de varios desarrolladores vía `TicketDesarrollador` (M2M
  through, sin asignado único).
- **Comentario**: de cualquier usuario sobre un ticket.
- **Adjunto**: pertenece a un `Ticket` O a un `Comentario` (FKs nullable
  `ticket`/`comentario`, con `CheckConstraint` que exige exactamente una de
  las dos completa — no es relación polimórfica).
- **AnalisisIA** (Fase 2): dos por ticket (tipo CONCEPTUAL / TECNICO),
  salida estructurada (`problema`, `comportamiento_esperado`,
  `comportamiento_observado`, `pasos_reproducir`, `datos_relevantes`,
  `informacion_faltante`), estado de aprobación (solo aplica al
  Conceptual), y referencia al `ModeloIA` que lo generó + `version_prompt`.
- **ModeloIA** (Fase 2): catálogo abierto de proveedores/modelos. No
  guarda API keys (van en variables de entorno).
- **ConfiguracionIA** (Fase 2): tabla singleton, indica qué `ModeloIA` está
  activo.

## Convenciones

- Nombres de modelos, campos y variables en **español**, en minúscula con
  guiones bajos (`descripcion_original`, `estado_aprobacion`) — mantener
  consistencia con lo ya escrito, no traducir a inglés.
- Los templates deben seguir el diseño del prototipo (se provee por
  separado, capturas de pantalla por pantalla).
- Las vistas deben respetar los permisos por rol: un Solicitante ve sus
  propios tickets y el análisis Conceptual (con opción de aceptar/objetar);
  un Desarrollador ve los tickets de los sistemas a los que tiene acceso,
  puede tomar tickets, comentar, y ver ambos análisis (Conceptual y
  Técnico).

## Referencia visual

Las capturas del prototipo de interfaz (Figma) se proveen aparte, una
imagen por pantalla. Seguir esa referencia para layout, colores y
componentes (sidebar, badges de estado, tarjetas de análisis IA) al armar
los templates.
