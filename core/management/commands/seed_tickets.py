"""
Genera datos de demostracion: usuarios solicitantes con acceso a sistemas + tickets
con las incidencias reales del dominio (Balances / Financiamiento).

Uso:
    python manage.py seed_tickets                 # crea los datos si no existen
    python manage.py seed_tickets --reset         # borra y recrea
    python manage.py seed_tickets --tickets 20    # cantidad de tickets (default 5)
    python manage.py seed_tickets --reset_all     # limpieza total (sin recrear)

Requisito previo: haber corrido `seed_init` (sistemas y catalogo IA).
"""

import random
import unicodedata

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connection, transaction

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

# Usuario desarrollador de demo. Se crea igual que los solicitantes (get_or_create),
# con acceso a todos los sistemas, pero NO recibe tickets (la demo de tickets es
# exclusiva de los solicitantes). Password: desa
# Además es staff con permisos de admin para gestionar usuarios y sus accesos,
# sistemas, catálogo de modelos IA y configuración de IA activa.
DEV_DEMO = {
    "username": "dev.demo",
    "first_name": "Dev",
    "last_name": "Demo",
    "email": "dev.demo@incidencias.local",
    "rol": "DESARROLLADOR",
    "password": "desa",
    "is_staff": True,
    "permisos_admin": ["Usuario", "UsuarioSistema", "Sistema", "ModeloIA", "ConfiguracionIA"],
}


# Tickets reales: incidencias del dominio (Balances / Financiamiento) que
# reporta un equipo de sistemas contable, con su descripcion original.
TICKETS_REALES = [
    {
        "titulo": 'Leyenda Rectificado',
        "sistema": 'FINANCIAMIENTO',
        "descripcion_original": '<p>Buenos días:</p><p>Hoy pudimos establecer, mediante una prueba en TEST, que la leyenda "RECTIFICADO" aparece en los informes de campaña que se rectifiquen SÓLO una vez que se hayan recibido.</p><p><br></p><p>¿Qué problema genera esto?</p><p><br></p><p>El Usuario imprime el Informe rectificado UNA VEZ QUE ESTÁ PRESENTADO y con su código de seguridad, para que el mismo sea firmado y presentado en el expediente como respuesta a observaciones, pero este Informe todavía no indica que se trata de un rectificado.</p><p><br></p><p>Por otra parte, a continuación de ello, la Secretaría recibirá el informe rectificado presentado y ese es el momento en el que pasa a constar en la carátula que se trata de un informe rectificado.</p><p><br></p><p>Coexisten, entonces, dos versiones del mismo informe:</p><p>1) La presentada en el Expediente SIN LA LEYENDA</p><p>2) La publicada en la página CON LA LEYENDA</p><p><br></p><p>Entendemos que debería aparecer el texto "RECTIFICADO" en el mismo momento en que se genera el código de seguridad.</p><p><br></p><p>Saludos!</p>',
    },
    {
        "titulo": 'Lógica en la numeración de notas automáticas',
        "sistema": 'BALANCES',
        "descripcion_original": '<p>Hay un problema con la numeración de las notas a los rubros (notas automáticas) y esta en la lógica que utiliza el aplicativo en el Estado de Situación Patrimonial, la que difiere de la que aplica en el apartado de Notas.</p><p><br></p><p>En el Estado de Situación Patrimonial el aplicativo piensa: "Voy a referir a una nota si y sólo si hay valores de este rubro para este ejercicio".</p><p>Esa lógica no parece ser correcta, ya que, aún cuando tenga saldo cero,  un rubro puede tener información comparativa, por lo tanto no es "CERO" per se, ameritando una  nota automática.</p><p><br></p><p>Por otra parte, en el Apartado de Notas, la lógica que usa es la siguiente: "Si tiene nota, la numero".</p><p><br></p><p><br></p><p>Esta divergencia en la forma de numerar hace que el rubro posterior quede mal referido, ya que en el Estado de Situación Patrimonial, el rubro "otros créditos" queda referido con la nota 3, mientras que -en realidad- corresponde a la nota 4 (la nota 3, en realidad, corresponde a "Créditos por Aportes Públicos", en nuestro ejemplo).</p>',
    },
    {
        "titulo": 'Error en variación del Estado de Flujo de Efectivo (cambia el signo)',
        "sistema": 'BALANCES',
        "descripcion_original": '<p>Este problema es difícil de explicar en texto.</p><p><br></p><p>Un Estado de Flujo de Efectivo consta de dos partes:</p><p>-La primera (la variación neta de efectivo) detalla cuanto aumentó o disminuyó el DINERO entre el inicio y el cierre.</p><p>Si tenía más plata al inicio que al cierre, quiere decir que gasté más de lo que cobré.</p><p>Si pasa lo contrario, entró más plata de la que salió.</p><p>- La segunda parte es la JUSTIFICACIÓN de esa VARIACIÓN (se desagregan los conceptos por los cuales entró el dinero -u orígenes- y las causales de las salidas -aplicaciones- de fondos.</p><p><br></p><p>El caso del ejemplo, es para una variación negativa (entró menos dinero del que salió).</p><p><br></p><p>   Fíjense en el archivo jpg. "EFE 1". </p><p><br></p><p>   El Partido empezó el año con $ 702.000,00 y terminó con $ 700.000,00. La variación es negativa en 2.000,00.</p><p>   Si voy a la justificación, veo que pagó gastos por $ 2.000,00. Sencillo. Un sólo movimiento explica todo.</p><p><br></p><p><br></p><p>Ahora, el problema:</p><p><br></p><p>A este mismo reporte, le introduzco un cambio. Una modificación de ejercicios anteriores (negativa) por $ 1.000,00. </p><p>(supongamos que el año pasado habían contado mal el dinero y no contemplaron ticket por pago de servicios de $ 1.000,00).</p><p><br></p><p><br></p><p>Necesito, entonces, bajar el saldo de inicio a $ 701.000,00.</p><p><br></p><p>El saldo de cierre sigue siendo de $ 700.000,00, porque sale del arqueo (recuento de dinero). Sólo que ese gasto de $ 2.000,00, en realidad era de $ 1.000,00, porque el ticket era del año pasado)</p><p><br></p><p>Matemáticamente, la variación sigue siendo negativa ($ 700.000,00 menos $ 701.000,00 = $ -1.000,00)</p><p><br></p><p>Sin embargo, si miramos el pdf "EFE 2", vemos que ME CAMBIÓ EL SIGNO DE LA VARIACIÓN A POSITIVO, CUANDO INCORPORÉ EL AJUSTE.</p><p><br></p><p><br></p><p>Sin embargo, el RESULTADO, EN VALORES ABSOLUTOS de la variación siegue siendo correcto, sólo que cambia el signo.</p>',
    },
    {
        "titulo": 'Inconsist. en la oferta p/"crear informe" según características del partido.',
        "sistema": 'FINANCIAMIENTO',
        "descripcion_original": '<p>Encontramos dos problemas en la lista de informes que se ofrece en la pantalla “Crear Informe”:</p><p><br></p><p>A. PARTIDOS EN GENERAL: INFORMES NO DESEADOS</p><p>Haciendo testeos en la resolución del punto anterior se observaron algunos casos en los que  se ofrece la posibilidad de crear informes que no corresponden al dominio del partido, ya sea porque son de otro orden (nacional/distrital), o que siendo del orden correcto el partido no debiera poder crearlos porque no tiene lista presentada para el cargo en cuestión. </p><p><br></p><p>B. PARTIDOS NACIONALES: NO APARECE LA OPCION DE CREAR INFORMES PARA CARGOS NACIONALES.</p><p>Se observaron casos en que si un partido de orden nacional ingresa a la pantalla de creación de informes, no le aparece la opción de crear informe de cargos nacionales (presidente y vice / mercosur nacionales). Este error sucede cuando un partido de orden nacional, no pertenece a una alianza nacional, es decir, en partidos nacionales que puedan participar de manera independiente en la elección.</p>',
    },
    {
        "titulo": 'El cuadro del Anexo de Transferencias trascienden los límites de la página del PDF',
        "sistema": 'BALANCES',
        "descripcion_original": '<p>Habíamos hablado de este Anexo, pero el usuario que reportó el error no se explicó bien (tampoco había mandado capturas), pero hoy hice la prueba y verifiqué el error.</p><p><br></p><p>El Anexo de Transferencias Recibidas (Ingresos) y Enviadas (Gastos) es el único Anexo combinado que no responde exclusivamente a resultados positivos o negativos.</p><p>En el mismo se detallan tanto las Transferencias que el Partido hace (gastos), como las que recibe (ganancias), tanto para desenvolvimiento institucional, como campaña nacional y local (Son 6 grupos de detalles)</p><p><br></p><p>INGRESOS</p><p>4.2.05.00 - Transf Recibidas de Otros Órganos o Distritos para Desenv Institucional</p><p>4.3.07.00 - Transf Recibidas de Otros Órganos o Distritos para Campaña Nacional</p><p>4.4.04.00 - Transf Recibidas de Otros Órganos o Distritos para Campaña Local</p><p>EGRESOS</p><p>5.1.41.00 - Transf Realizadas a Otros Órganos o Distritos para Desenv Institucional</p><p>5.2.31.00 - Transf Realizadas a Otros Órganos o Distritos para Campaña Nacional</p><p>5.3.09.00 - Transf Realizadas a Otros Órganos o Distritos para Campaña Local</p><p><br></p><p>Creo que el reporte se pensó así:</p><p><br></p><p>1- En la primera página, se detallas las cuentas de ingresos.</p><p>Si entran las tres cuentas, las detalla y salta de página SI O SI para listar los detalles de los gastos.</p><p><br></p><p>2- Pero si no entran los cuadros de las tres cuentas de ingresos en una página, separa los detalles por hoja (hace tantos saltos de página como sean necesarios). Funciona igual para los gastos</p><p><br></p><p>El problema se da cuando ni siquiera un cuadro entra en una hoja. Por ejemplo, el partido Solidario (Orden Nacional) que usa las transferencias como si fueran aportes privados. Todos los órganos distritales les giran dinero, por eso el cuadro es tan extenso.</p><p><br></p><p>Ahora, cuando pasa eso, el cuadro TRASPASA EL PIE DE PÁGINA HASTA DONDE LLEGUE. La información que no entra, SE PIERDE, porque no salta.</p><p><br></p><p>Además, hay información de extensión predeterminada (palabras Distrito o Nacional) o fechas e Importes mayores a 10 millones que deberían verse en un renglón.</p>',
    },
]


def _sin_acentos(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)
    )


def _username(persona):
    nombre = persona["nombres"].split()[0].lower()
    apellido = persona["apellido"].lower()
    return f"{_sin_acentos(nombre)}.{_sin_acentos(apellido)}"


class Command(BaseCommand):
    help = "Genera datos de demo (solicitantes + tickets reales)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Borra los datos de demo existentes antes de recrearlos.",
        )
        parser.add_argument(
            "--tickets", type=int, default=5,
            help="Cantidad de tickets a crear (default 5).",
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
        self._seed_dev_demo()
        self._seed_tickets(solicitantes, n_tickets)
        self.stdout.write(self.style.SUCCESS("Seed tickets completo."))

    def _reset(self):
        usernames = [_username(p) for p in SOLICITANTES] + [DEV_DEMO["username"]]
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
                username__in=[_username(p) for p in SOLICITANTES] + [DEV_DEMO["username"]]
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

    def _seed_dev_demo(self):
        """Crea el usuario desarrollador de demo (misma lógica que los solicitantes:
        get_or_create + password + accesos). NO recibe tickets. Tiene acceso al admin
        (staff) con permisos CRUD sobre los modelos indicados en DEV_DEMO."""
        sistemas = list(Sistema.objects.all())
        user, creado = Usuario.objects.get_or_create(
            username=DEV_DEMO["username"],
            defaults={
                "first_name": DEV_DEMO["first_name"],
                "last_name": DEV_DEMO["last_name"],
                "email": DEV_DEMO["email"],
                "rol": DEV_DEMO["rol"],
            },
        )
        if creado:
            user.set_password(DEV_DEMO["password"])
        user.is_staff = DEV_DEMO["is_staff"]
        user.save()

        permisos = self._permisos_admin(DEV_DEMO["permisos_admin"])
        user.user_permissions.add(*permisos)

        for s in sistemas:
            UsuarioSistema.objects.get_or_create(usuario=user, sistema=s)
        acceso = ", ".join(s.codigo for s in sistemas)
        self.stdout.write(
            f"  Desarrollador {user.first_name} {user.last_name} ({user.username}) -> {acceso}"
        )
        return user

    @staticmethod
    def _permisos_admin(nombres_modelos):
        """Devuelve los Permission (add/change/delete/view) para los modelos de la app
        core cuyos nombres coincidan con `nombres_modelos`."""
        ct_ids = [
            ct.id for ct in ContentType.objects.filter(app_label="core")
            if ct.model_class() and ct.model_class().__name__ in nombres_modelos
        ]
        return Permission.objects.filter(content_type_id__in=ct_ids)

    def _seed_tickets(self, solicitantes, n):
        sistemas_por_codigo = {s.codigo: s for s in Sistema.objects.all()}
        # Asigna cada ticket a un solicitante sin repetir: baraja la lista y la
        # recorre en ciclo; solo vuelve a barajar cuando agotó todas las opciones.
        cola = list(solicitantes)
        random.shuffle(cola)
        i_sol = 0
        contador = 0
        for i in range(n):
            tpl = TICKETS_REALES[i % len(TICKETS_REALES)]
            solicitante = cola[i_sol % len(cola)]
            i_sol += 1
            if i_sol % len(cola) == 0:
                random.shuffle(cola)
            Ticket.objects.create(
                titulo=tpl["titulo"],
                sistema=sistemas_por_codigo[tpl["sistema"]],
                solicitante=solicitante,
                descripcion_original=tpl["descripcion_original"],
                estado=EstadoTicket.PENDIENTE,
            )
            contador += 1
        self.stdout.write(f"  Tickets creados: {contador}")
