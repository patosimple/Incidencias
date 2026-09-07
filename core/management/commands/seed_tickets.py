"""
Genera datos de demostracion: usuarios solicitantes con acceso a sistemas + tickets
con titulos de lo que reportaria un equipo de sistemas contable y descripcion lorem ipsum.

Uso:
    python manage.py seed_tickets                 # crea los datos si no existen
    python manage.py seed_tickets --reset         # borra y recrea
    python manage.py seed_tickets --tickets 20    # cantidad de tickets (default 10)
    python manage.py seed_tickets --reset_all     # limpieza total (sin recrear)

Requisito previo: haber corrido `seed_init` (sistemas y catalogo IA).
"""

import random
import unicodedata

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connection, transaction
from django.utils import lorem_ipsum

from core.models import (
    Adjunto,
    AnalisisIA,
    Comentario,
    EstadoTicket,
    Sistema,
    Ticket,
    TicketDesarrollador,
    UsuarioSistema,
)

Usuario = get_user_model()


# Nombres reales en espanol para los solicitantes. El username se deriva
# automaticamente de nombres/apellidos sin acentos (ej: maria.lopez).
SOLICITANTES = [
    {"nombres": "María", "apellido": "López", "email": "maria.lopez@incidencias.local"},
    {"nombres": "Carlos", "apellido": "González", "email": "carlos.gonzalez@incidencias.local"},
    {"nombres": "Lucía", "apellido": "Fernández", "email": "lucia.fernandez@incidencias.local"},
    {"nombres": "Joaquín", "apellido": "Rodríguez", "email": "joaquin.rodriguez@incidencias.local"},
    {"nombres": "Valentina", "apellido": "Martínez", "email": "valentina.martinez@incidencias.local"},
]

# Titulos de tickets contables (un equipo de sistema real reportaria esto).
TITULOS = [
    "El Balancete no cuadra al cerrar el mes",
    "Error al exportar el libro mayor a PDF",
    "La conciliacion bancaria no muestra los movimientos del dia",
    "No se puede cargar una factura de proveedor",
    "El asiento de ajuste no guarda las notas",
    "El reporte de IVA compras trae montos duplicados",
    "Se duplica el asiento al guardar dos veces seguidas",
    "El panel de cuentas corrientes carga lento",
    "El cierre contable lanza error de control 402",
    "La planilla de mayores no filtra por rango de fechas",
    "Faltan las retenciones en el libro IVA ventas",
    "El recibo de sueldo no imprime la antiguedad",
    "Las tablas de amortizacion no se actualizan",
    "El modulo de financiamiento no valida el cupo disponible",
    "El importe en letras sale mal en los cheques",
    "La actualizacion de tipos de cambio no impacta en los asientos",
    "Los comprobantes de retencion no se numeran en orden",
    "El cierre anual no permite pasar asientos del ejercicio anterior",
]

# Palabras lorem para armar titulos/descripciones limpios (sin espacios sueltos).
_PALABRAS_LOREM = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua enim ad minim veniam "
    "quis nostrud exercitation ullamco laboris nisi aliquip"
).split()


def _sin_acentos(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)
    )


def _username(persona):
    nombre = persona["nombres"].split()[0].lower()
    apellido = persona["apellido"].lower()
    return f"{_sin_acentos(nombre)}.{_sin_acentos(apellido)}"


def _parrafo_lorem():
    return lorem_ipsum.paragraph().strip()


class Command(BaseCommand):
    help = "Genera datos de demo (solicitantes + tickets lorem ipsum)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Borra los datos de demo existentes antes de recrearlos.",
        )
        parser.add_argument(
            "--tickets", type=int, default=10,
            help="Cantidad de tickets a crear (default 10).",
        )
        parser.add_argument(
            "--reset_all", action="store_true",
            help="Limpieza total: borra todos los tickets/comentarios/adjuntos de TODOS los "
                 "usuarios + los usuarios del seed, y resetea el contador de id de Ticket a 0 "
                 "(el numero de ticket visible se reinicia en 1). No recrea nada.",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        n_tickets = options["tickets"]

        if options["reset_all"]:
            self._reset_all()
            self.stdout.write(
                self.style.SUCCESS(
                    "Reset total: tickets/comentarios/adjuntos de todos los usuarios y "
                    "usuarios del seed eliminados. El proximo ticket arranca en el id 1."
                )
            )
            return

        if reset:
            self._reset()
            self.stdout.write("Datos de demo anteriores eliminados.")

        if not Sistema.objects.exists():
            self.stderr.write(
                self.style.ERROR(
                    "No hay sistemas. Corré primero: python manage.py seed_init"
                )
            )
            return

        solicitantes = self._seed_solicitantes()
        self._seed_tickets(solicitantes, n_tickets)
        self.stdout.write(self.style.SUCCESS("Seed tickets completo."))

    def _reset(self):
        usernames = [_username(p) for p in SOLICITANTES]
        # Solo considera los tickets de los solicitantes del seed (no los de otros usuarios).
        tickets = Ticket.objects.filter(solicitante__username__in=usernames)

        # Recolecta y borra fisicamente los adjuntos de esos tickets y de sus
        # comentarios ANTES del delete en cascada (que solo borra registros en BD,
        # no los archivos fisicos). Util en local, donde el disco persiste.
        adjuntos = Adjunto.objects.filter(
            ticket__in=tickets
        ) | Adjunto.objects.filter(comentario__ticket__in=tickets)
        for adj in adjuntos.distinct():
            if adj.archivo:
                adj.archivo.delete(save=False)

        tickets.delete()
        Usuario.objects.filter(username__in=usernames).delete()

    def _reset_all(self):
        """Limpieza total del demo: borra TODOS los tickets/comentarios/adjuntos del
        sistema (no solo los del seed) y los usuarios del seed, y reinicia el contador
        de id de Ticket a 0 (id visible en el front == numero de ticket). No recrea nada.

        - Los adjuntos se borran fisicamente (disco) antes del DELETE de BD (el delete
          en cascada no borra archivos).
        - Se usan `all_objects` para incluir tickets/comentarios Soft-deleteados.
        - Se conservan Sistemas, catalogo IA y usuarios NO demos (patosimple, devs); por
          eso la secuencia de Usuario NO se resetea (colisionaria el PK con users vivos).
        - El reset de id es SOLO para core_ticket (id visible = numero de ticket)."""
        with transaction.atomic():
            # 1) Adjuntos: borrar el archivo fisico de cada uno.
            adjuntos = Adjunto.objects.all()
            for adj in adjuntos.iterator():
                if adj.archivo:
                    adj.archivo.delete(save=False)
            adjuntos.delete()

            # 2) Tickets y comentarios (incluidos soft-deleted). En cascada caen
            #    AnalisisIA y el through TicketDesarrollador.
            Comentario.all_objects.all().delete()
            Ticket.all_objects.all().delete()

            # 3) Usuarios del seed (cascada a sus UsuarioSistema).
            Usuario.objects.filter(
                username__in=[_username(p) for p in SOLICITANTES]
            ).delete()

            # 4) Reiniciar el id de Ticket a 0 (proximo insert = 1), solo core_ticket.
            reset_sql = connection.ops.sequence_reset_sql(no_style(), [Ticket])
            with connection.cursor() as cursor:
                for sql in reset_sql:
                    cursor.execute(sql)

    def _seed_solicitantes(self):
        sistemas = list(Sistema.objects.all())
        creados = []
        for persona in SOLICITANTES:
            username = _username(persona)
            user, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": persona["nombres"],
                    "last_name": persona["apellido"],
                    "email": persona["email"],
                    "rol": "SOLICITANTE",
                },
            )
            if creado:
                user.set_password("soli")
                user.save()
            # acceso random a 1 o 2 sistemas
            elegidos = random.sample(sistemas, random.randint(1, len(sistemas)))
            for s in elegidos:
                UsuarioSistema.objects.get_or_create(usuario=user, sistema=s)
            creados.append(user)
            acceso = ", ".join(s.codigo for s in elegidos)
            self.stdout.write(
                f"  Solicitante {user.first_name} {user.last_name} ({user.username}) -> {acceso}"
            )
        return creados

    def _seed_tickets(self, solicitantes, n):
        sistemas = list(Sistema.objects.all())
        contador = 0
        for _ in range(n):
            Ticket.objects.create(
                titulo=random.choice(TITULOS),
                sistema=random.choice(sistemas),
                solicitante=random.choice(solicitantes),
                descripcion_original=_parrafo_lorem(),
                estado=EstadoTicket.PENDIENTE,
            )
            contador += 1
        self.stdout.write(f"  Tickets creados: {contador}")
