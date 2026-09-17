# -*- coding: utf-8 -*-
"""Genera el HTML del informe de entrega del TP (UTN) para convertir a PDF.

Uso:  Venv\\Scripts\\python.exe TP\\generar_entrega_html.py
Salida: TP\\Entrega_Final_TP.html
PDF (opcional, con Edge headless):
  & "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" ^
      --headless --disable-gpu --print-to-pdf="TP\\Entrega_Final_TP.pdf" ^
      "file:///.../TP/Entrega_Final_TP.html"

Replica el contenido de generar_entrega.py (docx) con el estilo visual del
manual de uso de la app (Tailwind CDN + paleta brand #007AC3, modo claro).
Las capturas se incrustan desde TP/capturas/ como <img> reales; los
diagramas se incrustan si existe diagramas/<base>.png y si no se deja un
marcador con la referencia al .mmd (igual que hace el docx).
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE_DIR, "Entrega_Final_TP.html")
CAPTURAS = "capturas"
DIAGRAMAS = "diagramas"

TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trabajo de Fin de Ciclo — Sistema de Incidencias con análisis IA</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {
    theme: {
      extend: {
        colors: {
          brand: {
            50:  '#E8F5FE', 100: '#D3EBFD', 200: '#A6D6FA', 300: '#70BCF0',
            400: '#3FA0E4', 500: '#1488D3', 600: '#007AC3', 700: '#00639E',
            800: '#005080', 900: '#003E63', 950: '#00304F'
          }
        }
      }
    }
  }
</script>
<style>
  @media print {
    body { background: #f3f4f6 !important; }
    .page-break { page-break-before: always; }
    /* salto antes de una sección principal: se aplica al h2, no a un div vacío
       (los divs vacíos con page-break-before generan páginas en blanco en Chromium
       cuando la sección anterior llenó la página) */
    h2.page-before { page-break-before: always; }
    img, figure, table { page-break-inside: avoid; }
    h3, h4 { page-break-after: avoid; }
    .caja-junta { page-break-inside: avoid; }
    /* El log de sesión debe fluir entre páginas sin recortarse */
    .log-sesion { overflow: visible !important; }
    /* Líneas muy largas del log se cortan (no ensanchan la página → previene
       que el navegador escale todo el documento para "fit to page") */
    .log-sesion pre { white-space: pre-wrap; overflow-wrap: anywhere; }
    /* Diagramas: alto máximo para que título + texto + figura entren en una
       sola página del PDF (solo aplica a los diagramas estructurales). */
    .fig-diagrama img { max-height: 520pt; width: auto; max-width: 100%;
                        display: block; margin: 0 auto; }
  }
</style>
</head>
<body class="bg-gray-100 text-gray-900 antialiased print:bg-gray-100">

<main class="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6">

  <!-- ============================ PORTADA ============================ -->
  <div class="rounded-xl border border-gray-200 bg-white p-8 sm:p-10">
    <p class="text-sm font-semibold tracking-wide text-gray-500 uppercase">Inteligencia Artificial aplicada a organizaciones</p>
    <h1 class="mt-2 text-3xl font-bold text-brand-700">Trabajo de Fin de Ciclo</h1>
    <p class="mt-1 text-lg font-semibold text-gray-700">Entrega final de proyecto — Sistema de Gestión de Incidencias con análisis IA</p>
    <p class="mt-3 text-sm text-gray-600">UTN FRBA — Curso de Inteligencia Artificial para Programadores</p>
    <div class="mt-6 space-y-1 text-sm text-gray-700">
      <p><span class="text-gray-400">Grupo:</span> {GRUPO}</p>
      <p><span class="text-gray-400">Repositorio:</span> <a class="text-brand-700 underline" href="https://github.com/patosimple/Incidencias">https://github.com/patosimple/Incidencias</a></p>
    </div>
  </div>

  <!-- ========================= LINKS OBLIGATORIOS ========================= -->
  <div class="rounded-xl border border-gray-200 bg-white p-6">
    <h2 class="text-lg font-bold text-brand-700">Links de acceso directo (válidos al momento de la corrección)</h2>
    {LINKS_TABLA}
  </div>

  <!-- ============================ PARTE 1 ============================ -->
  <div class="rounded-xl bg-brand-800 px-6 py-4">
    <h2 class="text-xl font-bold text-white">PARTE 1 — El proyecto como aplicación real</h2>
  </div>

  {PARTE1}

  <!-- ============================ PARTE 2 ============================ -->
  <div class="rounded-xl bg-brand-800 px-6 py-4">
    <h2 class="text-xl font-bold text-white">PARTE 2 — IA local en tu proyecto</h2>
  </div>

  {PARTE2}

</main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers de render
# ---------------------------------------------------------------------------

def _tabla_thead(encabezados):
    return ("<table class='w-full text-left text-sm border-collapse'>"
            "<thead><tr class='bg-brand-600 text-white'>"
            + "".join(f"<th class='px-3 py-2 font-semibold'>{h}</th>" for h in encabezados)
            + "</tr></thead>")


def _tabla_body(filas):
    rows = []
    for fila in filas:
        cells = "".join(f"<td class='px-3 py-2 align-top'>{c}</td>" for c in fila)
        rows.append(f"<tr class='border-b border-gray-200 even:bg-gray-50'>{cells}</tr>")
    return "<tbody>" + "".join(rows) + "</tbody></table>"


def _tabla(encabezados, filas):
    return _tabla_thead(encabezados) + _tabla_body(filas)


def _h1(texto, page_before=False):
    cls = "page-before " if page_before else ""
    return f"<h2 class='{cls}text-2xl font-bold text-brand-700 mt-2'>{texto}</h2>"


def _h2(texto, page_before=False):
    cls = "page-before " if page_before else ""
    return f"<h3 class='{cls}text-xl font-bold text-brand-700 mt-6'>{texto}</h3>"


def _h3(texto):
    return f"<h4 class='text-base font-bold text-gray-800 mt-4'>{texto}</h4>"


def _p(texto, italic=False, bold=False):
    cls = "text-sm text-gray-700 leading-relaxed mt-3"
    if italic:
        cls += " italic text-gray-500"
    if bold:
        cls += " font-semibold"
    return f"<p class='{cls}'>{texto}</p>"


def _card(inner, clases="rounded-xl border border-gray-200 bg-white p-6"):
    return f"<div class='{clases} mt-4'>{inner}</div>"


def _junta(*fragmentos):
    """Envuelve varios fragmentos en un contenedor que no se parte entre páginas
    en el PDF (título + figura/diagrama quedan juntos)."""
    return "<div class='caja-junta'>" + "\n".join(fragmentos) + "</div>"


def _diagrama(archivo, titulo):
    """Si existe diagramas/<base>.png se incrusta; si no, marcador gris (vuelca el .mmd)."""
    base = archivo.rsplit(".", 1)[0]
    png = os.path.join(BASE_DIR, DIAGRAMAS, f"{base}.png")
    if os.path.exists(png):
        rel = f"{DIAGRAMAS}/{base}.png"
        return (f"<figure class='fig-diagrama mt-4'>"
                f"<img src='{rel}' alt='{titulo}' class='w-full h-auto rounded-lg border border-gray-200'>"
                f"<figcaption class='mt-1 text-xs text-gray-500 italic'>{titulo}</figcaption>"
                f"</figure>")
    # Marca de agua si el PNG no está generado
    src = os.path.join(BASE_DIR, DIAGRAMAS, archivo)
    cuerpo = "Generar el PNG en https://mermaid.live y guardarlo como "
    if os.path.exists(src):
        with open(src, "r", encoding="utf-8") as f:
            cuerpo = f.read()
    pre = "".join(f"{ln}<br>" for ln in cuerpo.splitlines())
    return (f"<div class='mt-4 rounded-lg border border-dashed border-gray-400 bg-gray-50 p-4'>"
            f"<p class='text-xs font-bold text-gray-500 uppercase'>{titulo}</p>"
            f"<p class='text-xs text-gray-400 mt-1'>Fuente Mermaid: diagramas/{archivo} "
            f"(todavía sin PNG — ofuscado a modo de marcador)</p>"
            f"<pre class='mt-2 text-[10px] leading-tight text-gray-400 whitespace-normal'>{pre}</pre>"
            f"</div>")


def _captura(archivo, pie):
    """Incrusta captura real o deja marcador gris."""
    png = os.path.join(BASE_DIR, CAPTURAS, archivo)
    if os.path.exists(png):
        rel = f"{CAPTURAS}/{archivo}"
        return (f"<figure class='mt-4 rounded-lg border border-gray-200 overflow-hidden'>"
                f"<img src='{rel}' alt='{pie}' class='w-full h-auto'>"
                f"<figcaption class='px-3 py-2 text-xs text-gray-500 bg-gray-50 border-t border-gray-200'>{pie}</figcaption>"
                f"</figure>")
    return (f"<div class='mt-4 rounded-lg border border-dashed border-gray-400 bg-gray-50 p-4'>"
            f"<p class='text-xs font-bold text-gray-500 uppercase'>Falta la captura {archivo}</p>"
            f"<p class='text-xs text-gray-400 mt-1'>Se necesita TP/capturas/{archivo}.</p>"
            f"</div>")


def _log_sesion():
    txt = os.path.join(BASE_DIR, "log_sesion.txt")
    if not os.path.exists(txt):
        return ("<div class='mt-4 rounded-lg border border-dashed border-gray-400 bg-gray-50 p-4'>"
                "<p class='text-xs font-bold text-gray-500'>LOG DE SESIÓN — falta TP/log_sesion.txt "
                "(generar con generar_log_sesion.py)</p></div>")
    with open(txt, "r", encoding="utf-8") as f:
        lineas = [ln.rstrip() for ln in f]
    pre = "".join(f"{ln}<br>" for ln in lineas)
    return (f"<div class='log-sesion mt-4 rounded-lg bg-slate-900 text-slate-200 p-4 font-mono text-[10px] "
            f"leading-tight'><pre>{pre}</pre></div>")


# ---------------------------------------------------------------------------
# Secciones Parte 1
# ---------------------------------------------------------------------------

def _parte1():
    out = []

    # ------------------------------------------------------------ seccion 1
    out.append(_h2("1. Presentación del equipo y del proyecto"))
    out.append(_p("<strong>Integrantes del grupo (nombre, rol en el desarrollo):</strong>"))
    out.append(_card(_p("[COMPLETAR por integrante]")))
    out.append(_junta(
        _h3("Nombre del proyecto"),
        _p("Sistema de Gestión de Incidencias de TI (tickets) con análisis IA asistido."),
    ))
    out.append(_junta(
        _h3("Problema que resuelve"),
        _p("Gestión interna de bugs y requerimientos sobre dos aplicaciones de negocio "
           "(Balances y Financiamiento político). Centraliza el reporte, el seguimiento, "
           "la toma colaborativa, el cambio de estado y el cierre de incidentes, e incorpora "
           "una capa de análisis IA que asiste a desarrolladores y coordinadores a entender "
           "el problema reportado."),
    ))
    out.append(_junta(
        _h3("Público objetivo"),
        _p("Usuarios internos de la organización: (a) solicitantes (usuarios de negocio que "
           "reportan incidencias sin acceso a detalles técnicos), (b) desarrolladores que "
           "atienden los tickets de sus sistemas, y (c) coordinadores que supervisan el flujo. "
           "El admin/superuser gestiona usuarios, accesos y configuración de IA."),
    ))

    # ------------------------------------------------------------ seccion 2
    out.append(_h2("2. Arquitectura técnica", page_before=True))
    out.append(_junta(
        _h3("Diagrama de arquitectura general"),
        _p("Componentes IA vs lógica tradicional: el núcleo de tickets (crear, listar, comentar, "
           "estados, permisos, adjuntos) es lógica tradicional Django. La única componente IA es "
           "el módulo de análisis de incidencias (ai/), que se dispara manualmente."),
        _diagrama("arquitectura.mmd", "Arquitectura general"),
    ))
    out.append(_junta(
        _h3("Diagrama de flujo de agentes"),
        _p("El proyecto como aplicación NO incluye orquestación multi-agente en producción: el "
           "análisis IA es un paso puntual y manual. El trabajo de desarrollo sí se apoyó en "
           "esquemas de IA, alternando dos modalidades: opencode (CLI) con cambio de agente "
           "manual por tarea, y Antigravity (IDE) con Gemini como orquestador sobre un multiMCP "
           "adaptado para usar rotación interna de API keys y proveedores. El diagrama siguiente "
           "representa esta metodología (las partes de la app están cubiertas en los diagramas "
           "funcionales)."),
        _diagrama("agentes_desarrollo.mmd", "Flujo de agentes (metodología de desarrollo)"),
    ))
    out.append(_junta(
        _h3("Flujo de estados del ticket"),
        _diagrama("estados_ticket.mmd", "Flujo de estados del ticket"),
    ))
    out.append(_junta(
        _h3("UML — Diagrama de clases"),
        _diagrama("clases.mmd", "Diagrama de clases (modelo de datos)"),
    ))
    out.append(_junta(
        _h3("UML — Casos de uso"),
        _diagrama("casos_de_uso.mmd", "Casos de uso por rol"),
    ))
    out.append(_junta(
        _h3("UML — Secuencia del análisis IA"),
        _diagrama("secuencia_analisis_ia.mmd", "Secuencia del análisis IA"),
    ))

    # ------------------------------------------------------------ seccion 3
    out.append(_h2("3. Stack tecnológico", page_before=True))
    out.append(_card(_tabla(
        ["Componente", "Tecnología / Herramienta", "Por qué esta y no otra"],
        [
            ["Frontend",
             "Templates Django + HTMX + Tailwind (CDN), dark mode",
             "HTMX permite interacciones parciales sin SPA ni JS pesado; Tailwind da consistencia "
             "rápida con paleta de marca y responsive; CDN evita build complejo. Se eligió sobre "
             "React/Vue por simplicidad de mantenimiento server-rendered en un equipo chico."],
            ["Backend",
             "Python Django 5.2 + Gunicorn + Whitenoise",
             "Django trae ORM, admin, auth y seguridad (CSRF, login) maduros; Python es el stack del "
             "curso y el idóneo para integrar APIs de IA. Whitenoise sirve estáticos sin servidor aparte."],
            ["Base de datos",
             "PostgreSQL (Neon/Supabase)",
             "Postgres por integridad (constraints, unique_together, índices) y por pgvector (plan RAG "
             "futuro). Neon gratis y con SSL. Almacenamiento de adjuntos persistido en Supabase Storage "
             "(S3, ver Despliegue). No SQLite porque el deploy en Render usa disco efímero y la app corre "
             "persistida en la nube."],
            ["Modelo de IA",
             "Multi-proveedor OpenAI-compatible: Groq, Gemini, OpenRouter, NVIDIA; Ollama local. "
             "Activo: qwen/qwen3.8-27b (Groq).",
             "Abstracción en ai/providers.py con un único contrato HTTP; permite probar el modelo activo "
             "o caer a Ollama local (privacidad). Groq como activo por latencia baja del free tier."],
            ["Orquestación",
             "Código propio + Huey (cola de tareas; hoy síncrono con immediate=True)",
             "Sin LangChain: la fachada IA es simple y completa (mensajes, formato, reintentos). "
             "Huey+PostgresHuey para no sumar Redis al proyecto: usa la misma base de datos."],
            ["Despliegue",
             "Render (Gunicorn) + Neon (Postgres) + Supabase Storage (S3)",
             "Render gratis con deploy por git; Neon gratis sin tarjeta. Los adjuntos van a un bucket S3 "
             "privado de Supabase Storage (URLs firmadas 5 min): el disco de Render es efímero y cada "
             "redeploy perdería los archivos, por eso se resolvió con storage en la nube (decisión "
             "16/09/2026). Local (DEBUG) usa FileSystemStorage en media/."],
        ],
    )))

    # ------------------------------------------------------------ seccion 4
    out.append(_h2("4. Evidencia de funcionamiento", page_before=True))
    out.append(_h3("Capturas de pantalla (mínimo 3)"))
    out.append(_p("Las siguientes capturas son pantallas reales de la aplicación desplegada (logeo con un "
                  "usuario del seed). Cubren el mínimo exigido por la consigna: pantalla principal/home, "
                  "el flujo de uso principal y el resultado del output de IA visible para el usuario."))
    out.append(_junta(
        _p("(a) Pantalla principal / home — listado de tickets con filtros, paginador e indicador "
          "de novedades:", italic=True),
        _captura("02_listado_desktop.png", "Listado de tickets (home) — rol Desarrollador, tema claro."),
    ))
    out.append(_junta(
        _p("(b) Flujo de uso principal — creación de ticket con editor enriquecido y adjuntos:",
           italic=True),
        _captura("04_crear_ticket.png", "Creación de ticket (form + editor Quill + lista de adjuntos)."),
    ))
    out.append(_junta(
        _p("(c) Resultado / output de la IA visible para el usuario — sección Análisis IA en el "
           "detalle:", italic=True),
        _captura("11_analisis_ia.png", "Detalle del ticket con la sección Análisis IA expandida "
                 "(cards de resultado generado por el LLM)."),
    ))
    out.append(_junta(
        _h3("Video de demostración (opcional)"),
        _p("[COMPLETAR enlace si aplica — max 3 min]"),
    ))
    out.append(_junta(
        _h3("Log de una sesión real"),
        _p("Se incluye en anexo: línea de tiempo de una ejecución completa extraída de la base de "
           "datos real (tickets + comentarios + análisis IA con proveedor/modelo/versión de prompt)."),
        _log_sesion(),
    ))

    # ------------------------------------------------------------ seccion 5
    out.append(_h2("5. Evaluación UX/UI", page_before=True))
    out.append(_h3("5.1 Heurísticas de Nielsen aplicadas al proyecto"))
    out.append(_card(_tabla(
        ["Heurística", "¿Cumple?", "Evidencia / Observación"],
        [
            ["Visibilidad del estado del sistema", "Sí",
             "Badges de estado coloreados en listado y detalle (PENDIENTE rojo, EN_PROCESO verde, CERRADO "
             "gris, REABIERTO); el color distingue si lo tomó el usuario u otro (verde=yo, azul=otro, "
             "rojo=sin tomar). Toasts/flash con feedback; spinner + barra de progreso real en adjuntos."],
            ["Coincidencia con el mundo real", "Sí",
             "Lenguaje del dominio en español (tickets, sistema, solicitante, colaborador); el usuario no "
             "ve internals; etiquetas claras en forms y botones con verbos (Tomar, Liberar, Cerrar, "
             "Reabrir, Analizar)."],
            ["Control y libertad del usuario", "Sí",
             "Cancelar en todos los forms; quitar adjuntos antes de subir; editar/eliminar comentarios y "
             "ticket propio; liberar/reabrir para corregir errores; los enlaces vuelven al listado; "
             "limpiar filtros."],
            ["Consistencia y estándares", "Sí",
             "Paleta brand única (#007AC3) en toda la app, dark mode coherente, partials reutilizables "
             "(badges, cards, página de ticket), mismos patrones de botones por estado, misma metodología "
             "de filtros en listado."],
            ["Prevención de errores", "Sí",
             "Validación client-side al seleccionar adjuntos (10MB + whitelist de extensiones con toast), "
             "validación de form antes de enviar, botones destructivos con confirmación (SweetAlert2), "
             "bloquear submit durante upload, botones contextuales (no aparece 'Tomar' si ya colabora)."],
            ["Reconocimiento sobre recuerdo", "Sí",
             "Selects con label placeholder (Sistema/Estado/Colaborador/Novedades), puntito de novedad por "
             "fila, filtro 'Tomado' para devs, badges que se explican solos; el usuario no necesita "
             "recordar valores."],
            ["Ayuda y documentación", "Sí",
             "Manual de uso dentro de la app (/manual/) con 18 secciones colapsables, TOC de anclas y "
             "visibilidad por rol (solicitante ve solo lo general; dev/coord suma toma/IA; staff suma "
             "admin); FAQs incluidas. Mensajes de error claros en español."],
        ],
    )))
    out.append(_h3("5.2 Evaluación orientada al público objetivo"))
    out.append(_p("Diseño apropiado para el nivel técnico: el solicitante no ve internals (ni análisis IA "
                  "ni toma colaborativa); devs/coord ven las herramientas de gestión sin fricción."))
    out.append(_p("Lenguaje visual/textual comprensible: español de negocio, no jerga de backend; hint de "
                  "adjuntos y textos de acción verbales. El análisis IA pide solo información que el "
                  "usuario podría aportar (pantalla, pasos, mensaje de error, frecuencia, OS)."))
    out.append(_p("Prueba con usuario real: se corrieron escenarios reales con el usuario y de ahí salieron "
                  "decisiones de UX concretas: toasts para mutaciones in-place (comentarios) vs flash tag "
                  "cuando hay navegación; límite de adjuntos en 10 MB (los informes llegan hasta ~6 MB); "
                  "indicador de novedades como puntito azul (en vez de badge) con toggle en el header; no "
                  "mostrar 'información faltante' del análisis IA (sin valor para el lector técnico); "
                  "filtros con label placeholder en español."))

    # ------------------------------------------------------------ seccion 6
    out.append(_h2("6. Evaluación de Ciberseguridad", page_before=True))
    out.append(_card(_tabla(
        ["Riesgo identificado", "Tipo (OWASP/privacidad/acceso)", "Medida implementada"],
        [
            ["Inyección de prompt en el modelo IA", "Prompt injection",
             "Prompt separado system/user; el user declara que la descripción del ticket es SOLO dato "
             "(puede contener órdenes) que se ignoran; bloque delimitado con \"\"\" y defensa explícita "
             "en system; el título también se protege. Ninguna instrucción dentro de la descripción "
             "modifica la tarea/reglas/formato."],
            ["Exposición de API keys", "Secretos en código",
             "Keys en .env (ignorado en git) propagadas a os.environ en settings; nunca hardcodeadas; "
             ".env.example commiteado solo con placeholders."],
            ["Datos de usuarios almacenados", "Privacidad",
             "Modelo mínimo: username, rol, accesos a sistemas; no se guardan datos sensibles extra; "
             "contraseñas hasheadas por Django; el análisis IA con datos de Financiamiento político puede "
             "correr 100% local con Ollama para no salir de la org."],
            ["Acceso no autorizado (autenticación/autorización)", "Acceso",
             "Login obligatorio (LOGIN_URL), permisos por rol (solicitante ve solo sus tickets; dev ve sus "
             "sistemas), verificación server-side (403/404) en tomar/cerrar/reabrir/comentar/analizar; "
             "superuser con bypass controlado; soft-delete conserva auditoría. Se implementó "
             "integralmente."],
            ["XSS en contenido del ticket/comentarios", "OWASP A3",
             "Sanitización nh3 al guardar (whitelist de tags/atributos Quill) en crear/editar ticket y "
             "comentarios; render con |safe es seguro porque el input llega ya saneado; tests E2E de XSS "
             "automatizados (XssVistaTest)."],
            ["Adjuntos maliciosos", "OWASP A1 (mayormente)",
             "Whitelist de extensiones (imágenes, office, comprimidos) — excluidos ejecutables, .svg, "
             "macros de Office y html/xml; límite de 10MB por archivo con validación client y server."],
            ["CSRF / sesión", "OWASP A1/A8",
             "CSRF middleware activo y token en todos los forms POST (incluidos los HTMX); logout por POST."],
        ],
    )))

    # ------------------------------------------------------------ seccion 7
    out.append(_h2("7. IAs usadas en el co-work de desarrollo", page_before=True))
    out.append(_p("El desarrollo se hizo en dos esquemas combinados: (1) esquema multi-agente con "
                  "Antigravity + Gemini como orquestador + un multiMCP adaptado para usar rotación interna "
                  "de API keys y proveedores; y (2) opencode como CLI con cambio de agente manual por "
                  "tarea. Ambas modalidades se alternaron a lo largo del desarrollo y se complementaron "
                  "(no hay un reparto de features por esquema: el mismo hito se pudo abordar desde "
                  "cualquiera de las dos). El contexto original del proyecto quedó documentado en el "
                  "archivo AGENTS.md dentro del repositorio, que ambas herramientas leyeron y actualizaron; "
                  "así el paso de un esquema al otro no perdía la memoria del desarrollo (conceptos, "
                  "decisiones y pendientes)."))
    out.append(_card(_tabla(
        ["Herramienta IA", "Para qué la usaron", "Aportó"],
        [
            ["Claude (claude.ai, chat)",
             "Planificación y diseño del sistema (entidades, flujos, esquema de datos) directamente desde "
             "el chat de claude.ai, y allí mismo generó el proyecto Django inicial listo para trabajar: "
             "estructura del proyecto, modelos, urls y views iniciales, archivos docker y requirements.txt, "
             "entregados como .zip.",
             "Bien: el andamiaje completo del proyecto quedó definido y descargable desde el arranque y "
             "consistente con el diseño planificado; sobre esa base luego se trabajó con Antigravity "
             "(multi-agente) y opencode (agentes manuales)."],
            ["Antigravity + Gemini (orquestador multi-agente) + multiMCP adaptado con rotación interna de "
             "API keys y proveedores",
             "Desarrollo de parte del código con esquema multi-agente: varios agentes orquestados por "
             "Gemini para generar features del backend y frontend.",
             "Bien: permitió encarar el desarrollo con agentes especializados coordinados por un "
             "orquestador. Limitaciones del multiMCP: en la sesión de prueba varios proveedores fallaron "
             "(modelos deprecados, carrusel de proveedores sin saldo, 404/410 en NVIDIA), por lo que el "
             "trabajo se terminó combinando con opencode manual."],
            ["opencode (CLI, agentes manuales)",
             "Generar backend Django, forms, vistas, templates (Tailwind/HTMX/Quill), capa IA "
             "multi-proveedor, tests automatizados, debugging",
             "Bien: velocidad de generación de estructura completa y consistente; revisión de bugs con "
             "repro (p.ej. scroll de SweetAlert2, orden de serialización HTMX). Mal: a veces generaba "
             "código con errores sutiles (p.ej. {# #} multilínea renderizado literal, orden de listeners "
             "HTMX) que hubo que corregir con tests."],
            ["GitHub/Git (historial de commits)",
             "Evidencia del proceso real de trabajo incremental",
             "Bien: historia de commits real es requisito de evaluación."],
        ],
    )))
    out.append(_h3("Reflexión obligatoria"))
    out.append(_p("Sin el co-work con IA el desarrollo hubiera tomado al menos el doble de tiempo: la capa "
                  "IA multi-proveedor (providers OpenAI-compatible con formato de salida por modelo, prompt "
                  "anti prompt-injection, escalera de degradación por contexto), la suite de ~65 tests "
                  "automatizados (XSS, adjuntos, transiciones, novedades, permisos; más de 120 al cierre) y "
                  "los fixes finos de UX (scroll del SweetAlert2, orden de serialización HTMX, barra de "
                  "progreso real en adjuntos). La IA también falló y esas fallas se corrigieron: un "
                  "comentario multilínea {# #} de Django que se renderizaba literal, incidentes de orden de "
                  "listeners HTMX que a veces no actualizaban el detalle, y garantías de XSS inexistentes "
                  "que los propios tests delataron (el render |safe solo es seguro si el input se sanea al "
                  "entrar). Sobre los esquemas: el multi-agente (Antigravity/Gemini) ayudó a encarar el "
                  "código con agentes especializados coordinados, pero su dependencia del carrusel de "
                  "proveedores resultó frágil en la sesión de prueba; el cambio manual de agente en opencode "
                  "dio más control y trazabilidad del trabajo por tarea, y fue el esquema con el que se "
                  "terminaron de consolidar las features y los tests."))

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Secciones Parte 2
# ---------------------------------------------------------------------------

def _parte2():
    out = []
    out.append(_p("Nota: la aplicación ya incorpora Ollama como proveedor local (formato NATIVO, sin "
                  "key). Como contexto del análisis, el prompt se arma con la descripción del ticket, la "
                  "descripción oficial del sistema (Sistema.prompt) y el manual de uso del sistema en "
                  "texto plano (manuales_rag/&lt;codigo&gt;, leído al momento de analizar). Se evaluaron "
                  "dos variantes para incorporar los manuales: RAG vectorial (embeddings locales con "
                  "nomic-embed-text + pgvector) y enviar el manual completo en el prompt. Se eligió esta "
                  "última porque los manuales son acotados (BALANCES ~24 KB, FINANCIAMIENTO ~16 KB, "
                  "~10-12K tokens) y entran enteros en el contexto: el modelo ve todo el contenido, sin "
                  "riesgo de fragmentos mal seleccionados por similitud; además evita pgvector, el "
                  "pipeline de indexado y la carga de un modelo de embeddings en Ollama por análisis. El "
                  "RAG quedó documentado como plan para escalar a manuales grandes."))

    out.append(_h2("Pregunta 1 — Qué papel jugaría un LLM/SLM local"))
    out.append(_p("Reemplazaría (o complementaría) la API externa para escenarios sensibles: los tickets "
                  "de Financiamiento político no deberían salir de la organización. El provider Ollama ya "
                  "existe en la app: cambiando el modelo activo (ConfiguracionIA) el análisis corre local. "
                  "Hoy el contexto del análisis ya incluye el manual de uso del sistema (txt completo, sin "
                  "que los datos salgan de la org); a futuro podría sumarle embeddings locales "
                  "(nomic-embed-text) para RAG sobre esos manuales. Sería un componente de soporte "
                  "intercambiable, no el agente principal."))

    out.append(_h2("Pregunta 2 — Qué le aportaría al usuario"))
    out.append(_p("Privacidad (los datos sensibles no salen de la org), cero costo por token y "
                  "funcionamiento offline. En experiencia, permitiría ofrecer el análisis como garantía "
                  "por defecto para incidencias de sistemas sensibles, sin depender del estado de un "
                  "proveedor externo."))

    out.append(_h2("Pregunta 3 — Qué te aportaría a vos como profesional"))
    out.append(_p("Analizar logs/comportamientos de incidencias y patrones de reportes sin necesidad de "
                  "que los datos salgan de la organización; probar el pipeline de IA offline; el modelo "
                  "local corre con el mismo código (mismo prompt y formato de salida), lo que permite "
                  "desarrollo sin keys ni costo y validar privacidad ante el cliente."))

    out.append(_h2("Pregunta 4 — Limitaciones concretas vs API en la nube"))
    out.append(_p("Comparación de tiempos de análisis local vs nube (medido sobre un ticket real con el "
                  "prompt completo y el manual del sistema; [COMPLETAR con las mediciones reales]): el "
                  "análisis con Ollama local (qwen2.5:3b-instruct-q4_K_M, ~6 tok/s de decode) tarda "
                  "[T_LOCAL — ~90-120s] vs la API en la nube (Groq, qwen/qwen3.8-27b) que tarda "
                  "[T_NUBE — pocos segundos]. La implementación final está prevista sobre un servidor de "
                  "la organización con características superiores a los equipos de desarrollo, lo que "
                  "reduce la brecha de rendimiento. La calidad del modelo local de ~3B es inferior a la de "
                  "los ~27B de Groq para el caso de uso específico. Mantenimiento (actualizar el modelo, "
                  "ollama pull) recae en el equipo local. No conviene para volumen alto ni para tareas "
                  "globales largas."))

    out.append(_h2("Entregable opcional — captura de Ollama local"))
    out.append(_p("[COMPLETAR captura tras ejecutar, p.ej.:]"))
    out.append(_card(_p("Comando: <code class='text-brand-700'>ollama run qwen2.5:3b</code>", bold=True)
                       + _p("Pregunta: \"En una organización que gestiona incidencias de Financiamiento "
                            "político, qué ventajas y riesgos tiene analizar esas incidencias con un LLM "
                            "local versus una API en la nube?\"", italic=True)
                       + _p("Respuesta (1 línea): [COMPLETAR lo que respondió el modelo]")))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    html = TEMPLATE.replace("{GRUPO}", "[COMPLETAR nombre/rol de cada integrante]")
    html = html.replace("{LINKS_TABLA}", _tabla(
        ["Recurso", "URL"],
        [
            ["Repositorio GitHub", "<a class='text-brand-700 underline' href='https://github.com/patosimple/Incidencias'>https://github.com/patosimple/Incidencias</a>"],
            ["Aplicación en producción", "<a class='text-brand-700 underline' href='https://incidencias.onrender.com'>https://incidencias.onrender.com</a>"],
            ["Video demo", "[COMPLETAR enlace — max 3 min]"],
            ["Otros recursos publicados", "[COMPLETAR si aplica — p.ej. el manual de uso /admin de la app]"],
        ],
    ))
    html = html.replace("{PARTE1}", _parte1())
    html = html.replace("{PARTE2}", _parte2())

    out = OUT
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML generado:", out)


if __name__ == "__main__":
    main()