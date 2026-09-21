"""Agrega marcadores (índice/outline) al PDF.

Correr SIEMPRE después de regenerar un PDF con Edge headless (Edge no genera
outline). Usa PyMuPDF: busca cada título en la página donde aparece y arma el
árbol con doc.set_toc().

Uso:
    ./venv/Scripts/python.exe TP/generar_marcadores.py                     # informe (default)
    ./venv/Scripts/python.exe TP/generar_marcadores.py --pdf TP/Manual_de_uso.pdf
        --marcas TP/marcas_manual.json                                    # manual de uso

El archivo --marcas es JSON con filas [nivel, título] o
[nivel, etiqueta_mostrada, texto_buscado] (permite buscar un texto distinto al
que se muestra como etiqueta, p. ej. para no matchear el título en la página 1
si ahí está el índice).
"""

import argparse
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

import pymupdf

PDF = "TP/Entrega_Final_TP.pdf"

# (nivel, título) en ORDEN de aparición.
MARCAS = [
    (1, "PARTE 1 — El proyecto como aplicación real"),
    (2, "1. Presentación del equipo y del proyecto"),
    (3, "Nombre del proyecto"),
    (3, "Problema que resuelve"),
    (3, "Público objetivo"),
    (2, "2. Arquitectura técnica"),
    (3, "Diagrama de arquitectura general"),
    (3, "Diagrama de flujo de agentes"),
    (3, "UML — Secuencia del análisis IA"),
    (3, "UML — Diagrama de clases"),
    (3, "UML — Casos de uso"),
    (3, "Flujo de estados del ticket"),
    (2, "3. Stack tecnológico"),
    (2, "4. Evidencia de funcionamiento"),
    (3, "Capturas de pantalla"),
    (3, "Video de demostración"),
    (3, "Log de una sesión real"),
    (2, "5. Evaluación UX/UI"),
    (3, "5.1 Heurísticas de Nielsen aplicadas al proyecto"),
    (3, "5.2 Evaluación orientada al público objetivo"),
    (2, "6. Evaluación de Ciberseguridad"),
    (2, "7. IAs usadas en el co-work de desarrollo"),
    (3, "Reflexión."),
    (1, "PARTE 2 — IA local en tu proyecto"),
    (2, "Introducción"),
    (2, "Pregunta 1 — Qué papel jugaría un LLM/SLM local"),
    (2, "Pregunta 2 — Qué le aportaría al usuario"),
    (2, "Pregunta 3 — Qué te aportaría a vos como profesional"),
    (2, "Pregunta 4 — Limitaciones concretas vs API en la nube"),
    (2, "Captura de Ollama local"),
]


def _norm(texto):
    return re.sub(r"\s+", " ", texto).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=PDF)
    ap.add_argument("--marcas", default=None, help="JSON con filas [nivel, título] o [nivel, etiqueta, buscado]")
    args = ap.parse_args()

    if args.marcas:
        with open(args.marcas, encoding="utf-8") as f:
            marcas = [tuple(fila) for fila in json.load(f)]
    else:
        marcas = MARCAS

    doc = pymupdf.open(args.pdf)
    paginas = [_norm(doc[i].get_text()) for i in range(doc.page_count)]

    toc = []
    for fila in marcas:
        nivel = int(fila[0])
        if len(fila) >= 3:
            etiqueta, buscado = fila[1], fila[2]
        else:
            etiqueta = buscado = fila[1]
        buscado = _norm(buscado)
        for i, texto in enumerate(paginas, start=1):
            if buscado in texto:
                toc.append([nivel, etiqueta, i])
                break
        else:
            print(f"AVISO: no se encontró el título -> {buscado!r}")

    faltantes = len(marcas) - len(toc)
    if faltantes:
        print(f"ERROR: {faltantes} título(s) sin página. No se toca el PDF.")
        sys.exit(1)

    doc.set_toc(toc)
    doc.save(args.pdf, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    doc.close()
    print(f"Marcadores OK ({len(toc)}). PDF actualizado: {args.pdf}")
    print("\n".join(f"  {'  '*(n-1)}L{n} p{p:02d} {t}" for n, t, p in toc))


if __name__ == "__main__":
    main()