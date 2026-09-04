from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    AnalisisIA,
    EstadoTicket,
    ModeloIA,
    Sistema,
    Ticket,
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
        self.ticket = Ticket.objects.create(
            titulo="No calcula el total",
            sistema=self.sistema,
            solicitante=self.solicitante,
            descripcion_original="Al cargar la contabilidad el total queda en cero.",
            estado=EstadoTicket.PENDIENTE,
        )
        self.modelo = ModeloIA.objects.create(proveedor="Groq", modelo="test-model")

    def _crear_analisis(self):
        return AnalisisIA.objects.create(
            ticket=self.ticket,
            tipo=TipoAnalisis.CONCEPTUAL,
            problema="Resumen técnico del problema.",
            comportamiento_esperado="Mostrar el total correcto.",
            estado_aprobacion=EstadoAprobacion.PENDIENTE_REVISION,
            modelo_ia=self.modelo,
        )

    def test_ruta_analizar_redirige(self):
        self.client.login(username="ana.testeo", password="clave123")
        with patch("core.views._ejecutar_analisis") as mock_task:
            resp = self.client.post(reverse("ticket_analizar", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 302)
        mock_task.assert_called_once_with(self.ticket.pk)

    def test_detalle_muestra_analisis_conceptual(self):
        self._crear_analisis()
        self.client.login(username="ana.testeo", password="clave123")
        resp = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Análisis IA · Conceptual")
        self.assertContains(resp, "Resumen técnico del problema.")

    def test_detalle_sin_analisis_muestra_mensaje(self):
        self.client.login(username="ana.testeo", password="clave123")
        resp = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "todavía no tiene análisis generado")

    def test_analizar_error_muestra_mensaje(self):
        self.client.login(username="ana.testeo", password="clave123")
        with patch("core.views._ejecutar_analisis", side_effect=RuntimeError("API caida")):
            resp = self.client.post(reverse("ticket_analizar", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 302)
        resp2 = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertContains(resp2, "No se pudo generar el análisis")

    def test_analizar_ajax_exito_devuelve_redirect(self):
        self.client.login(username="ana.testeo", password="clave123")
        with patch("core.views._ejecutar_analisis") as mock_task:
            resp = self.client.post(
                reverse("ticket_analizar", args=[self.ticket.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(resp.json()["redirect"], reverse("ticket_detail", args=[self.ticket.pk]))

    def test_analizar_ajax_retryable_devuelve_503(self):
        from ai.providers import RetryableProviderError

        self.client.login(username="ana.testeo", password="clave123")
        with patch("core.views._ejecutar_analisis", side_effect=RetryableProviderError("500")):
            resp = self.client.post(
                reverse("ticket_analizar", args=[self.ticket.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 503)
        self.assertTrue(resp.json()["retryable"])

    def test_analizar_ajax_retryable_solicitante_ve_mensaje_generico(self):
        from ai.providers import RetryableProviderError

        self.client.login(username="ana.testeo", password="clave123")
        with patch("core.views._ejecutar_analisis", side_effect=RetryableProviderError("500 del proveedor NVIDIA")):
            resp = self.client.post(
                reverse("ticket_analizar", args=[self.ticket.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 503)
        self.assertNotIn("NVIDIA", resp.json()["message"])
        self.assertIn("temporalmente saturado", resp.json()["message"])

    def test_analizar_ajax_error_solicitante_ve_mensaje_generico(self):
        self.client.login(username="ana.testeo", password="clave123")
        with patch("core.views._ejecutar_analisis", side_effect=RuntimeError("API caida detalle interno")):
            resp = self.client.post(
                reverse("ticket_analizar", args=[self.ticket.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn("API caida", resp.json()["message"])

    def test_analizar_ajax_error_duro_devuelve_400(self):
        self.client.login(username="ana.testeo", password="clave123")
        with patch("core.views._ejecutar_analisis", side_effect=RuntimeError("boom")):
            resp = self.client.post(
                reverse("ticket_analizar", args=[self.ticket.pk]),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["retryable"])
