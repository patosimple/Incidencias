# -*- coding: utf-8 -*-
"""Genera un HTML standalone del manual de uso de la app para convertir a PDF.

Renderiza core/manual_pdf.html con Django (reutiliza el partial de secciones
core/partials/manual_secciones.html) y embebe las imágenes del manual como
base64 (data URI) para que el HTML quede autocontenido.

Uso:
    ./venv/Scripts/python.exe TP/generar_manual_pdf_html.py
Salida:
    TP/Manual_de_uso.html

PDF (Edge headless):
    & "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" ^
        --headless=new --disable-gpu --user-data-dir=<temp> --no-first-run ^
        --no-pdf-header-footer --print-to-pdf="TP\Manual_de_uso.pdf" ^
        "file:///C:/DEV/django/Incidencias/TP/Manual_de_uso.html"

Marcadores:
    ./venv/Scripts/python.exe TP/generar_marcadores.py --pdf TP/Manual_de_uso.pdf --marcas TP/marcas_manual.json
"""

import base64
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.contrib.staticfiles import finders  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Manual_de_uso.html")

PREFIJO_STATIC = "/static/core/img/manual/"

TOC_GENERAL = [
    (1, "seccion-roles", "Roles y permisos"),
    (2, "seccion-primeros-pasos", "Primeros pasos"),
    (3, "seccion-ciclo-vida", "Ciclo de vida del ticket"),
    (4, "seccion-listado", "Listado de tickets"),
    (5, "seccion-crear-ticket", "Crear un ticket"),
    (6, "seccion-detalle", "Detalle del ticket"),
    (7, "seccion-comentarios", "Comentarios"),
    (8, "seccion-editar-ticket", "Editar o eliminar el propio ticket"),
    (9, "seccion-adjuntos", "Adjuntos"),
    (10, "seccion-faq", "Preguntas frecuentes"),
]

TOC_DESARROLLO = [
    (11, "seccion-tomar-ticket", "Tomar y liberar tickets"),
    (12, "seccion-cerrar-reabrir", "Cerrar y reabrir tickets"),
    (13, "seccion-filtro-colaborador", "Filtro de \"Colaborador\" en el listado"),
    (14, "seccion-analisis-ia", "Análisis IA de tickets"),
    (15, "seccion-colores-tomado", "Colores del badge según quién tomó"),
]

TOC_ADMIN = [
    (16, "seccion-admin-usuarios", "Administración: usuarios y accesos"),
    (17, "seccion-admin-ia", "Administración: modelos IA y configuración"),
    (18, "seccion-admin-nota", "Administración: nota técnica"),
]


class _UserPdf:
    """Usuario sintético: DESARROLLADOR + staff => el manual muestra TODAS las
    secciones (1-10 generales, 11-15 desarrollo, 16-18 administración)."""

    rol = "DESARROLLADOR"
    is_staff = True


def _embed_en_data_uri(src):
    """Reemplaza /static/core/img/manual/... por una data URI base64."""
    out = []
    i = 0
    while True:
        j = src.find(PREFIJO_STATIC, i)
        if j < 0:
            out.append(src[i:])
            break
        out.append(src[i:j])
        fin = src.find('"', j + len(PREFIJO_STATIC))
        nombre = src[j + len(PREFIJO_STATIC):fin]
        ruta = finders.find(os.path.join("core", "img", "manual", nombre))
        if ruta and os.path.exists(ruta):
            ext = os.path.splitext(nombre)[1].lstrip(".").lower() or "png"
            mime = {"jpg": "jpeg"}.get(ext, ext)
            b64 = base64.b64encode(open(ruta, "rb").read()).decode("ascii")
            out.append(f"data:image/{mime};base64,{b64}")
        else:
            out.append(PREFIJO_STATIC + nombre)
        i = fin
    return "".join(out)


def main():
    from django.template.loader import render_to_string

    html = render_to_string(
        "core/manual_pdf.html",
        {
            "user": _UserPdf(),
            "toc_general": TOC_GENERAL,
            "toc_desarrollo": TOC_DESARROLLO,
            "toc_admin": TOC_ADMIN,
        },
    )
    html = _embed_en_data_uri(html)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(html)
    print(f"HTML generado: {OUT} ({os.path.getsize(OUT):,} bytes)")
    print("Imágenes incrustadas en base64:", html.count("data:image/"))


if __name__ == "__main__":
    main()