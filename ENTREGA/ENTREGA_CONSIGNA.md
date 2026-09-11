# Consigna — Entrega Final de Proyecto

> **Fuente**: `d:\Mis documentos\DEV\Curso IA UTN\Entrega final curso.pdf`
> **Curso**: Inteligencia Artificial para Programadores — UTN FRBA
> **Guardado**: 11/09/2026, para no perder el contenido entre sesiones (compactions).
> **Nota**: el texto se extrajo del PDF con `pdftotext` (caracteres acentuados normalizados a mano).

**Contexto**: en la entrega de medio ciclo se diseñó conceptualmente una aplicación inteligente con orquestación agéntica, memoria persistente y ciclos de decisión. Esta entrega final tiene un objetivo concreto: esa idea debe existir, funcionar y estar publicada.

---

# PARTE 1 — El proyecto como aplicación real

**¿Qué se evalúa?**
Que el grupo evolucionó de un diseño conceptual a una aplicación real, funcional y demostrable, construida con el apoyo de herramientas de IA en co-work.

## Sección 1 — Presentación del equipo y del proyecto
- Integrantes del grupo (nombre, rol que tomó cada uno durante el desarrollo)
- Nombre del proyecto
- Problema que resuelve (mismo punto de partida de la entrega anterior, ahora con la solución implementada)
- Público objetivo (quiénes son los usuarios reales de la app)

## Sección 2 — Arquitectura técnica
**Diagrama de arquitectura general del sistema** (herramienta libre: Mermaid, draw.io, Lucidchart, IA generativa). Debe mostrar:
- Cómo fluyen los datos de entrada a salida
- Qué componentes son IA y cuáles son lógica tradicional
- Dónde vive la memoria persistente del sistema

**Diagrama de flujo de agentes** (si el proyecto tiene orquestación multi-agente):
- Qué decide cada agente
- Cómo se comunican
- Cuál es el ciclo cíclico de funcionamiento

**UML (al menos uno de los siguientes):**
- Diagrama de casos de uso (quién hace qué)
- Diagrama de secuencia (cómo fluye una interacción completa)
- Diagrama de clases (si hay estructura de datos definida)

## Sección 3 — Stack tecnológico
Tabla obligatoria con el siguiente formato:

| Componente | Tecnología / Herramienta | Por qué se eligió esta y no otra |
|---|---|---|
| Frontend | ej. React / HTML+JS / Flutter ... | ... |
| Backend | ej. Python FastAPI / Node.js ... | ... |
| Base de datos | ej. SQLite / Supabase / Firebase ... | ... |
| Modelo de IA | ej. GPT-4o / Claude / Gemini / ... | ... |
| Orquestación | ej. LangChain / n8n / código propio ... | ... |
| Despliegue | ej. Vercel / Render / local ... | ... |

*Nota para grupos sin base técnica: si usaron herramientas no-code (Bubble, Glide, Make, Zapier, Voiceflow), incluirlas igual en la tabla. El criterio de "por qué se eligió" sigue siendo obligatorio.*

## Sección 4 — Evidencia de funcionamiento
- **Capturas de pantalla del frontend (mínimo 3):**
  - Pantalla principal / home
  - Flujo de uso principal (el camino del usuario desde que entra hasta que obtiene valor)
  - Resultado o output de la IA visible para el usuario
- **Video de demostración** (opcional pero suma mucho):
  - Máximo 3 minutos
  - Mostrar el ciclo completo de uso real
- **Log o registro de una sesión real:**
  - Una ejecución completa del sistema con datos reales (no de prueba)
  - Puede ser un archivo de texto, una tabla, un dashboard screenshot

## Sección 5 — Evaluación UX/UI
El equipo debe realizar una autoevaluación del diseño de experiencia de usuario orientada al público objetivo definido.

### 5.1 — Heurísticas de Nielsen aplicadas al proyecto
Evaluar el sistema contra **al menos 5 de las 10** heurísticas de Nielsen:

| Heurística | Cumple? (Sí / Parcial / No) | Evidencia / Observación |
|---|---|---|
| Visibilidad del estado del sistema | ... | ... |
| Coincidencia con el mundo real | ... | ... |
| Control y libertad del usuario | ... | ... |
| Consistencia y estándares | ... | ... |
| Prevención de errores | ... | ... |
| Reconocimiento sobre recuerdo | ... | ... |
| Flexibilidad y eficiencia | ... | ... |
| Diseño estético y minimalista | ... | ... |
| Ayuda para reconocer errores | ... | ... |
| Ayuda y documentación | ... | ... |

### 5.2 — Evaluación orientada al público objetivo
Responder con evidencia concreta:
- ¿El diseño es apropiado para el nivel técnico del usuario final?
- ¿El lenguaje visual y textual es comprensible para ese usuario?
- ¿Se hizo alguna prueba con un usuario real (aunque sea informal)? ¿Qué feedback se obtuvo?

## Sección 6 — Evaluación de Ciberseguridad
No se requiere un informe de pentesting profesional. Se requiere conciencia de los riesgos y evidencia de que se pensó en seguridad durante el desarrollo.

**Log de consideraciones de seguridad** (mínimo 4 filas):

| Riesgo identificado | Tipo (OWASP / privacidad / acceso) | Medida implementada o decisión tomada |
|---|---|---|
| Inyección de prompt en el modelo IA | Prompt injection | Se limitó el contexto que el usuario puede modificar |
| Exposición de API keys | Secretos en código | Variables de entorno / .env ignorado en git |
| Datos de usuarios almacenados | Privacidad | Solo se guarda X, no se guarda Y |
| Acceso no autorizado | Autenticación | Se implementó / no se implementó (y por qué) |

## Sección 7 — IAs usadas en el co-work de desarrollo

| Herramienta IA | Para qué la usaron | Aportó bien / mal / sorprendió |
|---|---|---|
| Claude | Generar el backend / revisar código | ... |
| Gemini | Diseño de interfaces / diagramas | ... |
| ChatGPT | ... | ... |
| Cursor / Copilot | Autocompletado de código | ... |

**Reflexión obligatoria (1 párrafo):** ¿Qué parte del desarrollo hubiera sido imposible o hubiera tomado el doble de tiempo sin el co-work con IA? ¿Qué parte la IA hizo mal y tuvieron que corregir?

---

# PARTE 2 — IA local en tu proyecto

**Contexto**: un LLM local (Ollama + LLaMA, Mistral, Phi-3) o un SLM (Small Language Model: Phi-3 Mini, Gemma 2B) corre completamente en tu computadora o servidor. No envía datos a la nube. No tiene costo por token. Funciona sin internet.

Un SLM en tu organización puede ser la diferencia entre una herramienta que procesa datos sensibles de clientes y una que no puede usarse por cuestiones legales o de privacidad.

**Preguntas a responder (mínimo 1 párrafo cada una):**
1. ¿Qué papel jugaría un LLM/SLM local en tu proyecto?
   - ¿Reemplazaría algún componente IA que hoy usa una API externa?
   - ¿Haría algo nuevo que no podías hacer antes (por costo, privacidad, velocidad)?
   - ¿Sería el agente principal, un subagente específico, o un componente de soporte?
2. ¿Qué le aportaría al usuario de la aplicación?
   - ¿Mejora la experiencia de usuario? ¿De qué manera concreta?
   - ¿Hace la aplicación más rápida, más privada, más económica?
   - ¿Cambia lo que el usuario puede pedirle al sistema?
3. ¿Qué te aportaría a vos como profesional?
   - ¿Qué información nueva sobre el negocio o el usuario te daría tener el modelo local?
   - ¿Podrías analizar logs, comportamientos, patrones que hoy no podés ver porque los datos no pueden salir de la organización?
   - ¿Cómo cambiaría tu forma de trabajar día a día con esa herramienta disponible offline?
4. ¿Qué limitaciones concretas tiene versus una API en la nube?
   - Capacidad del hardware disponible
   - Calidad del modelo para tu caso de uso específico
   - Mantenimiento y actualización del modelo

**Entregable opcional (sube la nota):**
Instalar Ollama en la computadora del equipo, correr un modelo (Llama3.2, Phi3, Gemma2) y mostrar una captura de pantalla de la terminal con el modelo respondiendo una pregunta relacionada con el proyecto. Una línea explicando qué pregunta le hicieron y qué respondió.

---

# CRITERIOS DE EVALUACIÓN

| Criterio | Peso | Lo mínimo para aprobar |
|---|---|---|
| App funcionando y demostrable | **30%** | Existe, hace algo útil, se puede mostrar |
| Arquitectura documentada (diagrama + tabla stack) | **20%** | Al menos 1 diagrama + tabla completa |
| Evaluación UX/UI (heurísticas + público objetivo) | **20%** | 5 heurísticas evaluadas + 1 párrafo de público |
| Ciberseguridad (log de riesgos) | **10%** | 4 riesgos identificados con medida tomada |
| Parte 2 — IA local (reflexión fundamentada) | **20%** | Las 4 preguntas respondidas con criterio propio |

# FORMATO DE ENTREGA
- **Formato**: Presentación (PowerPoint, Slides, Canva) o documento (Word, PDF)
- **Extensión**: sin límite, pero sin relleno. Cada sección debe tener contenido real.
- **Modalidad**: exposición oral de 10 minutos + 5 minutos de preguntas del docente
- **Advertencia directa**: una presentación que dice "nuestra app hace X" pero no muestra X funcionando no aprueba la Parte 1. La evidencia es obligatoria.

# LINKS OBLIGATORIOS (primera página del informe)
El informe debe comenzar con una tabla de acceso directo. El docente evaluará directamente en estos links, no en el PDF.

| Recurso | URL |
|---|---|
| Repositorio GitHub / GitLab | https://github.com/... |
| Aplicación web en producción | https://... |
| Video de demo (YouTube / Drive) | https://... |
| Cualquier otro recurso publicado | https://... |

**Sin links válidos y funcionales al momento de la corrección, la entrega no se aprueba.**

# ENTREGA — Especificación de documentos
| Ítem | Especificación |
|---|---|
| Informe principal | PDF — 10 a 20 páginas — solo la información esencial |
| Anexos | docx o PDF — sin límite de páginas — diagramas, logs, tablas completas |
| Lo que se evalúa | El repositorio GitHub/GitLab y el sitio web publicado en vivo |

El informe PDF no es el producto final. Es el índice que guía al docente hacia el trabajo real publicado en la web o en el repositorio.

El docente abrirá los links de la primera página y evaluará:
- Que el repositorio tenga commits reales (historia de trabajo, no un solo commit con todo)
- Que el sitio web o la app esté funcionando al momento de la corrección
- Que el README del repositorio explique el proyecto con claridad

**Advertencia directa**: un repositorio vacío, privado, o con un solo commit el día de la entrega no aprueba. La historia de commits es evidencia del proceso de trabajo.