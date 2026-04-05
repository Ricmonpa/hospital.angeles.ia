"""Tests for OpenDoc SAT SOAP Web Service Client.

Validates:
- Dataclasses (SATAuthToken, SolicitudDescarga, VerificacionCFDI, etc.)
- Enums (EstadoSolicitud, EstadoCFDI, EstadoCancelacion)
- Exceptions
- SOAP request transport (_soap_request) with mocked HTTP
- Authentication flow (authenticate)
- Descarga Masiva lifecycle (solicitar, verificar, descargar)
- Verificador CFDI (public, no auth)
- Cancelación safety gates
- Fallback orchestrator (SOAP → Playwright)
- WhatsApp summary formatting
- XML parsing helpers

All tests mock HTTP calls — zero real SAT endpoint contact.
"""

import asyncio
import base64
import io
import zipfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

from src.tools.sat_ws_client import (
    # Enums
    EstadoSolicitud,
    EstadoCFDI,
    EstadoCancelacion,
    # Dataclasses
    SATAuthToken,
    SolicitudDescarga,
    VerificacionCFDI,
    ResultadoCancelacion,
    DescargaMasivaResult,
    # Exceptions
    SATWSAuthError,
    SATWSSolicitudError,
    SATWSDownloadError,
    SATWSCancelacionRequiresConfirmation,
    SATWSServiceUnavailable,
    # Functions
    _soap_request,
    _parse_soap_fault,
    _build_soap_envelope,
    _extract_xml_text,
    _extract_xml_attr,
    authenticate,
    solicitar_descarga,
    verificar_solicitud,
    descargar_paquete,
    descarga_masiva_completa,
    verificar_cfdi,
    preparar_cancelacion,
    ejecutar_cancelacion,
    download_cfdis_with_fallback,
    # Constants
    SAT_WS_AUTENTICACION_URL,
    SAT_WS_SOLICITUD_URL,
    SAT_WS_VERIFICACION_URL,
    SAT_WS_DESCARGA_URL,
    SAT_WS_VERIFICADOR_URL,
    SAT_WS_CANCELACION_URL,
    NS_DM,
    NS_SOAP,
)


# ─── Helpers ─────────────────────────────────────────────────────────

def _make_valid_token(rfc="MOPR881228EF9"):
    now = datetime.now(timezone.utc)
    return SATAuthToken(
        token="test-token-abc",
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        rfc=rfc,
    )


def _make_expired_token(rfc="MOPR881228EF9"):
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    return SATAuthToken(
        token="expired",
        created_at=past.isoformat(),
        expires_at=(past + timedelta(minutes=5)).isoformat(),
        rfc=rfc,
    )


def _make_zip_with_xmls(filenames=None):
    """Create a base64-encoded zip file containing dummy XMLs."""
    if filenames is None:
        filenames = ["cfdi1.xml", "cfdi2.xml"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in filenames:
            zf.writestr(name, f'<cfdi>{name}</cfdi>')
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _soap_response(body_content):
    """Wrap content in a SOAP envelope for test responses."""
    return (
        f'<s:Envelope xmlns:s="{NS_SOAP}">'
        f'<s:Body>{body_content}</s:Body>'
        f'</s:Envelope>'
    )


# ─── Test: Enums ─────────────────────────────────────────────────────

class TestEnums:
    def test_estado_solicitud_values(self):
        assert EstadoSolicitud.ACEPTADA.value == "Aceptada"
        assert EstadoSolicitud.TERMINADA.value == "Terminada"
        assert EstadoSolicitud.RECHAZADA.value == "Rechazada"
        assert len(EstadoSolicitud) == 6

    def test_estado_cfdi_values(self):
        assert EstadoCFDI.VIGENTE.value == "Vigente"
        assert EstadoCFDI.CANCELADO.value == "Cancelado"
        assert len(EstadoCFDI) == 3

    def test_estado_cancelacion_values(self):
        assert EstadoCancelacion.CANCELADO.value == "Cancelado"
        assert EstadoCancelacion.EN_PROCESO.value == "En proceso de cancelación"
        assert len(EstadoCancelacion) == 5


# ─── Test: Exceptions ────────────────────────────────────────────────

class TestExceptions:
    def test_auth_error(self):
        with pytest.raises(SATWSAuthError):
            raise SATWSAuthError("test")

    def test_solicitud_error(self):
        with pytest.raises(SATWSSolicitudError):
            raise SATWSSolicitudError("test")

    def test_download_error(self):
        with pytest.raises(SATWSDownloadError):
            raise SATWSDownloadError("test")

    def test_cancelacion_requires_confirmation(self):
        with pytest.raises(SATWSCancelacionRequiresConfirmation):
            raise SATWSCancelacionRequiresConfirmation("test")

    def test_service_unavailable(self):
        with pytest.raises(SATWSServiceUnavailable):
            raise SATWSServiceUnavailable("test")

    def test_all_inherit_exception(self):
        for exc in [SATWSAuthError, SATWSSolicitudError, SATWSDownloadError,
                     SATWSCancelacionRequiresConfirmation, SATWSServiceUnavailable]:
            assert issubclass(exc, Exception)


# ─── Test: SATAuthToken ─────────────────────────────────────────────

class TestSATAuthToken:
    def test_create(self):
        t = _make_valid_token()
        assert t.token == "test-token-abc"
        assert t.rfc == "MOPR881228EF9"

    def test_to_dict(self):
        d = _make_valid_token().to_dict()
        assert isinstance(d, dict)
        assert "token" in d
        assert "rfc" in d

    def test_is_expired_false(self):
        assert _make_valid_token().is_expired() is False

    def test_is_expired_true(self):
        assert _make_expired_token().is_expired() is True

    def test_invalid_date_is_expired(self):
        t = SATAuthToken(token="x", created_at="x", expires_at="bad", rfc="X")
        assert t.is_expired() is True


# ─── Test: SolicitudDescarga ────────────────────────────────────────

class TestSolicitudDescarga:
    def test_create(self):
        s = SolicitudDescarga(
            id_solicitud="abc-123", rfc_solicitante="MOPR881228EF9",
            tipo_solicitud="recibidos", fecha_inicio="2026-01-01",
            fecha_fin="2026-01-31", estado=EstadoSolicitud.ACEPTADA.value,
        )
        assert s.id_solicitud == "abc-123"

    def test_to_dict(self):
        s = SolicitudDescarga(
            id_solicitud="x", rfc_solicitante="x", tipo_solicitud="x",
            fecha_inicio="x", fecha_fin="x", estado="x",
        )
        assert isinstance(s.to_dict(), dict)

    def test_whatsapp_aceptada(self):
        s = SolicitudDescarga(
            id_solicitud="abcdef1234567890xyz", rfc_solicitante="X",
            tipo_solicitud="recibidos", fecha_inicio="2026-01-01",
            fecha_fin="2026-01-31", estado=EstadoSolicitud.ACEPTADA.value,
        )
        wsp = s.resumen_whatsapp()
        assert "━━━" in wsp
        assert "⏳" in wsp
        assert "Recibidos" in wsp

    def test_whatsapp_terminada(self):
        s = SolicitudDescarga(
            id_solicitud="x", rfc_solicitante="X",
            tipo_solicitud="emitidos", fecha_inicio="2026-01-01",
            fecha_fin="2026-01-31", estado=EstadoSolicitud.TERMINADA.value,
            numero_cfdis=42, ids_paquetes=["pkg1", "pkg2"],
        )
        wsp = s.resumen_whatsapp()
        assert "✅" in wsp
        assert "42" in wsp
        assert "2" in wsp

    def test_whatsapp_rechazada(self):
        s = SolicitudDescarga(
            id_solicitud="x", rfc_solicitante="X",
            tipo_solicitud="recibidos", fecha_inicio="x",
            fecha_fin="x", estado=EstadoSolicitud.RECHAZADA.value,
        )
        wsp = s.resumen_whatsapp()
        assert "❌" in wsp


# ─── Test: VerificacionCFDI ─────────────────────────────────────────

class TestVerificacionCFDI:
    def test_create(self):
        v = VerificacionCFDI(
            uuid="abc", rfc_emisor="X", rfc_receptor="Y",
            total="1000.00", estado=EstadoCFDI.VIGENTE.value,
        )
        assert v.estado == "Vigente"

    def test_to_dict(self):
        v = VerificacionCFDI(
            uuid="x", rfc_emisor="x", rfc_receptor="x",
            total="0", estado="x",
        )
        assert isinstance(v.to_dict(), dict)

    def test_whatsapp_vigente(self):
        v = VerificacionCFDI(
            uuid="abc-def", rfc_emisor="EMIT", rfc_receptor="RECV",
            total="5000.00", estado=EstadoCFDI.VIGENTE.value,
        )
        wsp = v.resumen_whatsapp()
        assert "✅" in wsp
        assert "abc-def" in wsp
        assert "5000" in wsp

    def test_whatsapp_cancelado(self):
        v = VerificacionCFDI(
            uuid="x", rfc_emisor="x", rfc_receptor="x",
            total="0", estado=EstadoCFDI.CANCELADO.value,
        )
        assert "❌" in v.resumen_whatsapp()


# ─── Test: ResultadoCancelacion ─────────────────────────────────────

class TestResultadoCancelacion:
    def test_create(self):
        r = ResultadoCancelacion(
            uuid="abc", rfc_emisor="X",
            estado=EstadoCancelacion.CANCELADO.value,
        )
        assert r.estado == "Cancelado"

    def test_to_dict_excludes_acuse(self):
        r = ResultadoCancelacion(
            uuid="x", rfc_emisor="x", estado="x",
            acuse_xml="<big>xml</big>",
        )
        d = r.to_dict()
        assert "acuse_xml" not in d

    def test_whatsapp(self):
        r = ResultadoCancelacion(
            uuid="abc-123", rfc_emisor="MOPR",
            estado=EstadoCancelacion.CANCELADO.value,
            fecha_cancelacion="2026-03-01",
        )
        wsp = r.resumen_whatsapp()
        assert "✅" in wsp
        assert "abc-123" in wsp


# ─── Test: DescargaMasivaResult ─────────────────────────────────────

class TestDescargaMasivaResult:
    def test_create(self):
        r = DescargaMasivaResult()
        assert r.total_descargados == 0
        assert r.canal == "soap"

    def test_to_dict(self):
        r = DescargaMasivaResult(total_descargados=5)
        d = r.to_dict()
        assert d["total_descargados"] == 5
        assert d["canal"] == "soap"

    def test_whatsapp(self):
        r = DescargaMasivaResult(
            total_descargados=10, canal="soap",
            solicitud=SolicitudDescarga(
                id_solicitud="x", rfc_solicitante="x",
                tipo_solicitud="recibidos", fecha_inicio="x",
                fecha_fin="x", estado=EstadoSolicitud.TERMINADA.value,
            ),
        )
        wsp = r.resumen_whatsapp()
        assert "10" in wsp
        assert "SOAP" in wsp


# ─── Test: XML Helpers ───────────────────────────────────────────────

class TestXMLHelpers:
    def test_extract_xml_text(self):
        xml = '<root><Name>hello</Name></root>'
        assert _extract_xml_text(xml, "Name") == "hello"

    def test_extract_xml_text_namespaced(self):
        xml = '<root xmlns:ns="http://test"><ns:Val>42</ns:Val></root>'
        assert _extract_xml_text(xml, "Val") == "42"

    def test_extract_xml_text_missing(self):
        xml = '<root><Other>x</Other></root>'
        assert _extract_xml_text(xml, "Name") == ""

    def test_extract_xml_text_invalid(self):
        assert _extract_xml_text("not xml", "x") == ""

    def test_extract_xml_attr(self):
        xml = '<root><Result CodEstatus="5000" Msg="ok"/></root>'
        assert _extract_xml_attr(xml, "Result", "CodEstatus") == "5000"

    def test_extract_xml_attr_missing(self):
        xml = '<root><Result other="x"/></root>'
        assert _extract_xml_attr(xml, "Result", "CodEstatus") == ""

    def test_build_soap_envelope(self):
        env = _build_soap_envelope("tok", "<body/>")
        assert "tok" in env
        assert "<body/>" in env
        assert "Envelope" in env

    def test_parse_soap_fault(self):
        xml = (
            f'<s:Envelope xmlns:s="{NS_SOAP}">'
            f'<s:Body><s:Fault><faultstring>oops</faultstring></s:Fault></s:Body>'
            f'</s:Envelope>'
        )
        assert _parse_soap_fault(xml) == "oops"

    def test_parse_soap_fault_no_fault(self):
        xml = f'<s:Envelope xmlns:s="{NS_SOAP}"><s:Body/></s:Envelope>'
        assert _parse_soap_fault(xml) == ""


# ─── Test: Constants ─────────────────────────────────────────────────

class TestConstants:
    def test_all_urls_https(self):
        for url in [SAT_WS_AUTENTICACION_URL, SAT_WS_SOLICITUD_URL,
                     SAT_WS_VERIFICACION_URL, SAT_WS_DESCARGA_URL,
                     SAT_WS_VERIFICADOR_URL, SAT_WS_CANCELACION_URL]:
            assert url.startswith("https://"), f"{url} not HTTPS"

    def test_autenticacion_url(self):
        assert "Autenticacion" in SAT_WS_AUTENTICACION_URL

    def test_verificador_url(self):
        assert "ConsultaCFDI" in SAT_WS_VERIFICADOR_URL

    def test_ns_dm(self):
        assert "DescargaMasivaTerceros" in NS_DM


# ─── Test: _soap_request ────────────────────────────────────────────

class TestSoapRequest:
    @pytest.mark.asyncio
    async def test_successful_request(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<result>ok</result>"

        with patch("src.tools.sat_ws_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await _soap_request("https://test.com", "<env/>", "action")
            assert result == "<result>ok</result>"

    @pytest.mark.asyncio
    async def test_all_retries_fail(self):
        with patch("src.tools.sat_ws_client.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = Exception("connection failed")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            with pytest.raises(SATWSServiceUnavailable, match="3 intentos"):
                await _soap_request("https://test.com", "<env/>", "action", retries=3)


# ─── Test: preparar_cancelacion ──────────────────────────────────────

class TestPrepararCancelacion:
    def test_always_raises(self):
        with pytest.raises(SATWSCancelacionRequiresConfirmation):
            preparar_cancelacion("uuid-123", "MOPR881228EF9")

    def test_motivo_01_requires_sustitucion(self):
        with pytest.raises(ValueError, match="UUID"):
            preparar_cancelacion("uuid", "RFC", motivo="01")

    def test_motivo_02_no_sustitucion(self):
        with pytest.raises(SATWSCancelacionRequiresConfirmation):
            preparar_cancelacion("uuid", "RFC", motivo="02")


# ─── Test: ejecutar_cancelacion ──────────────────────────────────────

class TestEjecutarCancelacion:
    @pytest.mark.asyncio
    async def test_refuses_without_confirmation(self):
        with pytest.raises(SATWSCancelacionRequiresConfirmation):
            await ejecutar_cancelacion(
                "cer", "key", "pwd", "uuid", "rfc",
                confirmacion_usuario=False,
            )

    @pytest.mark.asyncio
    async def test_refuses_default(self):
        with pytest.raises(SATWSCancelacionRequiresConfirmation):
            await ejecutar_cancelacion("c", "k", "p", "u", "r")


# ─── Test: verificar_cfdi ───────────────────────────────────────────

class TestVerificarCFDI:
    @pytest.mark.asyncio
    async def test_vigente(self):
        response_xml = _soap_response(
            '<ConsultaResult>'
            '<CodigoEstatus>S - ...</CodigoEstatus>'
            '<Estado>Vigente</Estado>'
            '<EsCancelable>Cancelable sin aceptación</EsCancelable>'
            '<EstatusCancelacion></EstatusCancelacion>'
            '</ConsultaResult>'
        )
        with patch("src.tools.sat_ws_client._soap_request",
                    new_callable=AsyncMock, return_value=response_xml):
            result = await verificar_cfdi("uuid-1", "EMIT", "RECV", "1000.00")
            assert result.estado == EstadoCFDI.VIGENTE.value
            assert result.uuid == "uuid-1"
            assert result.es_cancelable == "Cancelable sin aceptación"

    @pytest.mark.asyncio
    async def test_cancelado(self):
        response_xml = _soap_response(
            '<ConsultaResult>'
            '<Estado>Cancelado</Estado>'
            '</ConsultaResult>'
        )
        with patch("src.tools.sat_ws_client._soap_request",
                    new_callable=AsyncMock, return_value=response_xml):
            result = await verificar_cfdi("uuid-2", "E", "R", "500")
            assert result.estado == EstadoCFDI.CANCELADO.value

    @pytest.mark.asyncio
    async def test_service_unavailable_returns_no_encontrado(self):
        with patch("src.tools.sat_ws_client._soap_request",
                    new_callable=AsyncMock,
                    side_effect=SATWSServiceUnavailable("SAT down")):
            result = await verificar_cfdi("uuid-3", "E", "R", "0")
            assert result.estado == EstadoCFDI.NO_ENCONTRADO.value
            assert "Error" in result.codigo_estatus


# ─── Test: authenticate ─────────────────────────────────────────────

class TestAuthenticate:
    @pytest.mark.asyncio
    async def test_successful_auth(self, tmp_path):
        # Create test cert/key files
        from tests.test_sat_efirma import _generate_key_pair, _generate_cert, _write_cer, _write_key

        key = _generate_key_pair()
        cert = _generate_cert(key)
        cer_path = tmp_path / "test.cer"
        key_path = tmp_path / "test.key"
        _write_cer(cert, cer_path)
        _write_key(key, key_path, password="pass123")

        response_xml = _soap_response(
            '<AutenticaResponse>'
            '<AutenticaResult>token-from-sat-abc</AutenticaResult>'
            '</AutenticaResponse>'
        )
        with patch("src.tools.sat_ws_client._soap_request",
                    new_callable=AsyncMock, return_value=response_xml):
            token = await authenticate(cer_path, key_path, "pass123")
            assert token.token == "token-from-sat-abc"
            assert token.rfc == "MOPR881228EF9"
            assert token.is_expired() is False

    @pytest.mark.asyncio
    async def test_auth_failure(self, tmp_path):
        from tests.test_sat_efirma import _generate_key_pair, _generate_cert, _write_cer, _write_key

        key = _generate_key_pair()
        cert = _generate_cert(key)
        cer_path = tmp_path / "test.cer"
        key_path = tmp_path / "test.key"
        _write_cer(cert, cer_path)
        _write_key(key, key_path, password="pass")

        with patch("src.tools.sat_ws_client._soap_request",
                    new_callable=AsyncMock,
                    side_effect=SATWSServiceUnavailable("down")):
            with pytest.raises(SATWSAuthError):
                await authenticate(cer_path, key_path, "pass")


# ─── Test: solicitar_descarga ────────────────────────────────────────

class TestSolicitarDescarga:
    @pytest.mark.asyncio
    async def test_aceptada(self):
        token = _make_valid_token()
        response_xml = _soap_response(
            '<SolicitaDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">'
            '<SolicitaDescargaResult IdSolicitud="sol-001" CodEstatus="5000" Mensaje="Solicitud Aceptada"/>'
            '</SolicitaDescargaResponse>'
        )
        with patch("src.tools.sat_ws_client._soap_request",
                    new_callable=AsyncMock, return_value=response_xml):
            sol = await solicitar_descarga(
                token, "MOPR881228EF9", "2026-01-01", "2026-01-31",
            )
            assert sol.id_solicitud == "sol-001"
            assert sol.estado == EstadoSolicitud.ACEPTADA.value

    @pytest.mark.asyncio
    async def test_expired_token_raises(self):
        token = _make_expired_token()
        with pytest.raises(SATWSAuthError, match="expirado"):
            await solicitar_descarga(token, "X", "2026-01-01", "2026-01-31")


# ─── Test: verificar_solicitud ───────────────────────────────────────

class TestVerificarSolicitud:
    @pytest.mark.asyncio
    async def test_terminada(self):
        token = _make_valid_token()
        response_xml = _soap_response(
            '<VerificaSolicitudDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">'
            '<VerificaSolicitudDescargaResult CodEstatus="5000" EstadoSolicitud="3" '
            'NumeroCFDIs="15" Mensaje="ok">'
            '<IdsPaquetes>pkg-001</IdsPaquetes>'
            '<IdsPaquetes>pkg-002</IdsPaquetes>'
            '</VerificaSolicitudDescargaResult>'
            '</VerificaSolicitudDescargaResponse>'
        )
        with patch("src.tools.sat_ws_client._soap_request",
                    new_callable=AsyncMock, return_value=response_xml):
            sol = await verificar_solicitud(token, "sol-001", "MOPR881228EF9")
            assert sol.estado == EstadoSolicitud.TERMINADA.value
            assert sol.numero_cfdis == 15
            assert len(sol.ids_paquetes) == 2

    @pytest.mark.asyncio
    async def test_en_proceso(self):
        token = _make_valid_token()
        response_xml = _soap_response(
            '<VerificaSolicitudDescargaResponse xmlns="x">'
            '<VerificaSolicitudDescargaResult CodEstatus="5000" EstadoSolicitud="2" '
            'NumeroCFDIs="0" Mensaje="En proceso"/>'
            '</VerificaSolicitudDescargaResponse>'
        )
        with patch("src.tools.sat_ws_client._soap_request",
                    new_callable=AsyncMock, return_value=response_xml):
            sol = await verificar_solicitud(token, "sol-002", "X")
            assert sol.estado == EstadoSolicitud.EN_PROCESO.value


# ─── Test: descargar_paquete ─────────────────────────────────────────

class TestDescargarPaquete:
    @pytest.mark.asyncio
    async def test_downloads_and_extracts(self, tmp_path):
        token = _make_valid_token()
        zip_b64 = _make_zip_with_xmls(["factura1.xml", "factura2.xml"])
        response_xml = _soap_response(
            f'<RespuestaDescarga><Paquete>{zip_b64}</Paquete></RespuestaDescarga>'
        )
        with patch("src.tools.sat_ws_client._soap_request",
                    new_callable=AsyncMock, return_value=response_xml):
            paths = await descargar_paquete(
                token, "MOPR881228EF9", "pkg-001",
                download_dir=str(tmp_path),
            )
            assert len(paths) == 2
            assert any("factura1.xml" in p for p in paths)

    @pytest.mark.asyncio
    async def test_no_paquete_raises(self):
        token = _make_valid_token()
        response_xml = _soap_response('<RespuestaDescarga/>')
        with patch("src.tools.sat_ws_client._soap_request",
                    new_callable=AsyncMock, return_value=response_xml):
            with pytest.raises(SATWSDownloadError, match="paquete"):
                await descargar_paquete(token, "X", "pkg-bad")

    @pytest.mark.asyncio
    async def test_expired_token_raises(self):
        token = _make_expired_token()
        with pytest.raises(SATWSAuthError, match="expirado"):
            await descargar_paquete(token, "X", "pkg")


# ─── Test: download_cfdis_with_fallback ──────────────────────────────

class TestFallback:
    @pytest.mark.asyncio
    async def test_no_efirma_skips_soap(self):
        """Without e.firma, goes directly to Playwright."""
        with patch("src.tools.sat_portal_navigator.full_sat_navigation",
                    new_callable=AsyncMock) as mock_nav:
            mock_nav.side_effect = Exception("Playwright not available in test")
            result = await download_cfdis_with_fallback(
                "MOPR881228EF9", "2026-01-01", "2026-01-31",
            )
            assert len(result.errores) > 0

    @pytest.mark.asyncio
    async def test_soap_errors_recorded(self):
        with patch("src.tools.sat_ws_client.descarga_masiva_completa",
                    new_callable=AsyncMock) as mock_dm:
            mock_dm.return_value = DescargaMasivaResult(
                errores=["SOAP timeout"], total_descargados=0,
            )
            with patch("src.tools.sat_portal_navigator.full_sat_navigation",
                        new_callable=AsyncMock) as mock_nav:
                mock_nav.side_effect = Exception("No browser")
                result = await download_cfdis_with_fallback(
                    "X", "2026-01-01", "2026-01-31",
                    cer_path="x.cer", key_path="x.key", password="pwd",
                )
                soap_errors = [e for e in result.errores if "SOAP" in e]
                assert len(soap_errors) >= 1


# ─── Test: Module Exports ───────────────────────────────────────────

class TestModuleExports:
    def test_functions_importable(self):
        from src.tools.sat_ws_client import (
            authenticate, solicitar_descarga, verificar_solicitud,
            descargar_paquete, descarga_masiva_completa,
            verificar_cfdi, preparar_cancelacion, ejecutar_cancelacion,
            download_cfdis_with_fallback,
        )
        assert all(callable(f) for f in [
            authenticate, solicitar_descarga, verificar_solicitud,
            descargar_paquete, descarga_masiva_completa,
            verificar_cfdi, preparar_cancelacion, ejecutar_cancelacion,
            download_cfdis_with_fallback,
        ])

    def test_dataclasses_importable(self):
        from src.tools.sat_ws_client import (
            SATAuthToken, SolicitudDescarga, VerificacionCFDI,
            ResultadoCancelacion, DescargaMasivaResult,
        )
        for cls in [SATAuthToken, SolicitudDescarga, VerificacionCFDI,
                     ResultadoCancelacion, DescargaMasivaResult]:
            assert cls is not None

    def test_enums_importable(self):
        from src.tools.sat_ws_client import (
            EstadoSolicitud, EstadoCFDI, EstadoCancelacion,
        )
        assert len(EstadoSolicitud) == 6
        assert len(EstadoCFDI) == 3
        assert len(EstadoCancelacion) == 5

    def test_exceptions_importable(self):
        from src.tools.sat_ws_client import (
            SATWSAuthError, SATWSSolicitudError, SATWSDownloadError,
            SATWSCancelacionRequiresConfirmation, SATWSServiceUnavailable,
        )
        assert all(issubclass(e, Exception) for e in [
            SATWSAuthError, SATWSSolicitudError, SATWSDownloadError,
            SATWSCancelacionRequiresConfirmation, SATWSServiceUnavailable,
        ])
