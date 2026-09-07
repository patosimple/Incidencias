import os
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    Adjunto,
    AnalisisIA,
    Comentario,
    EstadoTicket,
    ModeloIA,
    Sistema,
    Ticket,
    TicketDesarrollador,
    TipoAdjunto,
    TipoAnalisis,
    UsuarioSistema,
    EstadoAprobacion,
)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class AnalisisIATest(TestCase):
    """Integración de la Fase 2: ruta de análisis y render del análisis en el detalle."""

    def setUp(self):
        Usuario = get_user_model()
        self.sistema = Sistema.objects.create(codigo="BALANCES", nombre="Balances")
        self.solicitante = Usuario.objects.create_user(
            username="ana.testeo",
            password="clave123",
            rol="SOLICITANTE",
            first_name="Ana",
            last_name="Testeo",
        )
        UsuarioSistema.objects.create(usuario=self.solicitante, sistema=self.sistema)
        # Desarrollador con acceso al mismo sistema: es quien puede analizar.
        self.dev = Usuario.objects.create_user(
            username="dev.testeo",
            password="clave123",
            rol="DESARROLLADOR",
            first_name="Dev",
            last_name="Testeo",
        )
        UsuarioSistema.objects.create(usuario=self.dev, sistema=self.sistema)
        self.ticket = Ticket.objects.create(
            titulo="No calcula el total",
            sistema=self.sistema,
            solicitante=self.solicitante,
            descripcion_original="Al cargar la contabilidad el total queda en cero.",
            estado=EstadoTicket.PENDIENTE,
        )
        self.modelo = ModeloIA.objects.create(proveedor="Groq", modelo="test-model")
        # El dev analiza/participa SOLO si es colaborador activo del ticket
        # (misma regla que comentar/editar comentarios).
        TicketDesarrollador.objects.create(ticket=self.ticket, usuario=self.dev, activo=True)

    def _login_dev(self):
        self.client.login(username="dev.testeo", password="clave123")

    def _login_solicitante(self):
        self.client.login(username="ana.testeo", password="clave123")

    def _crear_analisis(self):
        return AnalisisIA.objects.create(
            ticket=self.ticket,
            tipo=TipoAnalisis.TECNICO,
            problema="Resumen técnico del problema.",
            comportamiento_esperado="Mostrar el total correcto.",
            estado_aprobacion=EstadoAprobacion.PENDIENTE_REVISION,
            modelo_ia=self.modelo,
        )

    def test_solicitante_no_ve_analisis(self):
        self._crear_analisis()
        self._login_solicitante()
        resp = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 200)
        # La sección de análisis no se renderiza para el solicitante: ni el
        # cuerpo de la tarjeta (id=cuerpo-analizar) ni el contenido del análisis.
        self.assertNotContains(resp, 'id="cuerpo-analizar"')
        self.assertNotContains(resp, "Resumen técnico del problema.")

    def test_solicitante_no_puede_analizar(self):
        self._login_solicitante()
        resp = self.client.post(reverse("ticket_analizar", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_ruta_analizar_redirige(self):
        self._login_dev()
        with patch("core.views._ejecutar_analisis") as mock_task:
            resp = self.client.post(reverse("ticket_analizar", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 302)
        mock_task.assert_called_once_with(self.ticket.pk)

    def test_detalle_muestra_analisis_tecnico(self):
        self._crear_analisis()
        self._login_dev()
        resp = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Análisis IA")
        self.assertContains(resp, "Resumen técnico del problema.")

    def test_detalle_sin_analisis_muestra_mensaje(self):
        self._login_dev()
        resp = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "todavía no tiene análisis generado")

    def test_analizar_error_muestra_mensaje(self):
        self._login_dev()
        with patch("core.views._ejecutar_analisis", side_effect=RuntimeError("API caida")):
            resp = self.client.post(reverse("ticket_analizar", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 302)
        resp2 = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertContains(resp2, "No se pudo generar el análisis")

    def test_analizar_ajax_exito_devuelve_redirect(self):
        self._login_dev()
        with patch("core.views._ejecutar_analisis") as mock_task:
            resp = self.client.post(
                reverse("ticket_analizar", args=[self.ticket.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(resp.json()["redirect"], reverse("ticket_detail", args=[self.ticket.pk]))
        # El cuerpo renderizado debe incluir el análisis más reciente.
        self.assertIn("id=\"cuerpo-analizar\"", resp.json()["cuerpo"])

    def test_analizar_ajax_exito_cuerpo_muestra_analisis_nuevo(self):
        analisis = self._crear_analisis()
        self._login_dev()
        with patch("core.views._ejecutar_analisis"):
            resp = self.client.post(
                reverse("ticket_analizar", args=[self.ticket.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.json()["cuerpo"]
        # Debe reflejar el análisis recién generado (proveedor + contenido), no el vacío.
        self.assertIn("Resumen técnico del problema.", cuerpo)
        self.assertIn("test-model", cuerpo)

    def test_analizar_ajax_retryable_devuelve_503(self):
        from ai.providers import RetryableProviderError

        self._login_dev()
        with patch("core.views._ejecutar_analisis", side_effect=RetryableProviderError("500")):
            resp = self.client.post(
                reverse("ticket_analizar", args=[self.ticket.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 503)
        self.assertTrue(resp.json()["retryable"])

    def test_analizar_ajax_retryable_dev_ve_detalle(self):
        from ai.providers import RetryableProviderError

        self._login_dev()
        with patch("core.views._ejecutar_analisis", side_effect=RetryableProviderError("500 del proveedor NVIDIA")):
            resp = self.client.post(
                reverse("ticket_analizar", args=[self.ticket.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 503)
        # dev/coord ven el detalle del error (no el mensaje genérico del solicitante).
        self.assertIn("NVIDIA", resp.json()["message"])

    def test_analizar_ajax_error_dev_ve_detalle(self):
        self._login_dev()
        with patch("core.views._ejecutar_analisis", side_effect=RuntimeError("API caida detalle interno")):
            resp = self.client.post(
                reverse("ticket_analizar", args=[self.ticket.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("API caida", resp.json()["message"])

    def test_analizar_ajax_error_duro_devuelve_400(self):
        self._login_dev()
        with patch("core.views._ejecutar_analisis", side_effect=RuntimeError("boom")):
            resp = self.client.post(
                reverse("ticket_analizar", args=[self.ticket.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["retryable"])

    def test_cerrado_no_se_reanaliza_y_chevron_de_colapso_se_mantiene(self):
        self._login_dev()
        self.ticket.estado = EstadoTicket.CERRADO
        self.ticket.save(update_fields=["estado"])
        # El chevron de colapsar/expandir la tarjeta sigue visible, pero el botón
        # Analizar/Reanalizar no.
        resp = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="toggle-analizar"')
        self.assertNotContains(resp, 'id="form-analizar"')
        self.assertContains(resp, "Ticket cerrado (análisis inamovible)")
        # Re-analizar vía POST queda bloqueado (403) en un ticket cerrado.
        resp = self.client.post(reverse("ticket_analizar", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_dev_no_colaborador_puede_analizar(self):
        # Desde 09/2026 el análisis IA está disponible para CUALQUIER dev/coord,
        # aunque no sea colaborador activo del ticket (se quitó esa restricción).
        self._login_dev()
        TicketDesarrollador.objects.filter(ticket=self.ticket, usuario=self.dev).delete()
        resp = self.client.post(reverse("ticket_analizar", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 302)
        resp2 = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertContains(resp2, 'id="form-analizar"')


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class TicketDetailHtmxTest(TestCase):
    """Las acciones del detalle (tomar/liberar/estado/comentarios) responden el
    partial #ticket-pagina cuando llegan con header HX-Request (swap HTMX), y
    siguen redirigiendo como fallback sin JS."""

    def setUp(self):
        Usuario = get_user_model()
        self.sistema = Sistema.objects.create(codigo="BALANCES", nombre="Balances")
        self.solicitante = Usuario.objects.create_user(
            username="dueño.htmx",
            password="clave123",
            rol="SOLICITANTE",
            first_name="Dueño",
            last_name="Htmx",
        )
        UsuarioSistema.objects.create(usuario=self.solicitante, sistema=self.sistema)
        self.dev = Usuario.objects.create_user(
            username="dev.htmx",
            password="clave123",
            rol="DESARROLLADOR",
            first_name="Dev",
            last_name="Htmx",
        )
        UsuarioSistema.objects.create(usuario=self.dev, sistema=self.sistema)
        self.ticket = Ticket.objects.create(
            titulo="Pantalla en blanco",
            sistema=self.sistema,
            solicitante=self.solicitante,
            descripcion_original="Al abrir el informe la pantalla queda en blanco.",
            estado=EstadoTicket.PENDIENTE,
        )

    def _login(self, usuario):
        self.client.login(username=usuario.username, password="clave123")

    def test_tomar_htmx_devuelve_partial(self):
        self._login(self.dev)
        resp = self.client.post(
            reverse("ticket_tomar", args=[self.ticket.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        # Respuesta parcial (no redirect): trae el wrapper #ticket-pagina.
        self.assertContains(resp, 'id="ticket-pagina"')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, EstadoTicket.EN_PROCESO)
        # Badge actualizado dentro del partial: ya no muestra el form de tomar.
        self.assertNotContains(resp, "Tomar ticket")

    def test_tomar_sin_htmx_redirige(self):
        self._login(self.dev)
        resp = self.client.post(reverse("ticket_tomar", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp["Location"],
            reverse("ticket_detail", args=[self.ticket.pk]),
        )

    def test_cerrar_htmx_devuelve_partial(self):
        self._login(self.dev)
        resp = self.client.post(
            reverse("ticket_cambiar_estado", args=[self.ticket.pk]),
            {"estado": "CERRADO"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="ticket-pagina"')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, EstadoTicket.CERRADO)
        # Al cerrar, el form de comentar se oculta (puede_comentar=False) en el partial.
        self.assertNotContains(resp, 'id="comentario-form"')

    def test_comentar_htmx_devuelve_partial_con_comentario(self):
        self._login(self.solicitante)
        resp = self.client.post(
            reverse("ticket_comentar", args=[self.ticket.pk]),
            {"cuerpo": "<p>Comentario con HTMX</p>"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="ticket-pagina"')
        self.assertContains(resp, "Comentario con HTMX")

    def test_eliminar_comentario_htmx_devuelve_partial(self):
        self._login(self.solicitante)
        com = Comentario.objects.create(
            ticket=self.ticket, usuario=self.solicitante, cuerpo="<p>Hola</p>"
        )
        resp = self.client.post(
            reverse("comentario_eliminar", args=[com.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="ticket-pagina"')
        self.assertNotContains(resp, "Hola")
        com.refresh_from_db()
        self.assertIsNotNone(com.eliminado_en)
        # Confirmación vía toast (fuera del flujo) en el partial.
        self.assertContains(resp, 'data-toast="Comentario eliminado."')

    def test_editar_comentario_htmx_devuelve_partial(self):
        self._login(self.solicitante)
        com = Comentario.objects.create(
            ticket=self.ticket, usuario=self.solicitante, cuerpo="<p>Antes</p>"
        )
        resp = self.client.post(
            reverse("comentario_editar", args=[com.pk]),
            {"cuerpo": "<p>Después</p>"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="ticket-pagina"')
        self.assertContains(resp, "Después")
        com.refresh_from_db()
        self.assertEqual(com.cuerpo, "<p>Después</p>")
        self.assertContains(resp, 'data-toast="Comentario actualizado."')


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class TicketEdicionTest(TestCase):
    """Editar/eliminar un ticket: solo el solicitante dueño, mientras el ticket
    no esté cerrado. Edición HTMX con toast; eliminación con soft delete que
    oculta el ticket de listado/detalle."""

    def setUp(self):
        Usuario = get_user_model()
        self.sistema = Sistema.objects.create(codigo="BALANCES", nombre="Balances")
        self.dueño = Usuario.objects.create_user(
            username="dueño.edit",
            password="clave123",
            rol="SOLICITANTE",
            first_name="Dueño",
            last_name="Edit",
        )
        UsuarioSistema.objects.create(usuario=self.dueño, sistema=self.sistema)
        self.dev = Usuario.objects.create_user(
            username="dev.edit",
            password="clave123",
            rol="DESARROLLADOR",
            first_name="Dev",
            last_name="Edit",
        )
        UsuarioSistema.objects.create(usuario=self.dev, sistema=self.sistema)
        self.ticket = Ticket.objects.create(
            titulo="Título original",
            sistema=self.sistema,
            solicitante=self.dueño,
            descripcion_original="<p>Descripción original</p>",
            estado=EstadoTicket.PENDIENTE,
        )

    def _login(self, usuario):
        self.client.login(username=usuario.username, password="clave123")

    def test_dueño_edita_ticket_htmx(self):
        self._login(self.dueño)
        resp = self.client.post(
            reverse("ticket_editar", args=[self.ticket.pk]),
            {"titulo": "Título nuevo", "descripcion_original": "<p>Descripción nueva</p>"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="ticket-pagina"')
        self.assertContains(resp, "Título nuevo")
        self.assertContains(resp, "Descripción nueva")
        self.assertContains(resp, 'data-toast="Ticket actualizado."')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.titulo, "Título nuevo")
        self.assertIsNotNone(self.ticket.modificado_en)

    def test_dueño_edita_ticket_sin_htmx_redirige(self):
        self._login(self.dueño)
        resp = self.client.post(
            reverse("ticket_editar", args=[self.ticket.pk]),
            {"titulo": "Título nuevo", "descripcion_original": "<p>Descripción nueva</p>"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp["Location"], reverse("ticket_detail", args=[self.ticket.pk])
        )

    def test_no_dueño_no_puede_editar(self):
        self._login(self.dev)
        resp = self.client.post(
            reverse("ticket_editar", args=[self.ticket.pk]),
            {"titulo": "Hack", "descripcion_original": "<p>Hack</p>"},
        )
        self.assertEqual(resp.status_code, 403)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.titulo, "Título original")

    def test_dueño_elimina_ticket_htmx_redirige_al_listado(self):
        self._login(self.dueño)
        resp = self.client.post(
            reverse("ticket_eliminar", args=[self.ticket.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(resp["HX-Redirect"], reverse("ticket_list"))
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.eliminado_en)
        # El ticket eliminado ya no aparece en el listado ni en el detalle.
        resp_lista = self.client.get(reverse("ticket_list"))
        self.assertNotContains(resp_lista, "Título original")
        resp_detalle = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(resp_detalle.status_code, 404)

    def test_dueño_elimina_ticket_sin_htmx_redirige(self):
        self._login(self.dueño)
        resp = self.client.post(reverse("ticket_eliminar", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("ticket_list"))

    def test_no_dueño_no_puede_eliminar(self):
        self._login(self.dev)
        resp = self.client.post(reverse("ticket_eliminar", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 403)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.eliminado_en)

    def test_cerrado_no_se_edita_ni_se_elimina(self):
        self.ticket.estado = EstadoTicket.CERRADO
        self.ticket.save(update_fields=["estado"])
        self._login(self.dueño)
        resp_editar = self.client.post(
            reverse("ticket_editar", args=[self.ticket.pk]),
            {"titulo": "X", "descripcion_original": "<p>X</p>"},
        )
        self.assertEqual(resp_editar.status_code, 403)
        resp_eliminar = self.client.post(
            reverse("ticket_eliminar", args=[self.ticket.pk])
        )
        self.assertEqual(resp_eliminar.status_code, 403)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_"))
    def test_listado_edicion_usa_pk_plano_en_quitar(self):
        """El botón 'quitar' del edit lleva el pk plano (sin prefijo): un valor
        'ticket-5' en adjuntos_eliminar rompe el parseo .isdigit() del backend y
        el archivo no se elimina."""
        self._login(self.dueño)
        Adjunto.objects.create(
            ticket=self.ticket,
            subido_por=self.dueño,
            archivo=SimpleUploadedFile("a.txt", b"a", content_type="text/plain"),
            nombre_archivo="a.txt",
            tipo_archivo=TipoAdjunto.DOCUMENTO,
        )
        resp = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-quitar-existente="%s"' % self.ticket.adjuntos.first().pk)
        self.assertNotContains(resp, 'data-quitar-existente="ticket-')

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_"))
    def test_editar_agrega_y_quita_adjuntos(self):
        self._login(self.dueño)
        viejo = Adjunto.objects.create(
            ticket=self.ticket,
            subido_por=self.dueño,
            archivo=SimpleUploadedFile("viejo.txt", b"viejo", content_type="text/plain"),
            nombre_archivo="viejo.txt",
            tipo_archivo=TipoAdjunto.DOCUMENTO,
        )
        nuevo = SimpleUploadedFile("nuevo.pdf", b"nuevo", content_type="application/pdf")
        resp = self.client.post(
            reverse("ticket_editar", args=[self.ticket.pk]),
            {
                "titulo": "Título nuevo",
                "descripcion_original": "<p>Descripción nueva</p>",
                "archivos": [nuevo],
                "adjuntos_eliminar": str(viejo.pk),
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, 302)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.titulo, "Título nuevo")
        nombres = set(self.ticket.adjuntos.values_list("nombre_archivo", flat=True))
        self.assertIn("nuevo.pdf", nombres)
        self.assertNotIn("viejo.txt", nombres)
        self.assertFalse(Adjunto.objects.filter(pk=viejo.pk).exists())
        self.assertFalse(os.path.exists(viejo.archivo.path))
