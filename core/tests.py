import json
import os
import re
import requests
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ai.providers import (
    GroqProvider,
    _leer_manual_sistema,
    _normalizar_host_ollama,
    _recortar_manual,
)
from ai.providers import OllamaProvider, RetryableProviderError, TIMEOUT_OLLAMA
from core.management.commands.seed_tickets import _username
from core.forms import _sanear_html
from core.views import _guardar_adjuntos
from core.models import (
    Adjunto,
    AnalisisIA,
    Comentario,
    EstadoTicket,
    LecturaTicket,
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
        # TEMPORAL: la vista pasa el flag usar_manual (default True si no llega
        # el campo del checkbox). Se vuelve a la firma simple al revertir.
        mock_task.assert_called_once_with(self.ticket.pk, usar_manual=True)

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


class ManualPromptTest(TestCase):
    """Fase manual txt: el manual de uso entra al prompt como referencia
    documental, junto a Sistema.prompt (se complementan, no se reemplazan)."""

    def setUp(self):
        self.sistema = Sistema.objects.create(
            codigo="BALANCES",
            nombre="Balances",
            prompt="Descripción oficial del sistema.",
        )
        self.modelo = ModeloIA.objects.create(proveedor="Groq", modelo="test-model")
        self.provider = GroqProvider(self.modelo)

    def _mensajes(self, manual_sistema=""):
        return self.provider._construir_mensajes(
            "La pantalla queda en blanco al cargar el balance.",
            titulo="Pantalla en blanco",
            sistema_nombre=self.sistema.nombre,
            prompt_sistema=self.sistema.prompt,
            manual_sistema=manual_sistema,
        )

    def _user_y_system(self, manual_sistema=""):
        mensajes = self._mensajes(manual_sistema=manual_sistema)
        user = next(m["content"] for m in mensajes if m["role"] == "user")
        system = next(m["content"] for m in mensajes if m["role"] == "system")
        return user, system

    def test_manual_entra_al_user_y_system_lo_declara_referencia(self):
        user, system = self._user_y_system(
            manual_sistema="El sistema permite cargar saldos y generar reportes."
        )
        self.assertIn("Manual de uso del sistema", user)
        self.assertIn("El sistema permite cargar saldos", user)
        # El system declara que el manual es material de referencia (no órdenes)
        # y queda cubierto por la defensa anti prompt-injection.
        self.assertIn("material documental de referencia", system)

    def test_prompt_y_manual_coexisten(self):
        user, _ = self._user_y_system(manual_sistema="Manual de uso completo.")
        self.assertIn("Descripción oficial del sistema.", user)
        self.assertIn("Manual de uso completo.", user)

    def test_sin_manual_no_aparece_bloque_y_prompt_sigue(self):
        user, _ = self._user_y_system()
        self.assertNotIn("Manual de uso del sistema", user)
        self.assertIn("Descripción oficial del sistema.", user)

    def test_leer_manual_desde_carpeta_por_codigo(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "BALANCES"
            carpeta.mkdir()
            (carpeta / "BALANCES_Documentacion_RAG.txt").write_text(
                "Contenido del manual.", encoding="utf-8"
            )
            with patch("ai.providers.MANUALES_DIR", Path(tmp)):
                self.assertEqual(
                    _leer_manual_sistema(self.sistema),
                    "Contenido del manual.",
                )

    def test_leer_manual_sin_carpeta_devuelve_vacio(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ai.providers.MANUALES_DIR", Path(tmp)):
                self.assertEqual(_leer_manual_sistema(self.sistema), "")

    def test_leer_manual_lee_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "FINANCIAMIENTO"
            carpeta.mkdir()
            (carpeta / "FINANCIAMIENTO_Documentacion_RAG.txt").write_text(
                "Manual con tildes: presentación, elecciones, borrador.",
                encoding="utf-8",
            )
            with patch("ai.providers.MANUALES_DIR", Path(tmp)):
                self.assertIn("presentación", _leer_manual_sistema(
                    Sistema(codigo="FINANCIAMIENTO")
                ))

    def test_truncado_por_max_manual_caracteres(self):
        with patch("ai.providers.MAX_MANUAL_CARACTERES", 50):
            recortado = _recortar_manual("x" * 200)
        self.assertTrue(recortado.startswith("x" * 50))
        self.assertIn("truncado por límite de tamaño", recortado)

    def test_sin_truncado_si_no_alcanza_el_tope(self):
        recortado = _recortar_manual("texto corto")
        self.assertEqual(recortado, "texto corto")


class OllamaHostTest(SimpleTestCase):
    """Normalización de OLLAMA_HOST a una URL usable como cliente (sin red).

    OLLAMA_HOST suele venir del entorno como bind del daemon ('0.0.0.0') o sin
    esquema/puerto; el provider debe convertirla a http://<host>:11434.
    """

    def _norm(self, host):
        return _normalizar_host_ollama(host)

    def test_vacio_usa_default(self):
        self.assertEqual(self._norm(""), "http://localhost:11434")
        self.assertEqual(self._norm(None), "http://localhost:11434")

    def test_bind_del_daemon_sin_esquema_ni_puerto(self):
        self.assertEqual(self._norm("0.0.0.0"), "http://127.0.0.1:11434")

    def test_bind_con_puerto_sin_esquema(self):
        self.assertEqual(self._norm("0.0.0.0:11434"), "http://127.0.0.1:11434")

    def test_host_puro_sin_esquema_ni_puerto(self):
        self.assertEqual(self._norm("localhost"), "http://localhost:11434")
        self.assertEqual(self._norm("127.0.0.1"), "http://127.0.0.1:11434")

    def test_host_puro_con_puerto_sin_esquema(self):
        self.assertEqual(self._norm("localhost:11434"), "http://localhost:11434")

    def test_url_completa_y_con_puerto(self):
        self.assertEqual(
            self._norm("http://localhost:11434"), "http://localhost:11434"
        )
        self.assertEqual(
            self._norm("http://127.0.0.1:11434"), "http://127.0.0.1:11434"
        )

    def test_url_sin_puerto_completa_el_default(self):
        self.assertEqual(self._norm("http://localhost"), "http://localhost:11434")

    def test_puerto_no_default_se_respeta(self):
        self.assertEqual(self._norm("http://mi-host:6000"), "http://mi-host:6000")
        self.assertEqual(self._norm("mi-host:6000"), "http://mi-host:6000")


class OllamaTimeoutTest(SimpleTestCase):
    """El provider de Ollama tiene timeout propio (decode local lento) y
    envuelve timeout/conexión/5xx como RetryableProviderError (sin red)."""

    def _provider(self):
        return OllamaProvider(
            ModeloIA(proveedor="Ollama", modelo="qwen2.5:3b-instruct-q4_K_M")
        )

    def _respuesta_ok(self):
        # La respuesta real de /api/chat es {"message": {"content": "<json string>"}}:
        # el content que escribe el modelo viaja como STRING, no como objeto.
        inner = (
            '{"problema":"a","comportamiento_esperado":"b",'
            '"comportamiento_observado":"c","pasos_reproducir":"d",'
            '"datos_relevantes":"e","informacion_faltante":"f"}'
        )
        content = json.dumps({"message": {"content": inner}})
        fake = requests.models.Response()
        fake.status_code = 200
        fake._content = content.encode()
        fake.encoding = "utf-8"
        fake.headers = {}
        return fake

    def test_usa_timeout_propio_no_el_generico(self):
        provider = self._provider()
        with patch("ai.providers.requests.post", return_value=self._respuesta_ok()) as post:
            provider.generar_analisis("ticket", "TECNICO")
        self.assertNotEqual(post.call_args.kwargs["timeout"], 60)
        self.assertEqual(post.call_args.kwargs["timeout"], TIMEOUT_OLLAMA)

    def test_timeout_es_retryable(self):
        provider = self._provider()
        with patch(
            "ai.providers.requests.post",
            side_effect=requests.exceptions.Timeout(),
        ):
            with self.assertRaises(RetryableProviderError):
                provider.generar_analisis("ticket", "TECNICO")

    def test_connection_error_es_retryable(self):
        provider = self._provider()
        with patch(
            "ai.providers.requests.post",
            side_effect=requests.exceptions.ConnectionError(),
        ):
            with self.assertRaises(RetryableProviderError):
                provider.generar_analisis("ticket", "TECNICO")

    def test_5xx_es_retryable(self):
        provider = self._provider()
        for code in (500, 502, 503, 504, 429):
            fake = requests.models.Response()
            fake.status_code = code
            fake.reason = "x"
            fake.url = "http://host/api/chat"
            fake.headers = {}
            with self.subTest(code=code), patch(
                "ai.providers.requests.post", return_value=fake
            ):
                with self.assertRaises(RetryableProviderError):
                    provider.generar_analisis("ticket", "TECNICO")

    def test_200_ok_parsea_el_analisis(self):
        provider = self._provider()
        with patch("ai.providers.requests.post", return_value=self._respuesta_ok()):
            analisis = provider.generar_analisis("ticket", "TECNICO")
        self.assertEqual(analisis.problema, "a")
        self.assertEqual(analisis.informacion_faltante, "f")


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

    def test_eliminar_comentario_borra_adjuntos_fisicos(self):
        self._login(self.solicitante)
        com = Comentario.objects.create(
            ticket=self.ticket, usuario=self.solicitante, cuerpo="<p>Hola</p>"
        )
        adj = Adjunto.objects.create(
            comentario=com,
            subido_por=self.solicitante,
            nombre_archivo="nota.txt",
            tipo_archivo=TipoAdjunto.DOCUMENTO,
            archivo=SimpleUploadedFile("nota.txt", b"contenido"),
        )
        ruta_fisica = adj.archivo.path
        self.assertTrue(os.path.exists(ruta_fisica))
        resp = self.client.post(reverse("comentario_eliminar", args=[com.pk]))
        self.assertRedirects(resp, reverse("ticket_detail", args=[self.ticket.pk]))
        com.refresh_from_db()
        self.assertIsNotNone(com.eliminado_en)
        # El adjunto se borra de BD y su archivo físico tambien.
        self.assertFalse(Adjunto.objects.filter(pk=adj.pk).exists())
        self.assertFalse(os.path.exists(ruta_fisica))

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

    def test_eliminar_ticket_casca_soft_delete_a_comentarios(self):
        com = Comentario.objects.create(
            ticket=self.ticket, usuario=self.dueño, cuerpo="<p>Hola</p>"
        )
        self._login(self.dueño)
        resp = self.client.post(
            reverse("ticket_eliminar", args=[self.ticket.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 204)
        self.ticket.refresh_from_db()
        com.refresh_from_db()
        self.assertIsNotNone(self.ticket.eliminado_en)
        self.assertEqual(com.eliminado_en, self.ticket.eliminado_en)
        # El manager por defecto no ve los comentarios cascaded; all_objects
        # conserva el histórico.
        self.assertFalse(Comentario.objects.filter(ticket=self.ticket).exists())
        self.assertTrue(Comentario.all_objects.filter(ticket=self.ticket).exists())

    def test_soft_delete_cascade_y_restore(self):
        com = Comentario.objects.create(
            ticket=self.ticket, usuario=self.dueño, cuerpo="<p>c1</p>"
        )
        self.ticket.soft_delete()
        self.ticket.refresh_from_db()
        com.refresh_from_db()
        self.assertEqual(com.eliminado_en, self.ticket.eliminado_en)
        # restore: vuelve el ticket y los comentarios cascaded a visible.
        self.ticket.restore()
        self.ticket.refresh_from_db()
        com.refresh_from_db()
        self.assertIsNone(self.ticket.eliminado_en)
        self.assertIsNone(com.eliminado_en)
        self.assertTrue(Comentario.objects.filter(ticket=self.ticket).exists())

    def test_soft_delete_no_pisa_borrado_individual_ni_restore_lo_vuelve(self):
        com_moderado = Comentario.objects.create(
            ticket=self.ticket, usuario=self.dueño, cuerpo="<p>mal</p>"
        )
        com_moderado.soft_delete()  # borrado individual previo (moderación)
        com_normal = Comentario.objects.create(
            ticket=self.ticket, usuario=self.dueño, cuerpo="<p>bien</p>"
        )
        self.ticket.soft_delete()
        com_moderado.refresh_from_db()
        com_normal.refresh_from_db()
        self.ticket.refresh_from_db()
        # El moderado conserva su propio eliminado_en (anterior al del ticket);
        # el normal se casca con el del ticket.
        self.assertNotEqual(com_moderado.eliminado_en, self.ticket.eliminado_en)
        self.assertEqual(com_normal.eliminado_en, self.ticket.eliminado_en)
        # restore solo revierte los cascaded: el moderado sigue borrado.
        self.ticket.restore()
        com_moderado.refresh_from_db()
        com_normal.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.eliminado_en)
        self.assertIsNotNone(com_moderado.eliminado_en)
        self.assertIsNone(com_normal.eliminado_en)

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


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class SeedTicketsResetAllTest(TestCase):
    """seed_tickets --reset_all: borra TODOS los tickets/comentarios/adjuntos (incluidos
    soft-deleted), borra los usuarios del seed, conserva usuarios no-demo y Sistemas, y
    reinicia el id de Ticket a 0 (proximo ticket = 1)."""

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_"))
    def test_reset_all_limpia_todo_y_reinicia_id(self):
        Usuario = get_user_model()
        self.sistema = Sistema.objects.create(codigo="BALANCES", nombre="Balances")
        seed_user = Usuario.objects.create_user(
            username=_username({"nombres": "María", "apellido": "López"}),
            password="soli", rol="SOLICITANTE",
        )
        UsuarioSistema.objects.create(usuario=seed_user, sistema=self.sistema)
        otro = Usuario.objects.create_user(
            username="dev.manual", password="x", rol="DESARROLLADOR"
        )
        t1 = Ticket.objects.create(
            titulo="Ticket demo", sistema=self.sistema, solicitante=seed_user,
            descripcion_original="<p>d1</p>", estado=EstadoTicket.PENDIENTE,
        )
        Comentario.objects.create(ticket=t1, usuario=seed_user, cuerpo="<p>c1</p>")
        t2 = Ticket.objects.create(
            titulo="Ticket soft-deleted", sistema=self.sistema, solicitante=seed_user,
            descripcion_original="<p>d2</p>", estado=EstadoTicket.PENDIENTE,
        )
        t2.soft_delete()
        Adjunto.objects.create(
            ticket=t1, subido_por=seed_user,
            archivo=SimpleUploadedFile("a.txt", b"a", content_type="text/plain"),
            nombre_archivo="a.txt", tipo_archivo=TipoAdjunto.DOCUMENTO,
        )
        ruta_fisica = t1.adjuntos.first().archivo.path

        call_command("seed_tickets", reset_all=True)

        self.assertEqual(Ticket.all_objects.count(), 0)
        self.assertEqual(Comentario.all_objects.count(), 0)
        self.assertEqual(Adjunto.objects.count(), 0)
        self.assertFalse(os.path.exists(ruta_fisica))
        self.assertFalse(Usuario.objects.filter(username="maria.lopez").exists())
        self.assertTrue(Usuario.objects.filter(username="dev.manual").exists())
        self.assertEqual(Sistema.objects.count(), 1)

        nuevo = Ticket.objects.create(
            titulo="Primero post-reset", sistema=self.sistema, solicitante=otro,
            descripcion_original="<p>n</p>", estado=EstadoTicket.PENDIENTE,
        )
        self.assertEqual(nuevo.pk, 1)


class SanitizadorCitasTest(TestCase):
    """Las citas del quote/reply se insertan como <blockquote><strong>...</strong>
    en el editor; el saneo con nh3 debe CONSERVAR ese formato (whitelist) y seguir
    eliminando scripts (garantiza que el reply con cita persiste al guardar)."""

    def test_sanear_html_conserva_cita_y_quita_script(self):
        html = (
            "<blockquote><strong>Ana escribió:</strong><br>"
            "El informe no abre en Chromium<br>con datos de octubre</blockquote>"
            "<p><br></p><script>alert(1)</script>"
        )
        limpio = _sanear_html(html)
        self.assertIn("<blockquote>", limpio)
        self.assertIn("<strong>Ana escribió:</strong>", limpio)
        self.assertIn("<br>", limpio)
        self.assertNotIn("<script", limpio)

    def test_sanear_html_escapa_cita_maliciosa(self):
        html = "<blockquote><strong>Dev escribió:</strong><br><img src=x onerror=alert(1)></blockquote>"
        limpio = _sanear_html(html)
        self.assertIn("<blockquote>", limpio)
        self.assertNotIn("onerror", limpio)
        self.assertNotIn("alert", limpio)


class RespuestaComentarioTest(TestCase):
    """Quote/reply (solo front, SIN cambios de modelo): la cita es una cajita fija
    fuera del editor (inalterable al editar), y al publicar el cliente la concatena
    al inicio del `cuerpo` como <blockquote>. Este bloque es la marca estructural:
    Quill no produce blockquotes, así que el único en el body ES la cita. El saneo
    con nh3 (whitelist conserva blockquote) garantiza que persiste al guardar."""

    def setUp(self):
        Usuario = get_user_model()
        self.sistema = Sistema.objects.create(codigo="BALANCES", nombre="Balances")
        self.solicitante = Usuario.objects.create_user(
            username="soli.cita", password="clave123", rol="SOLICITANTE",
            first_name="Soli", last_name="Cita",
        )
        UsuarioSistema.objects.create(usuario=self.solicitante, sistema=self.sistema)
        self.ticket = Ticket.objects.create(
            titulo="Test cita", sistema=self.sistema, solicitante=self.solicitante,
            descripcion_original="Detalle.", estado=EstadoTicket.PENDIENTE,
        )
        self.client.login(username="soli.cita", password="clave123")

    def _comentar(self, cuerpo):
        return self.client.post(
            reverse("ticket_comentar", args=[self.ticket.pk]),
            {"cuerpo": cuerpo},
            HTTP_HX_REQUEST="true",
        )

    def test_reply_con_cita_guarda_blockquote_y_cuerpo_propio(self):
        # El front concatena: cita (blockquote) + body del usuario (como lo haría
        # el htmx:configRequest al armar el parámetro `cuerpo`).
        body = (
            '<blockquote><strong>Respondiendo a Soli Cita:</strong><br>'
            'El informe no exporta a PDF con datos de octubre.</blockquote>'
            '<p>Mi respuesta</p>'
        )
        resp = self._comentar(body)
        self.assertEqual(resp.status_code, 200)
        reply = Comentario.objects.latest("pk")
        # El blockquote (cita) y el body del usuario se conservan tras sanear.
        self.assertIn("<blockquote>", reply.cuerpo)
        self.assertIn("Respondiendo a Soli Cita:", reply.cuerpo)
        self.assertIn("<p>Mi respuesta</p>", reply.cuerpo)

    def test_saneo_conserva_blockquote_pero_quita_script(self):
        # Si por algún vector entrara un script en la cita, nh3 lo elimina sin
        # romper el blockquote (mitigación XSS).
        body = (
            '<blockquote><strong>Ana escribió:</strong><br>'
            '<script>alert(1)</script>Texto.</blockquote><p>Ok</p>'
        )
        resp = self._comentar(body)
        self.assertEqual(resp.status_code, 200)
        reply = Comentario.objects.latest("pk")
        self.assertIn("<blockquote>", reply.cuerpo)
        self.assertNotIn("<script", reply.cuerpo)
        self.assertNotIn("alert", reply.cuerpo)
        self.assertIn("<p>Ok</p>", reply.cuerpo)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class AdjuntosExtensionesTest(TestCase):
    """Whitelist de extensiones de adjunto: ejecutables/scripts/svg/macros de
    Office quedan fuera (no se guarda ningún Adjunto) y las permitidas sí."""

    def setUp(self):
        Usuario = get_user_model()
        self.sistema = Sistema.objects.create(codigo="BALANCES", nombre="Balances")
        self.solicitante = Usuario.objects.create_user(
            username="ana.adjuntos",
            password="clave123",
            rol="SOLICITANTE",
            first_name="Ana",
            last_name="Adjuntos",
        )
        UsuarioSistema.objects.create(usuario=self.solicitante, sistema=self.sistema)
        self.ticket = Ticket.objects.create(
            titulo="Titulo",
            sistema=self.sistema,
            solicitante=self.solicitante,
            descripcion_original="<p>Descripcion</p>",
            estado=EstadoTicket.PENDIENTE,
        )

    def _login(self, usuario):
        self.client.login(username=usuario.username, password="clave123")

    def test_crear_ticket_rechaza_exe(self):
        self._login(self.solicitante)
        malo = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
        resp = self.client.post(
            reverse("ticket_create"),
            {
                "titulo": "Ticket",
                "sistema": self.sistema.pk,
                "descripcion_original": "<p>Descripcion</p>",
                "archivos": [malo],
            },
            format="multipart",
        )
        self.assertContains(resp, "virus.exe")
        self.assertContains(resp, "no tiene un tipo permitido")
        self.assertEqual(Adjunto.objects.count(), 0)

    def test_agregar_comentario_rechaza_svg(self):
        self._login(self.solicitante)
        malo = SimpleUploadedFile("logo.svg", b"<svg/>", content_type="image/svg+xml")
        resp = self.client.post(
            reverse("ticket_comentar", args=[self.ticket.pk]),
            {"cuerpo": "<p>Mira el svg</p>", "archivos": [malo]},
            HTTP_HX_REQUEST="true",
            format="multipart",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "logo.svg")
        self.assertContains(resp, "no tiene un tipo permitido")
        self.assertEqual(Adjunto.objects.count(), 0)
        # El comentario igual queda creado (comportamiento histórico del manejo
        # de error en agregar_comentario: el adjunto se intenta después de salvar).
        self.assertEqual(Comentario.objects.count(), 1)

    def test_editar_ticket_rechaza_docm(self):
        self._login(self.solicitante)
        malo = SimpleUploadedFile(
            "macros.docm", b"PK",
            content_type="application/vnd.ms-word.document.macroEnabled.12",
        )
        resp = self.client.post(
            reverse("ticket_editar", args=[self.ticket.pk]),
            {
                "titulo": "Nuevo",
                "descripcion_original": "<p>Nueva</p>",
                "archivos": [malo],
            },
            HTTP_HX_REQUEST="true",
            format="multipart",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "macros.docm")
        self.assertContains(resp, "no tiene un tipo permitido")
        self.assertEqual(Adjunto.objects.count(), 0)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_"))
    def test_guardar_adjuntos_acepta_permitidas(self):
        archivos = [
            SimpleUploadedFile("reporte.pdf", b"pdf", content_type="application/pdf"),
            SimpleUploadedFile(
                "datos.xlsx", b"xlsx",
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            SimpleUploadedFile("captura.png", b"png", content_type="image/png"),
            SimpleUploadedFile("captura.heic", b"heic", content_type="image/heic"),
            SimpleUploadedFile("respaldos.zip", b"zip", content_type="application/zip"),
            SimpleUploadedFile("notas.txt", b"txt", content_type="text/plain"),
        ]
        guardados = _guardar_adjuntos(archivos, ticket=self.ticket, usuario=self.solicitante)
        self.assertEqual(len(guardados), 6)
        self.assertEqual(Adjunto.objects.count(), 6)
        self.assertEqual(
            Adjunto.objects.filter(tipo_archivo=TipoAdjunto.IMAGEN).count(), 2  # png + heic
        )


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class LecturaTicketTest(TestCase):
    """Indicador de novedades en el listado: registra la última lectura por
    usuario y marca como "nuevo" lo no leído o con actividad posterior."""

    def setUp(self):
        Usuario = get_user_model()
        self.sistema = Sistema.objects.create(codigo="BALANCES", nombre="Balances")
        self.solicitante = Usuario.objects.create_user(
            username="ana.novedades",
            password="clave123",
            rol="SOLICITANTE",
            first_name="Ana",
            last_name="Novedades",
        )
        UsuarioSistema.objects.create(usuario=self.solicitante, sistema=self.sistema)
        self.dev = Usuario.objects.create_user(
            username="dev.novedades",
            password="clave123",
            rol="DESARROLLADOR",
            first_name="Dev",
            last_name="Novedades",
        )
        UsuarioSistema.objects.create(usuario=self.dev, sistema=self.sistema)
        self.ticket = Ticket.objects.create(
            titulo="Tickete de pruebas",
            sistema=self.sistema,
            solicitante=self.solicitante,
            descripcion_original="<p>Descripcion</p>",
            estado=EstadoTicket.PENDIENTE,
        )
        self.client.login(username="ana.novedades", password="clave123")

    def _abrir_detalle(self):
        return self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))

    def _novedad_html(self, resp, pk):
        """Devuelve '1'/'0' según el data-novedad del primer nodo del ticket
        (fila de tabla) en el HTML de la lista, o None si no está."""
        m = re.search(
            rf'data-ticket-id="{pk}"[^>]*data-novedad="(\d)"',
            resp.content.decode("utf-8"),
        )
        return m.group(1) if m else None

    def test_abrir_detalle_registra_lectura(self):
        self.assertEqual(LecturaTicket.objects.count(), 0)
        self._abrir_detalle()
        lectura = LecturaTicket.objects.get(
            usuario=self.solicitante, ticket=self.ticket
        )
        self.assertIsNotNone(lectura.ultima_lectura_en)
        # Abrir de nuevo no duplica: es un upsert por (usuario, ticket)
        self._abrir_detalle()
        self.assertEqual(LecturaTicket.objects.count(), 1)

    def test_toggle_circulo_default_todos_por_data_estado(self):
        # Por defecto se ven TODOS y el estado lo declara el server en
        # `data-estado="todos"`; el círculo medio (semicírculo) va `display:inline`
        # y el lleno `display:none`, vía style inline (no clases/atributos).
        resp = self.client.get(reverse("ticket_list"))
        html = resp.content.decode()
        self.assertTrue(re.search(r'id="novedades-toggle".*?data-estado="todos"', html, re.S))
        self.assertIn(
            'id="novedades-circle-lleno" viewBox="0 0 20 20" class="w-3 h-3 pointer-events-none" style="display:none"',
            html,
        )
        self.assertIn(
            'id="novedades-circle-medio" viewBox="0 0 20 20" class="w-3 h-3 pointer-events-none" style="display:inline"',
            html,
        )
        self.assertFalse(resp.context["es_mostrando_nuevos"])
        # Con ?mostrar=nuevos (p.ej. toggle server/HTMX) se invierte: lleno visible.
        resp = self.client.get(reverse("ticket_list"), {"mostrar": "nuevos"})
        html = resp.content.decode()
        self.assertTrue(re.search(r'id="novedades-toggle".*?data-estado="nuevos"', html, re.S))
        self.assertIn(
            'id="novedades-circle-lleno" viewBox="0 0 20 20" class="w-3 h-3 pointer-events-none" style="display:inline"',
            html,
        )
        self.assertIn(
            'id="novedades-circle-medio" viewBox="0 0 20 20" class="w-3 h-3 pointer-events-none" style="display:none"',
            html,
        )
        self.assertTrue(resp.context["es_mostrando_nuevos"])

    def test_sin_lectura_es_novedad_y_abrir_la_limpia(self):
        resp = self.client.get(reverse("ticket_list"))
        self.assertEqual(self._novedad_html(resp, self.ticket.pk), "1")
        self._abrir_detalle()
        resp = self.client.get(reverse("ticket_list"))
        self.assertEqual(self._novedad_html(resp, self.ticket.pk), "0")

    def test_comentario_posterior_genera_novedad(self):
        self._abrir_detalle()
        Comentario.objects.create(
            ticket=self.ticket, usuario=self.solicitante, cuerpo="<p>Nuevo comentario</p>"
        )
        resp = self.client.get(reverse("ticket_list"))
        self.assertEqual(self._novedad_html(resp, self.ticket.pk), "1")

    def test_cambio_de_estado_posterior_genera_novedad(self):
        self._abrir_detalle()
        self.ticket.estado = EstadoTicket.CERRADO
        self.ticket.cerrado_en = timezone.now()
        self.ticket.save()
        resp = self.client.get(reverse("ticket_list"))
        self.assertEqual(self._novedad_html(resp, self.ticket.pk), "1")

    def test_edicion_posterior_genera_novedad(self):
        self._abrir_detalle()
        self.ticket.modificado_en = timezone.now()
        self.ticket.save()
        resp = self.client.get(reverse("ticket_list"))
        self.assertEqual(self._novedad_html(resp, self.ticket.pk), "1")

    def test_comentario_eliminado_no_genera_novedad(self):
        self._abrir_detalle()
        comentario = Comentario.objects.create(
            ticket=self.ticket, usuario=self.solicitante, cuerpo="<p>Otro mas</p>"
        )
        comentario.soft_delete()
        resp = self.client.get(reverse("ticket_list"))
        self.assertEqual(self._novedad_html(resp, self.ticket.pk), "0")

    @override_settings(MODO_FILTRO_CLIENTE=False)
    def test_filtro_server_mostrar_nuevos(self):
        # Ticket B: nunca leído -> novedad. Ticket A: leído y sin actividad -> no.
        ticket_b = Ticket.objects.create(
            titulo="Sin leer",
            sistema=self.sistema,
            solicitante=self.solicitante,
            descripcion_original="<p>B</p>",
            estado=EstadoTicket.PENDIENTE,
        )
        self._abrir_detalle()
        resp = self.client.get(reverse("ticket_list"), {"mostrar": "nuevos"})
        ids = [t.pk for t in resp.context["tickets"]]
        self.assertIn(ticket_b.pk, ids)
        self.assertNotIn(self.ticket.pk, ids)

    @override_settings(MODO_FILTRO_CLIENTE=False)
    def test_filtro_server_incluye_comentario_posterior(self):
        self._abrir_detalle()
        Comentario.objects.create(
            ticket=self.ticket, usuario=self.solicitante, cuerpo="<p>Actividad</p>"
        )
        resp = self.client.get(reverse("ticket_list"), {"mostrar": "nuevos"})
        self.assertIn(self.ticket.pk, [t.pk for t in resp.context["tickets"]])

    @override_settings(MODO_FILTRO_CLIENTE=False)
    def test_filtro_server_sin_parametro_devuelve_todo(self):
        self._abrir_detalle()
        self.ticket.cerrado_en = timezone.now()
        self.ticket.estado = EstadoTicket.CERRADO
        self.ticket.save()
        resp = self.client.get(reverse("ticket_list"))
        self.assertIn(self.ticket.pk, [t.pk for t in resp.context["tickets"]])

    def test_reapertura_posterior_genera_novedad(self):
        # ana lee el ticket; otro desarrollador lo reabre -> ana lo ve como novedad.
        self._abrir_detalle()
        self.client.post(
            reverse("ticket_cambiar_estado", args=[self.ticket.pk]),
            {"estado": "CERRADO"},
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, EstadoTicket.CERRADO)
        self.client.logout()
        self.client.login(username="dev.novedades", password="clave123")
        self.client.post(
            reverse("ticket_cambiar_estado", args=[self.ticket.pk]),
            {"estado": "REABIERTO"},
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, EstadoTicket.REABIERTO)
        self.assertIsNotNone(self.ticket.reabierto_en)
        self.client.logout()
        self.client.login(username="ana.novedades", password="clave123")
        resp = self.client.get(reverse("ticket_list"))
        self.assertEqual(self._novedad_html(resp, self.ticket.pk), "1")

    def test_reabrir_el_propio_no_auto_marca(self):
        # ana cierra y reabre su propio ticket: en el flujo real el redirect al
        # detalle (o el swap HTMX) refresca su lectura, así no se auto-marca.
        self._abrir_detalle()
        self.client.post(
            reverse("ticket_cambiar_estado", args=[self.ticket.pk]),
            {"estado": "CERRADO"},
            follow=True,
        )
        self.client.post(
            reverse("ticket_cambiar_estado", args=[self.ticket.pk]),
            {"estado": "REABIERTO"},
            follow=True,
        )
        resp = self.client.get(reverse("ticket_list"))
        self.assertEqual(self._novedad_html(resp, self.ticket.pk), "0")

    def test_editar_comentario_posterior_genera_novedad(self):
        # Comentario creado, ambos leen; luego el autor lo edita -> el otro lo
        # ve como novedad, el autor no (su lectura se refresca al editar).
        comentario = Comentario.objects.create(
            ticket=self.ticket, usuario=self.solicitante, cuerpo="<p>v1</p>"
        )
        self._abrir_detalle()
        self.client.login(username="dev.novedades", password="clave123")
        self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        resp = self.client.get(reverse("ticket_list"))
        self.assertEqual(self._novedad_html(resp, self.ticket.pk), "0")
        self.client.login(username="ana.novedades", password="clave123")
        self.client.post(
            reverse("comentario_editar", args=[comentario.pk]),
            {"cuerpo": "<p>v2</p>"},
            HTTP_HX_REQUEST="true",
        )
        self.client.login(username="dev.novedades", password="clave123")
        resp = self.client.get(reverse("ticket_list"))
        self.assertEqual(self._novedad_html(resp, self.ticket.pk), "1")
        self.client.login(username="ana.novedades", password="clave123")
        resp = self.client.get(reverse("ticket_list"))
        self.assertEqual(self._novedad_html(resp, self.ticket.pk), "0")

    @override_settings(MODO_FILTRO_CLIENTE=False)
    def test_filtro_server_incluye_reapertura(self):
        self._abrir_detalle()
        self.client.post(
            reverse("ticket_cambiar_estado", args=[self.ticket.pk]),
            {"estado": "CERRADO"},
        )
        self.client.post(
            reverse("ticket_cambiar_estado", args=[self.ticket.pk]),
            {"estado": "REABIERTO"},
        )
        resp = self.client.get(reverse("ticket_list"), {"mostrar": "nuevos"})
        self.assertIn(self.ticket.pk, [t.pk for t in resp.context["tickets"]])

    @override_settings(MODO_FILTRO_CLIENTE=False)
    def test_filtro_server_incluye_comentario_editado(self):
        comentario = Comentario.objects.create(
            ticket=self.ticket, usuario=self.solicitante, cuerpo="<p>v1</p>"
        )
        self._abrir_detalle()
        self.client.login(username="dev.novedades", password="clave123")
        self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.client.login(username="ana.novedades", password="clave123")
        self.client.post(
            reverse("comentario_editar", args=[comentario.pk]),
            {"cuerpo": "<p>v2</p>"},
            HTTP_HX_REQUEST="true",
        )
        self.client.login(username="dev.novedades", password="clave123")
        resp = self.client.get(reverse("ticket_list"), {"mostrar": "nuevos"})
        self.assertIn(self.ticket.pk, [t.pk for t in resp.context["tickets"]])

    @override_settings(MODO_FILTRO_CLIENTE=False)
    def test_toggle_contexto_circulo(self):
        resp = self.client.get(reverse("ticket_list"), {"mostrar": "nuevos"})
        self.assertTrue(resp.context["es_mostrando_nuevos"])
        self.assertNotIn("mostrar=", resp.context["url_lista_novedades"])
        resp = self.client.get(reverse("ticket_list"))
        self.assertFalse(resp.context["es_mostrando_nuevos"])
        self.assertIn("mostrar=nuevos", resp.context["url_lista_novedades"])


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class XssVistaTest(TestCase):
    """Nivel vista (E2E): postear vectores XSS reales vía el test client y
    verificar que llegan saneados a la DB (sin <script>/eventos/URLs
    peligrosas) y que el render del detalle no expone esos tags. Se usa POST
    HTTP directo (sin Quill) para simular un atacante que saltea el editor."""

    VECTORES = [
        "<p>Hola <script>alert(1)</script> mundo</p>",
        '<p><img src=x onerror=alert(1)></p>',
        '<p><a href="javascript:alert(1)">click</a></p>',
        '<p><svg onload=alert(1)></svg></p>',
        '<details open ontoggle=alert(1)>detalle</details>',
        '<p>Hola <iframe src="javascript:alert(1)"></iframe> mundo</p>',
    ]

    def setUp(self):
        Usuario = get_user_model()
        self.sistema = Sistema.objects.create(codigo="BALANCES", nombre="Balances")
        self.solicitante = Usuario.objects.create_user(
            username="ana.xss", password="clave123", rol="SOLICITANTE",
            first_name="Ana", last_name="XSS",
        )
        UsuarioSistema.objects.create(usuario=self.solicitante, sistema=self.sistema)
        self.ticket = Ticket.objects.create(
            titulo="Titulo", sistema=self.sistema, solicitante=self.solicitante,
            descripcion_original="<p>Ok</p>", estado=EstadoTicket.PENDIENTE,
        )
        self.client.login(username="ana.xss", password="clave123")

    def _sano(self, html):
        return all(
            token not in html
            for token in ("<script", "onerror=", "onload=", "ontoggle=", "javascript:", "<iframe", "<svg")
        )

    def test_crear_ticket_no_guarda_scripts(self):
        for i, vector in enumerate(self.VECTORES):
            resp = self.client.post(
                reverse("ticket_create"),
                {
                    "titulo": f"Ticket XSS {i}",
                    "sistema": self.sistema.pk,
                    "descripcion_original": vector,
                },
            )
            # Algunos vectores sanear a contenido vacío → el form pide el
            # campo (200 con errores); el resto crea y redirige (302).
            self.assertIn(resp.status_code, (200, 302), f"vector {vector!r}")
        tickets = Ticket.objects.exclude(pk=self.ticket.pk)
        for t in tickets:
            self.assertTrue(self._sano(t.descripcion_original), repr(t.descripcion_original))
        # Por lo menos los vectores que sobreviven al saneo llegaron a crearse.
        overvivientes = sum(1 for v in self.VECTORES if _sanear_html(v))
        self.assertEqual(tickets.count(), overvivientes)

    def test_comentar_no_guarda_scripts(self):
        for vector in self.VECTORES:
            resp = self.client.post(
                reverse("ticket_comentar", args=[self.ticket.pk]),
                {"cuerpo": vector},
                HTTP_HX_REQUEST="true",
            )
            self.assertEqual(resp.status_code, 200, f"vector {vector!r}")
        comentarios = Comentario.objects.all()
        self.assertEqual(comentarios.count(), len(self.VECTORES))
        for c in comentarios:
            self.assertTrue(self._sano(c.cuerpo), repr(c.cuerpo))

    def test_editar_ticket_sanea_descripcion(self):
        resp = self.client.post(
            reverse("ticket_editar", args=[self.ticket.pk]),
            {"titulo": "Nuevo titulo", "descripcion_original": "<p>Hola <script>alert(2)</script></p>"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertNotIn("<script", self.ticket.descripcion_original)
        self.assertIn("Hola", self.ticket.descripcion_original)  # texto se conserva

    def test_detalle_no_renderiza_onerror_de_comentario(self):
        # Camino real del atacante: el comentario entra por el form (que sanea).
        self.client.post(
            reverse("ticket_comentar", args=[self.ticket.pk]),
            {"cuerpo": '<p>Mira <img src=x onerror=alert(1)></p>'},
            HTTP_HX_REQUEST="true",
        )
        resp = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mira")
        # Sin onerror en todo el render (ni en el comentario ni en otra parte).
        self.assertNotIn("onerror", resp.content.decode("utf-8"))
        self.assertNotIn("alert(1)", resp.content.decode("utf-8"))

    def test_detalle_no_renderiza_scripts_de_ticket(self):
        # El ticket (ya limpio en DB por el saneo al crear) renderiza sin tags vivos.
        self.ticket.descripcion_original = _sanear_html(
            "<p>Buen texto <script>alert(1)</script> y sigue</p>"
        )
        self.ticket.save()
        resp = self.client.get(reverse("ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Buen texto")
        self.assertNotIn("alert(1)", resp.content.decode("utf-8"))

