"""Tests for SAT Portal Navigator.

Unit tests verify all logic WITHOUT launching a browser or making
network calls. Uses AsyncMock to mock Playwright page objects.

Test categories:
- Dataclass creation, to_dict(), summary()
- Forbidden selector enforcement (_safe_click)
- Authentication detection (mocked page)
- Session alive checks
- CAPTCHA detection
- Pipeline integration (with real CFDI XML)
- Audit logger
- Full orchestration data flow
"""

import json
import pytest
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from src.tools.sat_portal_navigator import (
    # Dataclasses
    SATNavigationStep,
    SATSession,
    CFDIDownloadResult,
    ConstanciaSituacionFiscal,
    BuzonNotificacion,
    BuzonTributarioResult,
    SATPortalResult,
    # Exceptions
    SATReadOnlyViolation,
    SATSessionExpired,
    SATCaptchaDetected,
    # Constants
    FORBIDDEN_SELECTORS,
    SAT_PORTAL_BASE,
    SAT_LOGIN_URL,
    SAT_CFDI_HOME_URL,
    SAT_CFDI_RECIBIDOS_URL,
    SAT_CFDI_EMITIDOS_URL,
    SAT_DESCARGA_MASIVA_URL,
    SAT_CANCELACION_URL,
    SAT_RETENCIONES_BASE,
    SAT_RETENCIONES_URL,
    SAT_MAIN_BASE,
    SAT_CONSTANCIA_INFO_URL,
    SAT_OPINION_CUMPLIMIENTO_URL,
    SAT_BUZON_BASE,
    SAT_BUZON_SERVICIOS_URL,
    SAT_CONSTANCIA_GENERATE_URL,
    SAT_CONSTANCIA_URL,
    SAT_BUZON_URL,
    SAT_BUZON_LOGIN_URL,
    SAT_BUZON_DECLARACIONES_URL,
    # Phase 6.5 — Complete SAT Ecosystem
    SAT_VERIFICADOR_BASE,
    SAT_VERIFICADOR_URL,
    SAT_VERIFICADOR_CCP_URL,
    SAT_VERIFICADOR_SOAP_URL,
    SAT_VERIFICADOR_RETENCIONES_URL,
    SAT_DECLARACION_MENSUAL_612_URL,
    SAT_DECLARACION_MENSUAL_RESICO_URL,
    SAT_DECLARACION_MENSUAL_LEGACY_URL,
    SAT_DECLARACION_ANUAL_URL,
    SAT_LINEA_CAPTURA_URL,
    SAT_MI_PORTAL_BASE,
    SAT_MI_PORTAL_LOGIN_URL,
    SAT_MI_PORTAL_CERTISAT_URL,
    SAT_MI_PORTAL_CERTIFICA_URL,
    SAT_CERTISAT_URL,
    SAT_CONTABILIDAD_ELECTRONICA_URL,
    SAT_CONTABILIDAD_ELECTRONICA_AUTH_URL,
    SAT_DIOT_BASE,
    SAT_DIOT_URL,
    SAT_DIOT_INFO_URL,
    SAT_PAGOS_REFERENCIADOS_URL,
    SAT_VISOR_NOMINA_PATRON_URL,
    SAT_VISOR_NOMINA_TRABAJADOR_URL,
    SAT_ID_URL,
    IMSS_IDSE_URL,
    INFONAVIT_EMPRESARIOS_URL,
    RECIBIDOS_TABLE_COLUMNS,
    SAT_SESSION_TIMEOUT_SEC,
    # Functions
    detect_auth_state,
    detect_captcha,
    _safe_click,
    _check_session_alive,
    _is_forbidden,
    _now_iso,
    _extract_uuid_from_text,
    process_downloaded_cfdis,
)

from src.tools.sat_audit_logger import (
    get_audit_logger,
    log_navigation_step,
    log_session_summary,
    export_audit_trail,
)


# Path to real CFDI XML for pipeline integration tests
REAL_XML = Path(__file__).parent.parent / "data" / "templates" / "MOPR881228EF9FF22.xml"


# ===================================================================
# DATACLASS TESTS
# ===================================================================

class TestSATNavigationStep:
    def test_create(self):
        step = SATNavigationStep(
            timestamp="2026-02-24T10:00:00",
            action="navigate",
            url="https://portalcfdi.facturaelectronica.sat.gob.mx/",
            description="Portal abierto",
        )
        assert step.action == "navigate"
        assert step.success is True
        assert step.error is None

    def test_to_dict(self):
        step = SATNavigationStep(
            timestamp="2026-02-24T10:00:00",
            action="click",
            url="https://example.com",
            description="Test click",
        )
        d = step.to_dict()
        assert isinstance(d, dict)
        assert d["action"] == "click"
        assert d["success"] is True

    def test_error_step(self):
        step = SATNavigationStep(
            timestamp="2026-02-24T10:00:00",
            action="BLOCKED",
            url="https://example.com",
            description="Blocked action",
            success=False,
            error="Read-only violation",
        )
        assert step.success is False
        assert "violation" in step.error


class TestSATSession:
    def test_create(self):
        s = SATSession(rfc="MOPR881228EF9", session_type="CIEC")
        assert s.rfc == "MOPR881228EF9"
        assert s.authenticated is False
        assert len(s.navigation_log) == 0

    def test_authenticated(self):
        s = SATSession(
            rfc="MOPR881228EF9",
            session_type="FIEL",
            authenticated=True,
            authenticated_at="2026-02-24T10:00:00",
        )
        assert s.authenticated is True
        assert s.session_type == "FIEL"

    def test_to_dict(self):
        s = SATSession(rfc="TEST123", session_type="CIEC", authenticated=True)
        d = s.to_dict()
        assert isinstance(d, dict)
        assert d["rfc"] == "TEST123"
        assert d["authenticated"] is True

    def test_summary_authenticated(self):
        s = SATSession(rfc="MOPR881228EF9", session_type="CIEC", authenticated=True)
        summary = s.summary()
        assert "MOPR881228EF9" in summary
        assert "Autenticado" in summary

    def test_summary_not_authenticated(self):
        s = SATSession(rfc="MOPR881228EF9", session_type="CIEC", authenticated=False)
        summary = s.summary()
        assert "No autenticado" in summary

    def test_add_step(self):
        s = SATSession(rfc="TEST", session_type="CIEC")
        step = SATNavigationStep(
            timestamp="2026-02-24T10:00:00",
            action="navigate",
            url="https://example.com",
            description="Test",
        )
        s.add_step(step)
        assert len(s.navigation_log) == 1
        assert s.last_activity == "2026-02-24T10:00:00"

    def test_summary_shows_step_count(self):
        s = SATSession(rfc="TEST", session_type="CIEC")
        for i in range(5):
            step = SATNavigationStep(
                timestamp=f"2026-02-24T10:0{i}:00",
                action="navigate",
                url="https://example.com",
                description=f"Step {i}",
            )
            s.add_step(step)
        assert "5 pasos" in s.summary()


class TestCFDIDownloadResult:
    def test_create(self):
        r = CFDIDownloadResult(
            tipo="recibidos",
            fecha_inicio="2026-01-01",
            fecha_fin="2026-01-31",
        )
        assert r.total_descargados == 0
        assert r.total_encontrados == 0
        assert r.tipo == "recibidos"
        assert len(r.archivos_xml) == 0

    def test_summary_recibidos(self):
        r = CFDIDownloadResult(
            tipo="recibidos",
            fecha_inicio="2026-01-01",
            fecha_fin="2026-01-31",
            total_encontrados=10,
            total_descargados=8,
        )
        s = r.summary()
        assert "Recibidos" in s
        assert "8/10" in s
        assert "2026-01-01" in s

    def test_summary_emitidos(self):
        r = CFDIDownloadResult(
            tipo="emitidos",
            fecha_inicio="2026-01-01",
            fecha_fin="2026-01-31",
            total_encontrados=5,
            total_descargados=5,
        )
        assert "Emitidos" in r.summary()

    def test_to_dict(self):
        r = CFDIDownloadResult(
            tipo="recibidos",
            fecha_inicio="2026-01-01",
            fecha_fin="2026-01-31",
        )
        d = r.to_dict()
        assert d["tipo"] == "recibidos"
        assert isinstance(d["archivos_xml"], list)

    def test_with_files_and_errors(self):
        r = CFDIDownloadResult(
            tipo="recibidos",
            fecha_inicio="2026-01-01",
            fecha_fin="2026-01-31",
            total_encontrados=3,
            total_descargados=2,
            archivos_xml=["/path/to/1.xml", "/path/to/2.xml"],
            errores=["Failed to download 3rd"],
        )
        assert len(r.archivos_xml) == 2
        assert len(r.errores) == 1


class TestConstanciaSituacionFiscal:
    def test_create(self):
        c = ConstanciaSituacionFiscal(
            rfc="MOPR881228EF9",
            nombre="RICARDO MONCADA PALAFOX",
            regimen_fiscal="612",
            regimen_desc="Personas Físicas con Actividades Empresariales y Profesionales",
            codigo_postal="37297",
            estatus_padron="Activo",
        )
        assert c.rfc == "MOPR881228EF9"
        assert c.estatus_padron == "Activo"

    def test_summary(self):
        c = ConstanciaSituacionFiscal(
            rfc="MOPR881228EF9",
            nombre="RICARDO MONCADA PALAFOX",
            regimen_fiscal="612",
            regimen_desc="Actividades Empresariales",
            codigo_postal="37297",
            estatus_padron="Activo",
        )
        s = c.summary()
        assert "RICARDO MONCADA" in s
        assert "Activo" in s
        assert "MOPR881228EF9" in s

    def test_to_dict(self):
        c = ConstanciaSituacionFiscal(
            rfc="TEST",
            nombre="Test",
            regimen_fiscal="625",
            regimen_desc="RESICO",
            codigo_postal="01000",
            estatus_padron="Activo",
        )
        d = c.to_dict()
        assert d["regimen_fiscal"] == "625"

    def test_with_obligaciones(self):
        c = ConstanciaSituacionFiscal(
            rfc="TEST",
            nombre="Test",
            regimen_fiscal="612",
            regimen_desc="Empresarial",
            codigo_postal="01000",
            estatus_padron="Activo",
            obligaciones=["ISR", "IVA"],
        )
        assert len(c.obligaciones) == 2


class TestBuzonNotificacion:
    def test_create(self):
        n = BuzonNotificacion(
            tipo="Requerimiento",
            fecha="2026-02-20",
            asunto="Pago pendiente ISR",
        )
        assert n.leida is False
        assert n.tipo == "Requerimiento"

    def test_to_dict(self):
        n = BuzonNotificacion(
            tipo="Notificación",
            fecha="2026-02-20",
            asunto="Test",
            leida=True,
        )
        d = n.to_dict()
        assert d["leida"] is True


class TestBuzonTributarioResult:
    def test_create_empty(self):
        b = BuzonTributarioResult()
        assert b.total_notificaciones == 0
        assert b.no_leidas == 0

    def test_summary(self):
        b = BuzonTributarioResult(
            total_notificaciones=5,
            no_leidas=2,
        )
        s = b.summary()
        assert "5 notificaciones" in s
        assert "2 sin leer" in s

    def test_to_dict(self):
        b = BuzonTributarioResult(total_notificaciones=3, no_leidas=1)
        d = b.to_dict()
        assert d["no_leidas"] == 1


class TestSATPortalResult:
    def test_minimal_result(self):
        result = SATPortalResult(
            session=SATSession(rfc="TEST", session_type="CIEC"),
        )
        assert result.cfdis_recibidos is None
        assert result.constancia is None

    def test_complete_result(self):
        result = SATPortalResult(
            session=SATSession(
                rfc="MOPR881228EF9",
                session_type="FIEL",
                authenticated=True,
            ),
            cfdis_recibidos=CFDIDownloadResult(
                tipo="recibidos",
                fecha_inicio="2026-01-01",
                fecha_fin="2026-01-31",
                total_encontrados=10,
                total_descargados=8,
            ),
            cfdis_emitidos=CFDIDownloadResult(
                tipo="emitidos",
                fecha_inicio="2026-01-01",
                fecha_fin="2026-01-31",
                total_encontrados=5,
                total_descargados=5,
            ),
            constancia=ConstanciaSituacionFiscal(
                rfc="MOPR881228EF9",
                nombre="RICARDO MONCADA",
                regimen_fiscal="612",
                regimen_desc="Empresarial",
                codigo_postal="37297",
                estatus_padron="Activo",
            ),
            buzon=BuzonTributarioResult(
                total_notificaciones=3,
                no_leidas=1,
            ),
        )
        s = result.summary()
        assert "MOPR881228EF9" in s
        assert "Recibidos" in s
        assert "Emitidos" in s
        assert "Constancia" in s
        assert "Buzón" in s

    def test_to_dict(self):
        result = SATPortalResult(
            session=SATSession(rfc="TEST", session_type="CIEC"),
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["session"]["rfc"] == "TEST"

    def test_summary_partial_result(self):
        """Summary works with only some sections populated."""
        result = SATPortalResult(
            session=SATSession(rfc="TEST", session_type="CIEC", authenticated=True),
            cfdis_recibidos=CFDIDownloadResult(
                tipo="recibidos",
                fecha_inicio="2026-01-01",
                fecha_fin="2026-01-31",
            ),
        )
        s = result.summary()
        assert "TEST" in s
        assert "Recibidos" in s
        assert "Constancia" not in s


# ===================================================================
# EXCEPTION TESTS
# ===================================================================

class TestExceptions:
    def test_read_only_violation(self):
        err = SATReadOnlyViolation("Cannot cancel CFDI")
        assert "cancel" in str(err).lower()

    def test_session_expired(self):
        err = SATSessionExpired("Session timed out after 300s")
        assert "300" in str(err)

    def test_captcha_detected(self):
        err = SATCaptchaDetected("CAPTCHA on login page")
        assert "CAPTCHA" in str(err)

    def test_exceptions_are_catchable(self):
        """All custom exceptions can be caught by base Exception."""
        for exc_class in [SATReadOnlyViolation, SATSessionExpired, SATCaptchaDetected]:
            with pytest.raises(Exception):
                raise exc_class("test")


# ===================================================================
# CONSTANTS TESTS
# ===================================================================

class TestConstants:
    def test_portal_base_url(self):
        assert "portalcfdi.facturaelectronica.sat.gob.mx" in SAT_PORTAL_BASE

    def test_login_url(self):
        assert SAT_PORTAL_BASE in SAT_LOGIN_URL

    def test_cfdi_home_url(self):
        assert "Consulta.aspx" in SAT_CFDI_HOME_URL

    def test_recibidos_url(self):
        assert "ConsultaReceptor.aspx" in SAT_CFDI_RECIBIDOS_URL

    def test_emitidos_url(self):
        assert "ConsultaEmisor.aspx" in SAT_CFDI_EMITIDOS_URL

    def test_descarga_masiva_url(self):
        assert "ConsultaDescargaMasiva.aspx" in SAT_DESCARGA_MASIVA_URL

    def test_cancelacion_url(self):
        assert "ConsultaCancelacion.aspx" in SAT_CANCELACION_URL

    def test_retenciones_base(self):
        assert "clouda.sat.gob.mx" in SAT_RETENCIONES_BASE

    def test_retenciones_url(self):
        assert SAT_RETENCIONES_BASE in SAT_RETENCIONES_URL
        assert "oculta=1" in SAT_RETENCIONES_URL

    def test_main_base(self):
        assert SAT_MAIN_BASE == "https://sat.gob.mx"

    def test_constancia_info_url(self):
        assert "constancia-de-situacion-fiscal" in SAT_CONSTANCIA_INFO_URL
        assert SAT_MAIN_BASE in SAT_CONSTANCIA_INFO_URL

    def test_opinion_cumplimiento_url(self):
        assert "mas-tramites" in SAT_OPINION_CUMPLIMIENTO_URL

    def test_buzon_base(self):
        assert "wwwmat.sat.gob.mx" in SAT_BUZON_BASE

    def test_buzon_servicios_url(self):
        assert "00834" in SAT_BUZON_SERVICIOS_URL
        assert SAT_BUZON_BASE in SAT_BUZON_SERVICIOS_URL

    def test_constancia_generate_url(self):
        assert "43824" in SAT_CONSTANCIA_GENERATE_URL
        assert SAT_BUZON_BASE in SAT_CONSTANCIA_GENERATE_URL

    def test_buzon_login_url(self):
        assert "iniciar-sesion" in SAT_BUZON_LOGIN_URL
        assert SAT_BUZON_BASE in SAT_BUZON_LOGIN_URL

    def test_buzon_declaraciones_url(self):
        assert "declaraciones" in SAT_BUZON_DECLARACIONES_URL

    def test_legacy_aliases(self):
        """Legacy URL aliases should point to the new constants."""
        assert SAT_CONSTANCIA_URL == SAT_CONSTANCIA_INFO_URL
        assert SAT_BUZON_URL == SAT_BUZON_SERVICIOS_URL

    def test_session_timeout(self):
        assert SAT_SESSION_TIMEOUT_SEC == 300

    def test_forbidden_selectors_not_empty(self):
        assert len(FORBIDDEN_SELECTORS) > 0

    def test_forbidden_includes_cancel(self):
        combined = " ".join(FORBIDDEN_SELECTORS).lower()
        assert "cancelar" in combined

    def test_forbidden_includes_modify(self):
        combined = " ".join(FORBIDDEN_SELECTORS).lower()
        assert "modificar" in combined

    def test_forbidden_includes_delete(self):
        combined = " ".join(FORBIDDEN_SELECTORS).lower()
        assert "eliminar" in combined

    def test_forbidden_includes_submit(self):
        combined = " ".join(FORBIDDEN_SELECTORS).lower()
        assert "enviar" in combined

    def test_forbidden_includes_generate(self):
        combined = " ".join(FORBIDDEN_SELECTORS).lower()
        assert "generar" in combined


class TestSATEcosystemURLs:
    """Tests for Phase 6.5 — Complete SAT Ecosystem URLs."""

    # Verificador CFDI (público)
    def test_verificador_base(self):
        assert "verificacfdi.facturaelectronica.sat.gob.mx" in SAT_VERIFICADOR_BASE

    def test_verificador_url(self):
        assert "default.aspx" in SAT_VERIFICADOR_URL
        assert SAT_VERIFICADOR_BASE in SAT_VERIFICADOR_URL

    def test_verificador_ccp(self):
        assert "verificaccp" in SAT_VERIFICADOR_CCP_URL

    def test_verificador_soap(self):
        assert "ConsultaCFDIService.svc" in SAT_VERIFICADOR_SOAP_URL
        assert "consultaqr" in SAT_VERIFICADOR_SOAP_URL

    def test_verificador_retenciones(self):
        assert "prodretencionverificacion" in SAT_VERIFICADOR_RETENCIONES_URL

    # DeclaraSAT
    def test_declaracion_mensual_612(self):
        assert "33006" in SAT_DECLARACION_MENSUAL_612_URL
        assert "actividades-empresariales" in SAT_DECLARACION_MENSUAL_612_URL
        assert SAT_BUZON_BASE in SAT_DECLARACION_MENSUAL_612_URL

    def test_declaracion_mensual_resico(self):
        assert "53359" in SAT_DECLARACION_MENSUAL_RESICO_URL
        assert SAT_BUZON_BASE in SAT_DECLARACION_MENSUAL_RESICO_URL

    def test_declaracion_mensual_legacy(self):
        assert "26984" in SAT_DECLARACION_MENSUAL_LEGACY_URL

    def test_declaracion_anual(self):
        assert "DeclaracionAnual" in SAT_DECLARACION_ANUAL_URL
        assert SAT_BUZON_BASE in SAT_DECLARACION_ANUAL_URL

    def test_linea_captura(self):
        assert "98410" in SAT_LINEA_CAPTURA_URL
        assert "linea-de-captura" in SAT_LINEA_CAPTURA_URL

    # Mi Portal SAT
    def test_mi_portal_base(self):
        assert "portalsat.plataforma.sat.gob.mx" in SAT_MI_PORTAL_BASE

    def test_mi_portal_login(self):
        assert "AuthLogin" in SAT_MI_PORTAL_LOGIN_URL
        assert SAT_MI_PORTAL_BASE in SAT_MI_PORTAL_LOGIN_URL

    def test_mi_portal_certisat(self):
        assert "certisat" in SAT_MI_PORTAL_CERTISAT_URL
        assert SAT_MI_PORTAL_BASE in SAT_MI_PORTAL_CERTISAT_URL

    def test_mi_portal_certifica(self):
        assert "certifica" in SAT_MI_PORTAL_CERTIFICA_URL

    # CertiSAT Web
    def test_certisat_url(self):
        assert "aplicacionesc.mat.sat.gob.mx" in SAT_CERTISAT_URL
        assert "certisat" in SAT_CERTISAT_URL

    # Contabilidad Electrónica
    def test_contabilidad_electronica_url(self):
        assert "42150" in SAT_CONTABILIDAD_ELECTRONICA_URL
        assert "contabilidad-electronica" in SAT_CONTABILIDAD_ELECTRONICA_URL

    def test_contabilidad_electronica_auth_url(self):
        assert "42150" in SAT_CONTABILIDAD_ELECTRONICA_AUTH_URL
        assert SAT_BUZON_BASE in SAT_CONTABILIDAD_ELECTRONICA_AUTH_URL

    # DIOT
    def test_diot_base(self):
        assert "pstcdi.clouda.sat.gob.mx" in SAT_DIOT_BASE

    def test_diot_url(self):
        assert SAT_DIOT_URL == SAT_DIOT_BASE

    def test_diot_info_url(self):
        assert "74295" in SAT_DIOT_INFO_URL
        assert "diot" in SAT_DIOT_INFO_URL.lower()

    # Pagos Referenciados
    def test_pagos_referenciados(self):
        assert "20425" in SAT_PAGOS_REFERENCIADOS_URL
        assert SAT_MAIN_BASE in SAT_PAGOS_REFERENCIADOS_URL

    # Visor de Nómina
    def test_visor_nomina_patron(self):
        assert "90887" in SAT_VISOR_NOMINA_PATRON_URL
        assert "patron" in SAT_VISOR_NOMINA_PATRON_URL

    def test_visor_nomina_trabajador(self):
        assert "97720" in SAT_VISOR_NOMINA_TRABAJADOR_URL
        assert "trabajador" in SAT_VISOR_NOMINA_TRABAJADOR_URL

    # SAT ID
    def test_sat_id_url(self):
        assert "satid.sat.gob.mx" in SAT_ID_URL

    # Portales gobierno relacionados
    def test_imss_idse_url(self):
        assert "idse.imss.gob.mx" in IMSS_IDSE_URL

    def test_infonavit_url(self):
        assert "empresarios.infonavit.org.mx" in INFONAVIT_EMPRESARIOS_URL

    # Consistency checks
    def test_all_declarasat_urls_use_buzon_base(self):
        """All DeclaraSAT URLs should use wwwmat.sat.gob.mx."""
        for url in [SAT_DECLARACION_MENSUAL_612_URL,
                     SAT_DECLARACION_MENSUAL_RESICO_URL,
                     SAT_DECLARACION_MENSUAL_LEGACY_URL,
                     SAT_DECLARACION_ANUAL_URL,
                     SAT_LINEA_CAPTURA_URL]:
            assert SAT_BUZON_BASE in url, f"URL {url} should use {SAT_BUZON_BASE}"

    def test_all_urls_are_https(self):
        """All URLs should use HTTPS."""
        all_urls = [
            SAT_VERIFICADOR_URL, SAT_VERIFICADOR_CCP_URL, SAT_VERIFICADOR_SOAP_URL,
            SAT_VERIFICADOR_RETENCIONES_URL,
            SAT_DECLARACION_MENSUAL_612_URL, SAT_DECLARACION_MENSUAL_RESICO_URL,
            SAT_DECLARACION_ANUAL_URL, SAT_LINEA_CAPTURA_URL,
            SAT_MI_PORTAL_LOGIN_URL, SAT_CERTISAT_URL,
            SAT_CONTABILIDAD_ELECTRONICA_URL, SAT_DIOT_URL,
            SAT_PAGOS_REFERENCIADOS_URL,
            SAT_VISOR_NOMINA_PATRON_URL, SAT_VISOR_NOMINA_TRABAJADOR_URL,
            SAT_ID_URL, IMSS_IDSE_URL, INFONAVIT_EMPRESARIOS_URL,
        ]
        for url in all_urls:
            assert url.startswith("https://"), f"URL {url} must be HTTPS"

    def test_ecosystem_total_url_count(self):
        """Verify we have a substantial number of SAT URLs mapped."""
        from src.tools import sat_portal_navigator as nav
        url_attrs = [attr for attr in dir(nav) if attr.startswith("SAT_") and attr.endswith("_URL")]
        assert len(url_attrs) >= 25, f"Expected 25+ URL constants, found {len(url_attrs)}"


class TestRecibidosTableColumns:
    def test_column_count(self):
        assert len(RECIBIDOS_TABLE_COLUMNS) == 18

    def test_first_column_is_checkbox(self):
        assert RECIBIDOS_TABLE_COLUMNS[0] == "checkbox"

    def test_uuid_column_exists(self):
        assert "folio_fiscal" in RECIBIDOS_TABLE_COLUMNS

    def test_key_columns_present(self):
        assert "rfc_emisor" in RECIBIDOS_TABLE_COLUMNS
        assert "nombre_emisor" in RECIBIDOS_TABLE_COLUMNS
        assert "total" in RECIBIDOS_TABLE_COLUMNS
        assert "fecha_emision" in RECIBIDOS_TABLE_COLUMNS
        assert "estado_comprobante" in RECIBIDOS_TABLE_COLUMNS

    def test_cancellation_columns_present(self):
        assert "estatus_cancelacion" in RECIBIDOS_TABLE_COLUMNS
        assert "fecha_cancelacion" in RECIBIDOS_TABLE_COLUMNS

    def test_acciones_column(self):
        assert RECIBIDOS_TABLE_COLUMNS[1] == "acciones"


# ===================================================================
# HELPER FUNCTION TESTS
# ===================================================================

class TestHelpers:
    def test_now_iso_format(self):
        ts = _now_iso()
        # Should be parseable as ISO format
        dt = datetime.fromisoformat(ts)
        assert dt.year >= 2026

    def test_is_forbidden_cancel(self):
        assert _is_forbidden("input[value*='Cancelar']") is True

    def test_is_forbidden_modificar(self):
        assert _is_forbidden("a[href*='Modificar']") is True

    def test_is_forbidden_eliminar(self):
        assert _is_forbidden("input[value*='Eliminar']") is True

    def test_is_forbidden_generar(self):
        assert _is_forbidden("a[href*='Generar']") is True

    def test_not_forbidden_buscar(self):
        assert _is_forbidden("button:has-text('Buscar')") is False

    def test_not_forbidden_download(self):
        assert _is_forbidden("a[title='XML']") is False

    def test_not_forbidden_consulta(self):
        assert _is_forbidden("a[href='ConsultaReceptor.aspx']") is False

    def test_extract_uuid(self):
        text = "Folio: C0172468-3CC7-4CA7-A5CD-C7A0E2CEA35D | Total: $150,000"
        uuid = _extract_uuid_from_text(text)
        assert uuid == "C0172468-3CC7-4CA7-A5CD-C7A0E2CEA35D"

    def test_extract_uuid_lowercase(self):
        text = "uuid: a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        uuid = _extract_uuid_from_text(text)
        assert uuid == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_extract_uuid_none(self):
        assert _extract_uuid_from_text("No UUID here") is None

    def test_extract_uuid_empty(self):
        assert _extract_uuid_from_text("") is None


# ===================================================================
# SAFE CLICK TESTS (mocked Playwright)
# ===================================================================

class TestSafeClick:
    @pytest.mark.asyncio
    async def test_allowed_click(self):
        """Clicking a safe selector should work."""
        page = AsyncMock()
        session = SATSession(rfc="TEST", session_type="CIEC")

        await _safe_click(page, "button:has-text('Buscar')", session, "Search")
        page.click.assert_called_once()
        assert len(session.navigation_log) == 1
        assert session.navigation_log[0].action == "click"

    @pytest.mark.asyncio
    async def test_blocked_cancelar(self):
        """Clicking Cancelar should raise SATReadOnlyViolation."""
        page = AsyncMock()
        session = SATSession(rfc="TEST", session_type="CIEC")

        with pytest.raises(SATReadOnlyViolation):
            await _safe_click(page, "input[value*='Cancelar']", session)

        # Should log the blocked action
        assert len(session.navigation_log) == 1
        assert session.navigation_log[0].action == "BLOCKED"
        assert session.navigation_log[0].success is False

    @pytest.mark.asyncio
    async def test_blocked_modificar(self):
        page = AsyncMock()
        session = SATSession(rfc="TEST", session_type="CIEC")

        with pytest.raises(SATReadOnlyViolation):
            await _safe_click(page, "a[href*='Modificar']", session)

    @pytest.mark.asyncio
    async def test_blocked_eliminar(self):
        page = AsyncMock()
        session = SATSession(rfc="TEST", session_type="CIEC")

        with pytest.raises(SATReadOnlyViolation):
            await _safe_click(page, "input[value*='Eliminar']", session)

    @pytest.mark.asyncio
    async def test_blocked_generar(self):
        page = AsyncMock()
        session = SATSession(rfc="TEST", session_type="CIEC")

        with pytest.raises(SATReadOnlyViolation):
            await _safe_click(page, "a[href*='Generar']", session)

    @pytest.mark.asyncio
    async def test_allowed_xml_download(self):
        """XML download links should be allowed."""
        page = AsyncMock()
        session = SATSession(rfc="TEST", session_type="CIEC")

        await _safe_click(page, "a[title='Descargar XML']", session)
        page.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_logs_description(self):
        page = AsyncMock()
        session = SATSession(rfc="TEST", session_type="CIEC")

        await _safe_click(page, "button#search", session, "Buscar facturas")
        assert session.navigation_log[0].description == "Buscar facturas"


# ===================================================================
# AUTH DETECTION TESTS (mocked Playwright)
# ===================================================================

class TestDetectAuthState:
    @pytest.mark.asyncio
    async def test_login_page_not_authenticated(self):
        page = AsyncMock()
        page.url = "https://portalcfdi.facturaelectronica.sat.gob.mx/Login.aspx"
        page.query_selector.return_value = None

        is_auth, rfc = await detect_auth_state(page)
        assert is_auth is False
        assert rfc == ""

    @pytest.mark.asyncio
    async def test_authenticated_with_rfc_and_logout(self):
        """Authenticated when RFC visible + logout present."""
        page = AsyncMock()
        page.url = "https://portalcfdi.facturaelectronica.sat.gob.mx/ConsultaReceptor.aspx"

        # Mock query_selector to return elements for RFC, logout, and menu
        rfc_el = AsyncMock()
        rfc_el.inner_text = AsyncMock(return_value="MOPR881228EF9")
        logout_el = AsyncMock()
        menu_el = AsyncMock()

        # query_selector is called 3 times with different selectors
        page.query_selector.side_effect = [rfc_el, logout_el, menu_el]

        is_auth, rfc = await detect_auth_state(page)
        assert is_auth is True

    @pytest.mark.asyncio
    async def test_not_authenticated_no_elements(self):
        """Not authenticated when no elements found."""
        page = AsyncMock()
        page.url = "https://portalcfdi.facturaelectronica.sat.gob.mx/SomeOtherPage.aspx"
        page.query_selector.return_value = None

        is_auth, rfc = await detect_auth_state(page)
        assert is_auth is False

    @pytest.mark.asyncio
    async def test_login_in_url_means_not_auth(self):
        page = AsyncMock()
        page.url = "https://portalcfdi.facturaelectronica.sat.gob.mx/nidp/idff/sso/login"
        page.query_selector.return_value = None

        is_auth, _ = await detect_auth_state(page)
        assert is_auth is False


class TestDetectCaptcha:
    @pytest.mark.asyncio
    async def test_no_captcha(self):
        page = AsyncMock()
        page.query_selector.return_value = None

        result = await detect_captcha(page)
        assert result is False

    @pytest.mark.asyncio
    async def test_captcha_img_detected(self):
        page = AsyncMock()
        # First selector matches (captcha image)
        page.query_selector.side_effect = [AsyncMock()]

        result = await detect_captcha(page)
        assert result is True

    @pytest.mark.asyncio
    async def test_recaptcha_iframe_detected(self):
        page = AsyncMock()
        # Return None for all except recaptcha iframe
        side_effects = [None] * 4 + [AsyncMock()] + [None] * 2
        page.query_selector.side_effect = side_effects

        result = await detect_captcha(page)
        assert result is True


# ===================================================================
# SESSION ALIVE TESTS
# ===================================================================

class TestCheckSessionAlive:
    @pytest.mark.asyncio
    async def test_expired_by_time(self):
        page = AsyncMock()
        page.url = "https://portalcfdi.facturaelectronica.sat.gob.mx/Consulta.aspx"
        old_time = (datetime.now() - timedelta(seconds=400)).isoformat()
        session = SATSession(
            rfc="TEST",
            session_type="CIEC",
            last_activity=old_time,
        )

        result = await _check_session_alive(page, session)
        assert result is False

    @pytest.mark.asyncio
    async def test_expired_by_redirect_to_login(self):
        page = AsyncMock()
        page.url = "https://portalcfdi.facturaelectronica.sat.gob.mx/Login.aspx"
        session = SATSession(rfc="TEST", session_type="CIEC")

        result = await _check_session_alive(page, session)
        assert result is False

    @pytest.mark.asyncio
    async def test_alive_recent_activity(self):
        page = AsyncMock()
        page.url = "https://portalcfdi.facturaelectronica.sat.gob.mx/ConsultaReceptor.aspx"
        recent_time = datetime.now().isoformat()
        session = SATSession(
            rfc="TEST",
            session_type="CIEC",
            last_activity=recent_time,
        )

        # Mock auth detection as True
        rfc_el = AsyncMock()
        rfc_el.inner_text = AsyncMock(return_value="TEST1234567")
        logout_el = AsyncMock()
        menu_el = AsyncMock()
        page.query_selector.side_effect = [rfc_el, logout_el, menu_el]

        result = await _check_session_alive(page, session)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_last_activity_checks_page(self):
        """When no last_activity, falls through to page check."""
        page = AsyncMock()
        page.url = "https://portalcfdi.facturaelectronica.sat.gob.mx/Login.aspx"
        session = SATSession(rfc="TEST", session_type="CIEC")

        result = await _check_session_alive(page, session)
        assert result is False


# ===================================================================
# PIPELINE INTEGRATION TESTS
# ===================================================================

class TestProcessDownloadedCFDIs:
    @pytest.mark.asyncio
    async def test_process_real_xml(self):
        """Test pipeline with the real CFDI XML file."""
        if not REAL_XML.exists():
            pytest.skip("Real CFDI XML not available")

        download_result = CFDIDownloadResult(
            tipo="recibidos",
            fecha_inicio="2022-01-01",
            fecha_fin="2022-01-31",
            total_encontrados=1,
            total_descargados=1,
            archivos_xml=[str(REAL_XML)],
        )

        results = await process_downloaded_cfdis(
            download_result,
            doctor_rfc="IIC200908QY6",  # Doctor is receptor
        )

        assert len(results) == 1
        cfdi, clasificacion = results[0]
        assert cfdi.emisor_rfc == "MOPR881228EF9"
        assert cfdi.total == 150000.0
        assert clasificacion.deducibilidad is not None

    @pytest.mark.asyncio
    async def test_process_missing_xml_continues(self):
        """Pipeline should skip bad files and continue."""
        download_result = CFDIDownloadResult(
            tipo="recibidos",
            fecha_inicio="2026-01-01",
            fecha_fin="2026-01-31",
            total_encontrados=1,
            total_descargados=1,
            archivos_xml=["/nonexistent/file.xml"],
        )

        results = await process_downloaded_cfdis(
            download_result,
            doctor_rfc="TEST",
        )

        assert len(results) == 0
        assert len(download_result.errores) == 1

    @pytest.mark.asyncio
    async def test_process_mixed_good_and_bad(self):
        """Pipeline processes valid files and logs errors for bad ones."""
        if not REAL_XML.exists():
            pytest.skip("Real CFDI XML not available")

        download_result = CFDIDownloadResult(
            tipo="recibidos",
            fecha_inicio="2022-01-01",
            fecha_fin="2022-12-31",
            total_encontrados=3,
            total_descargados=3,
            archivos_xml=[
                str(REAL_XML),
                "/bad/path.xml",
                str(REAL_XML),
            ],
        )

        results = await process_downloaded_cfdis(
            download_result,
            doctor_rfc="IIC200908QY6",
        )

        assert len(results) == 2     # Two valid
        assert len(download_result.errores) == 1  # One error

    @pytest.mark.asyncio
    async def test_process_empty_list(self):
        download_result = CFDIDownloadResult(
            tipo="recibidos",
            fecha_inicio="2026-01-01",
            fecha_fin="2026-01-31",
        )

        results = await process_downloaded_cfdis(
            download_result,
            doctor_rfc="TEST",
        )

        assert len(results) == 0
        assert len(download_result.errores) == 0


# ===================================================================
# AUDIT LOGGER TESTS
# ===================================================================

class TestAuditLogger:
    def test_get_audit_logger(self, tmp_path):
        logger = get_audit_logger(
            rfc="TEST",
            session_id="TEST_session_001",
            audit_dir=str(tmp_path),
        )
        assert logger is not None
        assert logger.name == "sat_audit_TEST_session_001"

    def test_log_navigation_step(self, tmp_path):
        logger = get_audit_logger(
            rfc="TEST",
            session_id="log_test_001",
            audit_dir=str(tmp_path),
        )
        step = SATNavigationStep(
            timestamp="2026-02-24T10:00:00",
            action="navigate",
            url="https://example.com",
            description="Test step",
        )
        log_navigation_step(logger, step)

        # Verify log file was written
        log_file = tmp_path / "log_test_001.jsonl"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        data = json.loads(content.strip())
        assert data["event"] == "navigation_step"
        assert data["step"]["action"] == "navigate"

    def test_log_session_summary(self, tmp_path):
        logger = get_audit_logger(
            rfc="TEST",
            session_id="summary_test_001",
            audit_dir=str(tmp_path),
        )
        result = SATPortalResult(
            session=SATSession(rfc="TEST", session_type="CIEC", authenticated=True),
        )
        log_session_summary(logger, result)

        log_file = tmp_path / "summary_test_001.jsonl"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        data = json.loads(content.strip())
        assert data["event"] == "session_summary"

    def test_export_audit_trail(self, tmp_path):
        session = SATSession(rfc="TEST", session_type="CIEC")
        step = SATNavigationStep(
            timestamp="2026-02-24T10:00:00",
            action="navigate",
            url="https://example.com",
            description="Test",
        )
        session.add_step(step)

        export_path = export_audit_trail(session, audit_dir=str(tmp_path))

        assert Path(export_path).exists()
        with open(export_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["rfc"] == "TEST"
        assert data["total_steps"] == 1
        assert len(data["steps"]) == 1

    def test_export_empty_session(self, tmp_path):
        session = SATSession(rfc="EMPTY", session_type="CIEC")
        export_path = export_audit_trail(session, audit_dir=str(tmp_path))

        with open(export_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_steps"] == 0
        assert data["steps"] == []

    def test_logger_no_duplicate_handlers(self, tmp_path):
        """Getting the same logger twice should not add duplicate handlers."""
        logger1 = get_audit_logger(
            rfc="TEST",
            session_id="dup_test",
            audit_dir=str(tmp_path),
        )
        logger2 = get_audit_logger(
            rfc="TEST",
            session_id="dup_test",
            audit_dir=str(tmp_path),
        )
        assert len(logger2.handlers) == 1
