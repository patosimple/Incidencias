# -*- coding: utf-8 -*-
"""Genera el documento Word del TP de entrega (UTN) con python-docx.

Uso:  Venv\\Scripts\\python.exe TP\\generar_entrega.py
Salida: TP\\Entrega_Final_TP.docx

Los diagramas van como IMAGEN (PNG). Si existe diagramas/<base>.png se
incrusta; si no, se deja el espacio con la referencia al .mmd fuente
(la imagen se genera aparte en https://mermaid.live).
"""

import os

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

OUT = r"TP\Entrega_Final_TP.docx"

BRAND = RGBColor(0, 0x7A, 0xC3)
GRAY = RGBColor(0x66, 0x66, 0x66)


def _tabla(doc, headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        r = cell.paragraphs[0].add_run(h)
        r.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
    return t


def _titulo(doc, texto, level=1):
    h = doc.add_heading(texto, level=level)
    for r in h.runs:
        r.font.color.rgb = BRAND
    return h


def _p(doc, texto, bold=False, color=None, italic=False):
    p = doc.add_paragraph()
    r = p.add_run(texto)
    r.bold = bold
    r.italic = italic
    if color:
        r.font.color.rgb = color
    return p


def _diagrama(doc, archivo, titulo):
    """Deja el espacio para la imagen del diagrama.

    Si existe el PNG generado (diagramas/<base>.png) se incrusta; si no,
    se deja un marcador de posicion con la referencia al .mmd fuente.
    """
    base = archivo.rsplit(".", 1)[0]
    png = f"TP\\diagramas\\{base}.png"
    if os.path.exists(png):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(png, width=Inches(6.3))
        return
    _p(doc, f"DIAGRAMA IMAGEN — [{titulo}]", bold=True)
    _p(doc, f"Fuente Mermaid: diagramas\\{archivo}  (generar el PNG aparte en "
            f"https://mermaid.live y guardarlo como diagramas\\{base}.png para "
            f"que se incruste a esta ubicacion).", italic=True, color=GRAY)
    doc.add_paragraph()


def _captura(doc, archivo, pie):
    """Incrusta una captura de pantalla real desde TP/capturas/.

    Si el PNG no existe, deja un marcador de posicion gris.
    """
    png = f"TP\\capturas\\{archivo}"
    if os.path.exists(png):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(png, width=Inches(5.9))
        doc.add_paragraph()
        _p(doc, pie, italic=True, color=GRAY)
        doc.add_paragraph()
        return
    _p(doc, f"CAPTURA — [{archivo}]", bold=True)
    _p(doc, f"Falta el archivo TP\\capturas\\{archivo}.", italic=True, color=GRAY)
    doc.add_paragraph()


def _log_sesion(doc):
    """Vuelca TP/log_sesion.txt (linea de tiempo real) como anexo en
    monoespaciado. Si el archivo no existe, deja el marcador de posicion."""
    txt = r"TP\log_sesion.txt"
    if not os.path.exists(txt):
        _p(doc, "LOG DE SESION — falta agregar TP\\log_sesion.txt "
                "(generarlo con Venv\\Scripts\\python.exe "
                "TP\\generar_log_sesion.py).", bold=True)
        return
    with open(txt, "r", encoding="utf-8") as f:
        lineas = [ln.rstrip() for ln in f]
    for ln in lineas:
        p = doc.add_paragraph()
        r = p.add_run(ln)
        r.font.name = "Consolas"
        r.font.size = Pt(8)
        r.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    doc.add_paragraph()


def main():
    doc = Document()
    # estilo base
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # ---------------------------------------------------------------- portada
    doc.add_paragraph()
    _p(doc, "INTELIGENCIA ARTIFICIAL APLICADA A ORGANIZACIONES", bold=True)
    _p(doc, "Trabajo de Fin de Ciclo — ENTREGA FINAL DE PROYECTO", bold=True)
    _p(doc, "UTN FRBA — Curso de Inteligencia Artificial para Programadores")
    doc.add_paragraph()
    _p(doc, "Grupo: [COMPLETAR nombre/rol de cada integrante]", color=GRAY)
    _p(doc, "Repositorio: https://github.com/patosimple/Incidencias")
    doc.add_paragraph()

    # ---------------------------------------------------- links obligatorios
    _titulo(doc, "Links de acceso directo (validos al momento de la correccion)")
    _tabla(doc, ["Recurso", "URL"], [
        ["Repositorio GitHub", "https://github.com/patosimple/Incidencias"],
        ["Aplicacion en produccion", "https://incidencias.onrender.com"],
        ["Video demo", "[COMPLETAR enlace — max 3 min]"],
        ["Otros recursos publicados", "[COMPLETAR si aplica — p.ej. el manual de uso /admin de la app]"],
    ])

    doc.add_page_break()

    # ====================================================== PARTE 1
    _titulo(doc, "PARTE 1 — El proyecto como aplicacion real")

    # ------------------------------------------------------------ seccion 1
    _titulo(doc, "1. Presentacion del equipo y del proyecto", 2)
    _p(doc, "Integrantes del grupo (nombre, rol en el desarrollo):", bold=True)
    _p(doc, "[COMPLETAR por integrante]")
    _titulo(doc, "Nombre del proyecto", 3)
    _p(doc, "Sistema de Gestion de Incidencias de TI (tickets) con analisis IA asistido.")
    _titulo(doc, "Problema que resuelve", 3)
    _p(doc, "Gestion interna de bugs y requerimientos sobre dos aplicaciones de "
            "negocio (Balances y Financiamiento politico). Centraliza el reporte, "
            "el seguimiento, la toma colaborativa, el cambio de estado y el cierre "
            "de incidentes, e incorpora una capa de analisis IA que asiste a "
            "desarrolladores y coordinadores a entender el problema reportado.")
    _titulo(doc, "Publico objetivo", 3)
    _p(doc, "Usuarios internos de la organizacion: (a) solicitantes "
            "(usuarios de negocio que reportan incidencias sin acceso a "
            "detalles tecnicos), (b) desarrolladores que atienden los tickets "
            "de sus sistemas, y (c) coordinadores que supervisan el flujo. "
            "El admin/superuser gestiona usuarios, accesos y configuracion de IA.")

    # ------------------------------------------------------------ seccion 2
    _titulo(doc, "2. Arquitectura tecnica", 2)

    _titulo(doc, "Diagrama de arquitectura general", 3)
    _p(doc, "Componentes IA vs logica tradicional: el nucleo de tickets (crear, "
            "listar, comentar, estados, permisos, adjuntos) es logica tradicional "
            "Django. La unica componente IA es el modulo de analisis de "
            "incidencias (ai/), que se dispara manualmente.")
    _diagrama(doc, "arquitectura.mmd", "Arquitectura general")

    _titulo(doc, "Diagrama de flujo de agentes", 3)
    _p(doc, "El proyecto como aplicacion NO incluye orquestacion multi-agente "
            "en produccion: el analisis IA es un paso puntual y manual. El "
            "trabajo de desarrollo si se apoyo en esquemas de IA, alternando "
            "dos modalidades: opencode (CLI) con cambio de agente manual por "
            "tarea, y Antigravity (IDE) con Gemini como orquestador sobre un "
            "multiMCP adaptado para usar rotacion interna de API keys y "
            "proveedores. El diagrama siguiente representa esta metodologia "
            "(las partes de la app estan cubiertas en los diagramas "
            "funcionales).")
    _diagrama(doc, "agentes_desarrollo.mmd", "Flujo de agentes (metodologia de desarrollo)")
    _diagrama(doc, "estados_ticket.mmd", "Flujo de estados del ticket")

    _titulo(doc, "UML — Diagrama de clases", 3)
    _diagrama(doc, "clases.mmd", "Diagrama de clases (modelo de datos)")
    _titulo(doc, "UML — Casos de uso", 3)
    _diagrama(doc, "casos_de_uso.mmd", "Casos de uso por rol")
    _titulo(doc, "UML — Secuencia del analisis IA", 3)
    _diagrama(doc, "secuencia_analisis_ia.mmd", "Secuencia del analisis IA")

    doc.add_page_break()

    # ------------------------------------------------------------ seccion 3
    _titulo(doc, "3. Stack tecnologico", 2)
    _tabla(doc, ["Componente", "Tecnologia / Herramienta", "Por que esta y no otra"], [
        ["Frontend",
         "Templates Django + HTMX + Tailwind (CDN), dark mode",
         "HTMX permite interacciones parciales sin SPA ni JS pesado; Tailwind da "
         "consistencia rapida con paleta de marca y responsive; CDN evita build "
         "complejo. Se eligio sobre React/Vue por simplicidad de mantenimiento "
         "server-rendered en un equipo chico."],
        ["Backend",
         "Python Django 5.2 + Gunicorn + Whitenoise",
         "Django trae ORM, admin, auth y seguridad (CSRF, login) maduros; "
         "Python es el stack del curso y el idoneo para integrar APIs de IA. "
         "Whitenoise sirve estaticos sin servidor aparte."],
        ["Base de datos",
         "PostgreSQL (Neon/Supabase)",
         "Postgres por integridad (constraints, unique_together, indices) y por "
         "pgvector (plan RAG futuro). Neon gratis y con SSL. Almacenamiento de "
         "adjuntos persistido en Supabase Storage (S3, ver Despliegue). No SQLite "
         "porque el deploy en Render usa disco efimero y la app corre persistida "
         "en la nube."],
        ["Modelo de IA",
         "Multi-proveedor OpenAI-compatible: Groq, Gemini, OpenRouter, NVIDIA; "
         "Ollama local. Activo: qwen/qwen3.8-27b (Groq).",
         "Abstraccion en ai/providers.py con un unico contrato HTTP; permite "
         "probar el modelo activo o caer a Ollama local (privacidad). Groq "
         "como activo por latencia baja del free tier."],
        ["Orquestacion",
         "Codigo propio + Huey (cola de tareas; hoy sincrono con immediate=True)",
         "Sin LangChain: la fachada IA es simple y completa (mensajes, formato, "
         "reintentos). Huey+PostgresHuey para no sumar Redis al proyecto: "
         "usa la misma base de datos."],
        ["Despliegue",
         "Render (Gunicorn) + Neon (Postgres) + Supabase Storage (S3)",
         "Render gratis con deploy por git; Neon gratis sin tarjeta. Los adjuntos "
         "van a un bucket S3 privado de Supabase Storage (URLs firmadas 5 min): "
         "el disco de Render es efimero y cada redeploy perderia los archivos, "
         "por eso se resolvio con storage en la nube (decision 16/09/2026). "
         "Local (DEBUG) usa FileSystemStorage en media/."],
    ])

    doc.add_page_break()

    # ------------------------------------------------------------ seccion 4
    _titulo(doc, "4. Evidencia de funcionamiento", 2)
    _titulo(doc, "Capturas de pantalla (minimo 3)", 3)
    _p(doc, "Las siguientes capturas son pantallas reales de la aplicacion "
            "desplegada (logeo con un usuario del seed). Cubren el minimo "
            "exigido por la consigna: pantalla principal/home, el flujo de uso "
            "principal y el resultado del output de IA visible para el usuario.")
    _p(doc, "(a) Pantalla principal / home — listado de tickets con filtros, "
            "paginador e indicador de novedades:", italic=True, color=GRAY)
    _captura(doc, "02_listado_desktop.png",
             "Listado de tickets (home) — rol Desarrollador, tema claro.")
    _p(doc, "(b) Flujo de uso principal — creacion de ticket con editor "
            "enriquecido y adjuntos:", italic=True, color=GRAY)
    _captura(doc, "04_crear_ticket.png",
             "Creacion de ticket (form + editor Quill + lista de adjuntos).")
    _p(doc, "(c) Resultado / output de la IA visible para el usuario — seccion "
            "Analisis IA en el detalle:", italic=True, color=GRAY)
    _captura(doc, "11_analisis_ia.png",
             "Detalle del ticket con la seccion Analisis IA expandida "
             "(cards de resultado generado por el LLM).")
    _titulo(doc, "Video de demostracion (opcional)", 3)
    _p(doc, "[COMPLETAR enlace si aplica — max 3 min]")
    _titulo(doc, "Log de una sesion real", 3)
    _p(doc, "Se incluye en anexo: linea de tiempo de una ejecucion completa "
            "extraida de la base de datos real (tickets + comentarios + "
            "analisis IA con proveedor/modelo/version de prompt).")
    _log_sesion(doc)

    doc.add_page_break()

    # ------------------------------------------------------------ seccion 5
    _titulo(doc, "5. Evaluacion UX/UI", 2)
    _titulo(doc, "5.1 Heuristicas de Nielsen aplicadas al proyecto", 3)
    _tabla(doc, ["Heuristica", "Cumple?", "Evidencia / Observacion"], [
        ["Visibilidad del estado del sistema", "Si",
         "Badges de estado coloreados en listado y detalle (PENDIENTE rojo, "
         "EN_PROCESO verde, CERRADO gris, REABIERTO); el color distingue si lo "
         "tomo el usuario u otro (verde=yo, azul=otro, rojo=sin tomar). "
         "Toasts/flash con feedback; spinner + barra de progreso real en "
         "adjuntos."],
        ["Coincidencia con el mundo real", "Si",
         "Lenguaje del dominio en espanol (tickets, sistema, solicitante, "
         "colaborador); el usuario no ve internals; etiquetas claras en forms "
         "y botones con verbos (Tomar, Liberar, Cerrar, Reabrir, Analizar)."],
        ["Control y libertad del usuario", "Si",
         "Cancelar en todos los forms; quitar adjuntos antes de subir; "
         "editar/eliminar comentarios y ticket propio; liberar/reabrir para "
         "corregir errores; Los enlaces vuelven al listado; limpiar filtros."],
        ["Consistencia y estandares", "Si",
         "Paleta brand unica (#007AC3) en toda la app, dark mode coherente, "
         "partials reutilizables (badges, cards, pagina de ticket), mismos "
         "patrones de botones por estado, misma metodologia de filtros en "
         "listado."],
        ["Prevencion de errores", "Si",
         "Validacion client-side al seleccionar adjuntos (10MB + whitelist de "
         "extensiones con toast), validacion de form antes de enviar, botones "
         "destructivos con confirmacion (SweetAlert2), bloquear submit durante "
         "upload, botones contextuales (no aparece 'Tomar' si ya colabora)."],
        ["Reconocimiento sobre recuerdo", "Si",
         "Selects con label placeholder (Sistema/Estado/Colaborador/Novedades), "
         "puntito de novedad por fila, filtro 'Tomado' para devs, badges que se "
         "explican solos; el usuario no necesita recordar valores."],
        ["Ayuda y documentacion", "Si",
         "Manual de uso dentro de la app (/manual/) con 18 secciones "
         "colapsables, TOC de anclas y visibilidad por rol (solicitante ve solo "
         "lo general; dev/coord suma toma/IA; staff suma admin); FAQs incluidas. "
         "Mensajes de error claros en espanol."],
    ])

    _titulo(doc, "5.2 Evaluacion orientada al publico objetivo", 3)
    _p(doc, "Diseño apropiado para el nivel tecnico: el solicitante no ve "
            "internals (ni analisis IA ni toma colaborativa); devs/coord ven "
            "las herramientas de gestion sin friccion.", bold=False)
    _p(doc, "Lenguaje visual/textual comprensible: espanol de negocio, no "
            "jargon de backend; hint de adjuntos y textos de accion verbales. "
            "El analisis IA pide solo informacion que el usuario podria aportar "
            "(pantalla, pasos, mensaje de error, frecuencia, OS).")
    _p(doc, "Prueba con usuario real: se corrieron escenarios reales con el usuario "
        "y de ahi salieron decisiones de UX concretas: toasts para mutaciones "
        "in-place (comentarios) vs flash tag cuando hay navegacion; limite de "
        "adjuntos en 10 MB (los informes llegan hasta ~6 MB); indicador de "
        "novedades como puntito azul (en vez de badge) con toggle en el header; "
        "no mostrar 'informacion faltante' del analisis IA (sin valor para el "
        "lector tecnico); filtros con label placeholder en espanol.")

    doc.add_page_break()

    # ------------------------------------------------------------ seccion 6
    _titulo(doc, "6. Evaluacion de Ciberseguridad", 2)
    _tabla(doc, ["Riesgo identificado", "Tipo (OWASP/privacidad/acceso)", "Medida implementada"], [
        ["Inyeccion de prompt en el modelo IA", "Prompt injection",
         "Prompt separado system/user; el user declara que la descripcion del "
         "ticket es SOLO dato (puede contener ordenes) que se ignoran; bloque "
         "delimitado con \"\"\" y defensa explicita en system; el titulo tambien "
         "se protege. Ninguna instruccion dentro de la descripcion modifica la "
         "tarea/reglas/formato."],
        ["Exposicion de API keys", "Secretos en codigo",
         "Keys en .env (ignorado en git) propagadas a os.environ en settings; "
         "nunca hardcodeadas; .env.example commiteado solo con placeholders."],
        ["Datos de usuarios almacenados", "Privacidad",
         "Modelo minimo: username, rol, accesos a sistemas; no se guardan datos "
         "sensibles extra; contraseñas hasheadas por Django; el analisis IA con "
         "datos de Financiamiento politico puede correr 100% local con Ollama "
         "para no salir de la org."],
        ["Acceso no autorizado (autenticacion/autorizacion)", "Acceso",
         "Login obligatorio (LOGIN_URL), permisos por rol (solicitante ve solo "
         "sus tickets; dev ve sus sistemas), verificacion server-side (403/404) "
         "en tomar/cerrar/reabrir/comentar/analizar; superuser con bypass "
         "controlado; soft-delete conserva auditoria. Se implemento integralmente."],
        ["XSS en contenido del ticket/comentarios", "OWASP A3",
         "Sanitizacion nh3 al guardar (whitelist de tags/atributos Quill) en "
         "crear/editar ticket y comentarios; render con |safe es seguro porque "
         "el input llega ya saneado; tests E2E de XSS automatizados "
         "(XssVistaTest)."],
        ["Adjuntos maliciosos", "OWASP A1 (mayormente)",
         "Whitelist de extensiones (imagenes, office, comprimidos) — excluidos "
         "ejecutables, .svg, macros de Office y html/xml; limite de 10MB por "
         "archivo con validacion client y server."],
        ["CSRF / sesion", "OWASP A1/A8",
         "CSRF middleware activo y token en todos los forms POST (incluidos "
         "los HTMX); logout por POST."],
    ])

    doc.add_page_break()

    # ------------------------------------------------------------ seccion 7
    _titulo(doc, "7. IAs usadas en el co-work de desarrollo", 2)
    _p(doc, "El desarrollo se hizo en dos esquemas combinados: (1) esquema "
            "multi-agente con Antigravity + Gemini como orquestador + un "
            "multiMCP adaptado para usar rotacion interna de API keys y "
            "proveedores; y "
            "(2) opencode como CLI con cambio de agente manual por tarea. "
            "Ambas modalidades se alternaron a lo largo del desarrollo y se "
            "complementaron (no hay un reparto de features por esquema: el "
            "mismo hito se pudo abordar desde cualquiera de las dos). El "
            "contexto original del proyecto quedo documentado en el archivo "
            "AGENTS.md dentro del repositorio, que ambas herramientas leyeron "
            "y actualizaron; asi el paso de un esquema al otro no perdia la "
            "memoria del desarrollo (conceptos, decisiones y pendientes).")
    _tabla(doc, ["Herramienta IA", "Para que la usaron", "Aporto"], [
        ["Claude (claude.ai, chat)", "Planificacion y diseno del sistema (entidades, "
         "flujos, esquema de datos) directamente desde el chat de claude.ai, y "
         "allí mismo genero el proyecto Django inicial listo para trabajar: "
         "estructura del proyecto, modelos, urls y views iniciales, archivos "
         "docker y requirements.txt, entregados como .zip.",
         "Bien: el andamiaje completo del proyecto quedo definido y descargable "
         "desde el arranque y consistente con el diseno planificado; sobre esa "
         "base luego se trabajó con Antigravity (multi-agente) y opencode "
         "(agentes manuales)."],
        ["Antigravity + Gemini (orquestador multi-agente) + multiMCP adaptado "
         "con rotacion interna de API keys y proveedores", "Desarrollo de parte "
         "del codigo con esquema "
         "multi-agente: varios agentes orquestados por Gemini para generar "
         "features del backend y frontend.",
         "Bien: permitio encarar el desarrollo con agentes especializados "
         "coordinados por un orquestador. Limitaciones del multiMCP: en la "
         "sesion de prueba varios proveedores fallaron (modelos deprecados, "
         "carrusel de proveedores sin saldo, 404/410 en NVIDIA), por lo que el "
         "trabajo se termino combinando con opencode manual."],
        ["opencode (CLI, agentes manuales)", "Generar backend Django, forms, "
         "vistas, templates (Tailwind/HTMX/Quill), capa IA multi-proveedor, "
         "tests automatizados, debugging",
         "Bien: velocidad de generacion de estructura completa y consistente; "
         "revision de bugs con repro (p.ej. scroll de SweetAlert2, orden de "
         "serializacion HTMX). Mal: a veces generaba codigo con errores sutiles "
         "(p.ej. {# #} multilinea renderizado literal, Orden de listeners "
         "HTMX) que hubo que corregir con tests."],
        ["GitHub/Git (historial de commits)", "Evidencia del proceso real de "
         "trabajo incremental", "Bien: historia de commits real es requisito "
         "de evaluacion."],
    ])
    _titulo(doc, "Reflexion obligatoria", 3)
    _p(doc, "Sin el co-work con IA el desarrollo hubiera tomado al menos el doble "
            "de tiempo: la capa IA multi-proveedor (providers OpenAI-compatible "
            "con formato de salida por modelo, prompt anti prompt-injection, "
            "escalera de degradacion por contexto), la suite de ~65 tests "
            "automatizados (XSS, adjuntos, transiciones, novedades, permisos; "
            "mas de 120 al cierre) y "
            "los fixes finos de UX (scroll del SweetAlert2, orden de "
            "serializacion HTMX, barra de progreso real en adjuntos). La IA "
            "tambien fallo y esas fallas se corrigieron: un comentario "
            "multilinea {# #} de Django que se renderizaba literal, incidentes "
            "de orden de listeners HTMX que a veces no actualizaban el detalle, "
            "y garantias de XSS inexistentes que los propios tests delataron "
            "(el render |safe solo es seguro si el input se sanea al entrar). "
            "Sobre los esquemas: el multi-agente (Antigravity/Gemini) ayudo a "
            "encarar el codigo con agentes especializados coordinados, pero su "
            "dependencia del carrusel de proveedores resulto fragil en la "
            "sesion de prueba; el cambio manual de agente en opencode dio mas "
            "control y trazabilidad del trabajo por tarea, y fue el esquema con "
            "el que se terminaron de consolidar las features y los tests.")

    doc.add_page_break()

    # ====================================================== PARTE 2
    _titulo(doc, "PARTE 2 — IA local en tu proyecto", 1)
    _p(doc, "Nota: la aplicacion ya incorpora Ollama como proveedor local "
            "(formato NATIVO, sin key). Como contexto del analisis, el prompt "
            "se arma con la descripcion del ticket, la descripcion oficial del "
            "sistema (Sistema.prompt) y el manual de uso del sistema en texto "
            "plano (manuales_rag/<codigo>, leido al momento de analizar). Se "
            "evaluaron dos variantes para incorporar los manuales: RAG "
            "vectorial (embeddings locales con nomic-embed-text + pgvector) y "
            "enviar el manual completo en el prompt. Se eligio esta ultima "
            "porque los manuales son acotados (BALANCES ~24 KB, FINANCIAMIENTO "
            "~16 KB, ~10-12K tokens) y entran enteros en el contexto: el modelo "
            "ve todo el contenido, sin riesgo de fragmentos mal seleccionados "
            "por similitud; ademas evita pgvector, el pipeline de indexado y la "
            "carga de un modelo de embeddings en Ollama por analisis. El RAG "
            "quedo documentado como plan para escalar a manuales grandes.")

    _titulo(doc, "Pregunta 1 - Que papel jugaria un LLM/SLM local", 2)
    _p(doc, "Reemplazaria (o complementaria) la API externa para escenarios "
            "sensibles: los tickets de Financiamiento politico no deberian "
            "salir de la organizacion. El provider Ollama ya existe en la app: "
            "cambiando el modelo activo (ConfiguracionIA) el analisis corre "
            "local. Hoy el contexto del analisis ya incluye el manual de uso "
            "del sistema (txt completo, sin que los datos salgan de la org); a "
            "futuro podria sumarle embeddings locales (nomic-embed-text) para "
            "RAG sobre esos manuales. Seria un componente de soporte "
            "intercambiable, no el agente principal.")
    _titulo(doc, "Pregunta 2 - Que le aportaria al usuario", 2)
    _p(doc, "Privacidad (los datos sensibles no salen de la org), cero costo "
            "por token y funcionamiento offline. En experiencia, permitiria "
            "ofrecer el analisis como garantia por defecto para incidencias de "
            "sistemas sensibles, sin depender del estado de un proveedor "
            "externo.")
    _titulo(doc, "Pregunta 3 - Que te aportaria a vos como profesional", 2)
    _p(doc, "Analizar logs/comportamientos de incidencias y patrones de "
            "reportes sin necesidad de que los datos salgan de la organizacion; "
            "probar el pipeline de IA offline; el modelo local corre con el "
            "mismo codigo (mismo prompt y formato de salida), lo que permite "
            "desarrollo sin keys ni costo y validar privacidad ante el cliente.")
    _titulo(doc, "Pregunta 4 - Limitaciones concretas vs API en la nube", 2)
    _p(doc, "Comparacion de tiempos de analisis local vs nube (medido sobre un "
            "ticket real con el prompt completo y el manual del sistema; "
            "[COMPLETAR con las mediciones reales]): el analisis con Ollama "
            "local (qwen2.5:3b-instruct-q4_K_M, ~6 tok/s de decode) tarda "
            "[T_LOCAL — ~90-120s] vs la API en la nube (Groq, qwen/qwen3.8-27b) "
            "que tarda [T_NUBE — pocos segundos]. La implementacion final esta "
            "prevista sobre un servidor de la organizacion con caracteristicas "
            "superiores a los equipos de desarrollo, lo que reduce la brecha "
            "de rendimiento. La calidad del modelo local de ~3B es inferior a "
            "la de los ~27B de Groq para el caso de uso especifico. "
            "Mantenimiento (actualizar el modelo, ollama pull) recae en el "
            "equipo local. No conviene para volumen alto ni para tareas "
            "globales largas.")

    _titulo(doc, "Entregable opcional — captura de Ollama local", 2)
    _p(doc, "[COMPLETAR captura tras ejecutar, p.ej.:]")
    _p(doc, "Comando: ollama run qwen2.5:3b", bold=False)
    _p(doc, "Pregunta: \"En una organizacion que gestiona incidencias de "
            "Financiamiento politico, que ventajas y riesgos tiene analizar "
            "esas incidencias con un LLM local versus una API en la nube?\"")
    _p(doc, "Respuesta (1 linea): [COMPLETAR lo que respondio el modelo]")

    doc.save(OUT)
    print("Documento generado:", OUT)


if __name__ == "__main__":
    main()