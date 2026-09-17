# -*- coding: utf-8 -*-
"""Exporta una "linea de tiempo" de la base de datos real como log de sesion.

Uso:  Venv\\Scripts\\python.exe TP\\generar_log_sesion.py
Salida: TP\\log_sesion.txt

SOLO LECTURA: consulta la DB de la app (DATABASE_URL de settings/.env) y
escribe unicamente el archivo .txt de evidencia. No modifica datos.

Cada evento de la linea de tiempo se deriva de las fechas que ya registra el
modelo: creacion de ticket, comentarios (creado/actualizado), cambios de
estado (cerrado/reabierto), ediciones del ticket y analisis IA generados
(con proveedor/modelo/version de prompt).
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.utils import timezone  # noqa: E402
from django.utils.html import strip_tags  # noqa: E402

from core.models import (  # noqa: E402
    Adjunto,
    AnalisisIA,
    Comentario,
    EstadoTicket,
    Ticket,
    TicketDesarrollador,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_sesion.txt")

# El log de evidencia documenta SOLO la sesion real que se hizo hace un rato
# (la creacion de maria.lopez despues de las 13 hs). Todo lo anterior (seed de
# tickets de ejemplo) queda descartado.
HORA_CORTE = 13  # solo eventos de hoy a partir de las HH:00 (hora local)

ESTADO_LABEL = dict(EstadoTicket.choices)


def _fmt(dt):
    if not dt:
        return None
    local = timezone.localtime(dt)
    return local.strftime("%d/%m/%Y %H:%M")


def _eventos():
    """Devuelve lista de tuplas (datetime, linea) ordenadas cronologicamente."""
    eventos = []

    for t in Ticket.objects.select_related("solicitante", "sistema").all():
        quien = t.solicitante.get_full_name() or t.solicitante.username
        sistema = t.sistema.nombre
        e = [
            (t.creado_en,
             f"[{t.pk:02d}] CREADO ticket #{t.pk} \"{t.titulo}\" por {quien} "
             f"(sistema {sistema}). Estado: {ESTADO_LABEL[t.estado]}. "
             f"Descripcion: {strip_tags(t.descripcion_original)}"),
        ]
        if t.modificado_en:
            e.append((t.modificado_en,
                      f"[{t.pk:02d}] EDITADO ticket #{t.pk} (titulo/descripcion) "
                      f"por {quien}."))
        if t.reabierto_en:
            e.append((t.reabierto_en,
                      f"[{t.pk:02d}] REABIERTO ticket #{t.pk} "
                      f"(CERRADO -> REABIERTO), estado actual {ESTADO_LABEL[t.estado]}."))
        if t.cerrado_en:
            e.append((t.cerrado_en,
                      f"[{t.pk:02d}] CERRADO ticket #{t.pk} "
                      f"(estado actual {ESTADO_LABEL[t.estado]})."))

        for a in Adjunto.objects.filter(ticket=t).select_related("subido_por"):
            nom = a.subido_por.get_full_name() or a.subido_por.username
            e.append((a.subido_en,
                      f"[{t.pk:02d}] ADJUNTO a ticket #{t.pk}: {nom} subio "
                      f"\"{a.nombre_archivo}\"."))

        for colab in TicketDesarrollador.objects.filter(ticket=t).select_related("usuario"):
            nom = colab.usuario.get_full_name() or colab.usuario.username
            accion = "TOMO" if colab.activo else "LIBERO"
            e.append((colab.tomado_en,
                      f"[{t.pk:02d}] {accion} ticket #{t.pk} {nom} "
                      f"(colaborador {'activo' if colab.activo else 'liberado'})."))

        for c in Comentario.objects.filter(ticket=t).select_related("usuario"):
            nom = c.usuario.get_full_name() or c.usuario.username
            cuerpo = strip_tags(c.cuerpo).replace("\n", " ")
            for a in Adjunto.objects.filter(comentario=c).select_related("subido_por"):
                nom_a = a.subido_por.get_full_name() or a.subido_por.username
                e.append((a.subido_en,
                          f"[{t.pk:02d}] ADJUNTO a comentario #{c.pk} #{a.pk}: "
                          f"{nom_a} subio \"{a.nombre_archivo}\"."))
            if c.modificado_en:
                e.append((c.modificado_en,
                          f"[{t.pk:02d}] COMENTARIO Editado por {nom} en ticket #{t.pk}: "
                          f"\"{cuerpo}\""))
            else:
                e.append((c.creado_en,
                          f"[{t.pk:02d}] COMENTARIO {nom} en ticket #{t.pk}: "
                          f"\"{cuerpo}\""))

        for a in AnalisisIA.objects.filter(ticket=t).select_related("modelo_ia"):
            mod = a.modelo_ia
            e.append((a.generado_en,
                      f"[{t.pk:02d}] ANALISIS IA ticket #{t.pk} (tipo {a.tipo}): "
                      f"modelo {mod.proveedor}/{mod.modelo}, version_prompt {a.version_prompt}. "
                      f"Problema: {strip_tags(a.problema)}"))

        eventos.extend(e)

    return [ev for ev in eventos if ev[0] is not None]


def main():
    from datetime import datetime as _dt

    todos = _eventos()
    # Corte: solo eventos posteriores a HORA_CORTE de hoy (la sesion real).
    ahora = timezone.localtime(timezone.now())
    hoy_corte = ahora.replace(hour=HORA_CORTE, minute=0, second=0, microsecond=0)
    eventos = [(dt, linea) for dt, linea in todos if timezone.localtime(dt) >= hoy_corte]
    eventos.sort(key=lambda ev: (ev[0],))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("LOG DE SESION REAL — Sistema de Gestion de Incidencias de TI\n")
        f.write(f"Exportado el {_fmt(ahora)} desde la base de datos "
                f"de la aplicacion.\n")
        f.write("Linea de tiempo cronologica: sesion de prueba con datos reales "
                f"(desde las {HORA_CORTE:02d}:00 hs).\n")
        f.write("Incluye: creacion de ticket, comentarios con adjuntos, "
                "toma/liberacion, analisis IA, cierre.\n")
        f.write("=" * 88 + "\n")
        if not eventos:
            f.write("\n(Sin actividad registrada a partir de las "
                    f"{HORA_CORTE:02d}:00)\n")
            return
        for dt, linea in eventos:
            f.write(f"{_fmt(dt)}  {linea}\n")
    print(f"Log generado: {OUT} ({len(eventos)} eventos)")


if __name__ == "__main__":
    main()