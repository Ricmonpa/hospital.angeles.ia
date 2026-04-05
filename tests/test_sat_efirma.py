"""Tests for OpenDoc e.firma Certificate Handler.

Validates:
- Certificate loading (.cer DER/PEM)
- Private key loading (.key PKCS#8 DER)
- Certificate pair validation
- SAT auth token generation (WS-Security XML)
- SOAP body signing (RSA-SHA256)
- RFC extraction from certificate subject
- Certificate metadata (validity, fingerprint, serial)
- WhatsApp summary formatting
- Error handling (wrong password, expired cert, mismatched pair)

All tests use in-memory generated certificates — no real SAT credentials.
"""

import base64
import hashlib
import datetime
import os
import pytest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID

from src.tools.sat_efirma import (
    EstadoCertificado,
    TipoCertificado,
    CertificadoInfo,
    EFirmaPasswordError,
    EFirmaCertificateError,
    EFirmaExpiredError,
    EFirmaSigningError,
    EFirmaKeyMismatchError,
    load_certificate,
    load_private_key,
    validate_certificate_pair,
    generate_sat_auth_token,
    sign_soap_body,
    _wipe_key,
    _extract_cert_info,
    _extract_rfc,
    NS_SOAP,
    NS_WSU,
    NS_WSSE,
    NS_DSIG,
)


# ─── Test Helpers ────────────────────────────────────────────────────

def _generate_key_pair():
    """Generate an RSA key pair for testing."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )


def _generate_cert(
    private_key,
    rfc="MOPR881228EF9",
    cn="MARIA PEREZ RODRIGUEZ",
    days_valid=365,
    expired=False,
):
    """Generate a self-signed test certificate."""
    now = datetime.datetime.utcnow()
    if expired:
        not_before = now - datetime.timedelta(days=days_valid + 1)
        not_after = now - datetime.timedelta(days=1)
    else:
        not_before = now - datetime.timedelta(days=1)
        not_after = now + datetime.timedelta(days=days_valid)

    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
        x509.NameAttribute(NameOID.SERIAL_NUMBER, rfc),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "MX"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SAT"),
    ])

    issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "AC del SAT"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SAT"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .sign(private_key, hashes.SHA256(), default_backend())
    )
    return cert


def _write_cer(cert, path):
    """Write certificate as DER .cer file."""
    path.write_bytes(cert.public_bytes(serialization.Encoding.DER))


def _write_key(private_key, path, password="test123"):
    """Write private key as encrypted DER .key file."""
    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                password.encode("utf-8")
            ),
        )
    )


def _write_pem_cer(cert, path):
    """Write certificate as PEM (wrong format for SAT but should still load)."""
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


# ─── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def key_pair():
    return _generate_key_pair()


@pytest.fixture
def valid_cert(key_pair):
    return _generate_cert(key_pair)


@pytest.fixture
def expired_cert(key_pair):
    return _generate_cert(key_pair, expired=True)


@pytest.fixture
def cer_file(tmp_path, valid_cert):
    p = tmp_path / "test.cer"
    _write_cer(valid_cert, p)
    return p


@pytest.fixture
def key_file(tmp_path, key_pair):
    p = tmp_path / "test.key"
    _write_key(key_pair, p, password="test123")
    return p


@pytest.fixture
def expired_cer_file(tmp_path, expired_cert):
    p = tmp_path / "expired.cer"
    _write_cer(expired_cert, p)
    return p


# ─── Test: Enums ─────────────────────────────────────────────────────

class TestEnums:
    def test_estado_vigente(self):
        assert EstadoCertificado.VIGENTE.value == "Vigente"

    def test_estado_vencido(self):
        assert EstadoCertificado.VENCIDO.value == "Vencido"

    def test_estado_por_vencer(self):
        assert EstadoCertificado.POR_VENCER.value == "Por Vencer"

    def test_estado_no_cargado(self):
        assert EstadoCertificado.NO_CARGADO.value == "No Cargado"

    def test_four_estados(self):
        assert len(EstadoCertificado) == 4

    def test_tipo_efirma(self):
        assert TipoCertificado.EFIRMA.value == "e.firma (FIEL)"

    def test_tipo_csd(self):
        assert TipoCertificado.CSD.value == "CSD (Sello Digital)"

    def test_two_tipos(self):
        assert len(TipoCertificado) == 2


# ─── Test: Exceptions ────────────────────────────────────────────────

class TestExceptions:
    def test_password_error(self):
        with pytest.raises(EFirmaPasswordError):
            raise EFirmaPasswordError("wrong password")

    def test_certificate_error(self):
        with pytest.raises(EFirmaCertificateError):
            raise EFirmaCertificateError("invalid cer")

    def test_expired_error(self):
        with pytest.raises(EFirmaExpiredError):
            raise EFirmaExpiredError("expired")

    def test_signing_error(self):
        with pytest.raises(EFirmaSigningError):
            raise EFirmaSigningError("sign failed")

    def test_key_mismatch_error(self):
        with pytest.raises(EFirmaKeyMismatchError):
            raise EFirmaKeyMismatchError("mismatch")

    def test_all_inherit_exception(self):
        for exc_class in [EFirmaPasswordError, EFirmaCertificateError,
                          EFirmaExpiredError, EFirmaSigningError,
                          EFirmaKeyMismatchError]:
            assert issubclass(exc_class, Exception)


# ─── Test: CertificadoInfo ──────────────────────────────────────────

class TestCertificadoInfo:
    def test_create(self):
        info = CertificadoInfo(
            rfc="MOPR881228EF9",
            nombre_titular="MARIA PEREZ",
            numero_serie="ABC123",
            tipo=TipoCertificado.EFIRMA.value,
            estado=EstadoCertificado.VIGENTE.value,
            fecha_inicio_vigencia="2025-01-01",
            fecha_fin_vigencia="2029-01-01",
            dias_restantes=1000,
            emisor_certificado="AC del SAT",
            algoritmo="RSA-2048",
            huella_digital="AABB",
        )
        assert info.rfc == "MOPR881228EF9"

    def test_to_dict(self):
        info = CertificadoInfo(
            rfc="X", nombre_titular="Y", numero_serie="Z",
            tipo="T", estado="E", fecha_inicio_vigencia="A",
            fecha_fin_vigencia="B", dias_restantes=10,
            emisor_certificado="C", algoritmo="D", huella_digital="F",
        )
        d = info.to_dict()
        assert isinstance(d, dict)
        assert d["rfc"] == "X"
        assert "dias_restantes" in d

    def test_whatsapp_vigente(self):
        info = CertificadoInfo(
            rfc="MOPR881228EF9", nombre_titular="MARIA PEREZ",
            numero_serie="ABC", tipo=TipoCertificado.EFIRMA.value,
            estado=EstadoCertificado.VIGENTE.value,
            fecha_inicio_vigencia="2025-01-01",
            fecha_fin_vigencia="2029-01-01", dias_restantes=1000,
            emisor_certificado="SAT", algoritmo="RSA-2048",
            huella_digital="AB",
        )
        wsp = info.resumen_whatsapp()
        assert "━━━" in wsp
        assert "✅" in wsp
        assert "MOPR881228EF9" in wsp

    def test_whatsapp_vencido(self):
        info = CertificadoInfo(
            rfc="X", nombre_titular="Y", numero_serie="Z",
            tipo="T", estado=EstadoCertificado.VENCIDO.value,
            fecha_inicio_vigencia="A", fecha_fin_vigencia="B",
            dias_restantes=0, emisor_certificado="C",
            algoritmo="D", huella_digital="F",
        )
        wsp = info.resumen_whatsapp()
        assert "❌" in wsp
        assert "VENCIDO" in wsp

    def test_whatsapp_por_vencer(self):
        info = CertificadoInfo(
            rfc="X", nombre_titular="Y", numero_serie="Z",
            tipo="T", estado=EstadoCertificado.POR_VENCER.value,
            fecha_inicio_vigencia="A", fecha_fin_vigencia="B",
            dias_restantes=15, emisor_certificado="C",
            algoritmo="D", huella_digital="F",
        )
        wsp = info.resumen_whatsapp()
        assert "⚠️" in wsp
        assert "Renueva" in wsp


# ─── Test: load_certificate ─────────────────────────────────────────

class TestLoadCertificate:
    def test_loads_der_cer(self, cer_file):
        info, cert = load_certificate(cer_file)
        assert isinstance(info, CertificadoInfo)
        assert isinstance(cert, x509.Certificate)

    def test_extracts_rfc(self, cer_file):
        info, _ = load_certificate(cer_file)
        assert info.rfc == "MOPR881228EF9"

    def test_extracts_nombre(self, cer_file):
        info, _ = load_certificate(cer_file)
        assert "MARIA PEREZ" in info.nombre_titular

    def test_serial_not_empty(self, cer_file):
        info, _ = load_certificate(cer_file)
        assert len(info.numero_serie) > 0

    def test_estado_vigente(self, cer_file):
        info, _ = load_certificate(cer_file)
        assert info.estado == EstadoCertificado.VIGENTE.value

    def test_dias_restantes_positive(self, cer_file):
        info, _ = load_certificate(cer_file)
        assert info.dias_restantes > 0

    def test_algoritmo_rsa(self, cer_file):
        info, _ = load_certificate(cer_file)
        assert "RSA" in info.algoritmo

    def test_huella_digital_sha256(self, cer_file):
        info, _ = load_certificate(cer_file)
        assert len(info.huella_digital) == 64  # SHA-256 hex

    def test_loads_pem_cer(self, tmp_path, valid_cert):
        p = tmp_path / "test.pem"
        _write_pem_cer(valid_cert, p)
        info, cert = load_certificate(p)
        assert info.rfc == "MOPR881228EF9"

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_certificate("/nonexistent/path.cer")

    def test_invalid_file_raises(self, tmp_path):
        p = tmp_path / "garbage.cer"
        p.write_bytes(b"this is not a certificate")
        with pytest.raises(EFirmaCertificateError):
            load_certificate(p)

    def test_empty_file_raises(self, tmp_path):
        p = tmp_path / "empty.cer"
        p.write_bytes(b"")
        with pytest.raises(EFirmaCertificateError):
            load_certificate(p)

    def test_expired_cert_detected(self, expired_cer_file):
        info, _ = load_certificate(expired_cer_file)
        assert info.estado == EstadoCertificado.VENCIDO.value
        assert info.dias_restantes == 0

    def test_issuer_extracted(self, cer_file):
        info, _ = load_certificate(cer_file)
        assert "SAT" in info.emisor_certificado


# ─── Test: load_private_key ──────────────────────────────────────────

class TestLoadPrivateKey:
    def test_loads_with_correct_password(self, key_file):
        key = load_private_key(key_file, "test123")
        assert isinstance(key, rsa.RSAPrivateKey)

    def test_wrong_password_raises(self, key_file):
        with pytest.raises(EFirmaPasswordError):
            load_private_key(key_file, "wrong_password")

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_private_key("/nonexistent/path.key", "pwd")

    def test_invalid_file_raises(self, tmp_path):
        p = tmp_path / "garbage.key"
        p.write_bytes(b"this is not a key")
        with pytest.raises(EFirmaPasswordError):
            load_private_key(p, "test")

    def test_empty_file_raises(self, tmp_path):
        p = tmp_path / "empty.key"
        p.write_bytes(b"")
        with pytest.raises(EFirmaPasswordError):
            load_private_key(p, "test")

    def test_key_size_2048(self, key_file):
        key = load_private_key(key_file, "test123")
        assert key.key_size == 2048


# ─── Test: validate_certificate_pair ─────────────────────────────────

class TestValidatePair:
    def test_valid_pair(self, cer_file, key_file):
        info = validate_certificate_pair(cer_file, key_file, "test123")
        assert isinstance(info, CertificadoInfo)
        assert info.rfc == "MOPR881228EF9"

    def test_mismatched_pair_raises(self, cer_file, tmp_path):
        """Different key than the cert's key should raise mismatch."""
        other_key = _generate_key_pair()
        other_key_path = tmp_path / "other.key"
        _write_key(other_key, other_key_path, password="test123")
        with pytest.raises(EFirmaKeyMismatchError):
            validate_certificate_pair(cer_file, other_key_path, "test123")

    def test_expired_pair_raises(self, expired_cer_file, tmp_path, key_pair):
        key_path = tmp_path / "key.key"
        _write_key(key_pair, key_path, password="test123")
        with pytest.raises(EFirmaExpiredError):
            validate_certificate_pair(expired_cer_file, key_path, "test123")

    def test_wrong_password_raises(self, cer_file, key_file):
        with pytest.raises(EFirmaPasswordError):
            validate_certificate_pair(cer_file, key_file, "wrong")


# ─── Test: generate_sat_auth_token ───────────────────────────────────

class TestGenerateAuthToken:
    def test_returns_string(self, valid_cert, key_pair):
        xml = generate_sat_auth_token(valid_cert, key_pair)
        assert isinstance(xml, str)

    def test_is_valid_xml(self, valid_cert, key_pair):
        from lxml import etree
        xml = generate_sat_auth_token(valid_cert, key_pair)
        etree.fromstring(xml.encode("utf-8"))  # Should not raise

    def test_contains_soap_envelope(self, valid_cert, key_pair):
        xml = generate_sat_auth_token(valid_cert, key_pair)
        assert "Envelope" in xml
        assert NS_SOAP in xml

    def test_contains_timestamp(self, valid_cert, key_pair):
        xml = generate_sat_auth_token(valid_cert, key_pair)
        assert "Timestamp" in xml
        assert "Created" in xml
        assert "Expires" in xml

    def test_contains_binary_security_token(self, valid_cert, key_pair):
        xml = generate_sat_auth_token(valid_cert, key_pair)
        assert "BinarySecurityToken" in xml

    def test_contains_signature(self, valid_cert, key_pair):
        xml = generate_sat_auth_token(valid_cert, key_pair)
        assert "Signature" in xml
        assert "SignatureValue" in xml
        assert "DigestValue" in xml

    def test_contains_autentica_body(self, valid_cert, key_pair):
        xml = generate_sat_auth_token(valid_cert, key_pair)
        assert "Autentica" in xml
        assert "DescargaMasivaTerceros" in xml

    def test_custom_uuid(self, valid_cert, key_pair):
        xml = generate_sat_auth_token(valid_cert, key_pair, token_uuid="my-uuid-123")
        assert "my-uuid-123" in xml

    def test_unique_uuids(self, valid_cert, key_pair):
        xml1 = generate_sat_auth_token(valid_cert, key_pair)
        xml2 = generate_sat_auth_token(valid_cert, key_pair)
        # Different UUIDs means different token content
        assert xml1 != xml2

    def test_cert_b64_in_token(self, valid_cert, key_pair):
        xml = generate_sat_auth_token(valid_cert, key_pair)
        cert_der = valid_cert.public_bytes(serialization.Encoding.DER)
        cert_b64 = base64.b64encode(cert_der).decode("ascii")
        assert cert_b64 in xml

    def test_signature_verifiable(self, valid_cert, key_pair):
        """The signature in the token should be verifiable with the public key."""
        from lxml import etree
        xml = generate_sat_auth_token(valid_cert, key_pair)
        root = etree.fromstring(xml.encode("utf-8"))

        # Extract SignatureValue
        ns = {"ds": NS_DSIG}
        sig_val_elem = root.find(f".//{{{NS_DSIG}}}SignatureValue")
        assert sig_val_elem is not None
        sig_bytes = base64.b64decode(sig_val_elem.text)

        # Extract and canonicalize SignedInfo
        si_elem = root.find(f".//{{{NS_DSIG}}}SignedInfo")
        assert si_elem is not None
        si_c14n = etree.tostring(si_elem, method="c14n", exclusive=True)

        # Verify with public key (should not raise)
        valid_cert.public_key().verify(
            sig_bytes,
            si_c14n,
            padding.PKCS1v15(),
            hashes.SHA1(),
        )


# ─── Test: sign_soap_body ───────────────────────────────────────────

class TestSignSoapBody:
    def test_returns_string(self, valid_cert, key_pair):
        sig = sign_soap_body("<body>test</body>", valid_cert, key_pair)
        assert isinstance(sig, str)

    def test_contains_signature_elements(self, valid_cert, key_pair):
        sig = sign_soap_body("<body>test</body>", valid_cert, key_pair)
        assert "Signature" in sig
        assert "SignatureValue" in sig
        assert "DigestValue" in sig
        assert "X509Certificate" in sig

    def test_uses_sha256(self, valid_cert, key_pair):
        sig = sign_soap_body("<body>test</body>", valid_cert, key_pair)
        assert "sha256" in sig.lower() or "sha-256" in sig.lower()

    def test_signature_verifiable(self, valid_cert, key_pair):
        from lxml import etree
        body_xml = '<TestBody xmlns="http://test.com">content</TestBody>'
        sig_xml = sign_soap_body(body_xml, valid_cert, key_pair)

        root = etree.fromstring(sig_xml.encode("utf-8"))
        sig_val_elem = root.find(f".//{{{NS_DSIG}}}SignatureValue")
        assert sig_val_elem is not None
        sig_bytes = base64.b64decode(sig_val_elem.text)

        si_elem = root.find(f".//{{{NS_DSIG}}}SignedInfo")
        si_c14n = etree.tostring(si_elem, method="c14n", exclusive=True)

        valid_cert.public_key().verify(
            sig_bytes,
            si_c14n,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_custom_body_id(self, valid_cert, key_pair):
        sig = sign_soap_body("<x>y</x>", valid_cert, key_pair, body_id="myBody")
        assert "myBody" in sig

    def test_invalid_xml_raises(self, valid_cert, key_pair):
        with pytest.raises(EFirmaSigningError):
            sign_soap_body("not xml at all <<<", valid_cert, key_pair)


# ─── Test: _extract_rfc ──────────────────────────────────────────────

class TestExtractRFC:
    def test_from_serial_number_attr(self, valid_cert):
        rfc = _extract_rfc(valid_cert)
        assert rfc == "MOPR881228EF9"

    def test_13_char_persona_fisica(self, key_pair):
        cert = _generate_cert(key_pair, rfc="XAXX010101000")
        assert _extract_rfc(cert) == "XAXX010101000"

    def test_12_char_persona_moral(self, key_pair):
        cert = _generate_cert(key_pair, rfc="SAT970701NN3")
        assert _extract_rfc(cert) == "SAT970701NN3"

    def test_no_rfc_returns_empty(self, key_pair):
        """Certificate without RFC in subject returns empty string."""
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Test User"),
            x509.NameAttribute(NameOID.COUNTRY_NAME, "MX"),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key_pair.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .sign(key_pair, hashes.SHA256(), default_backend())
        )
        rfc = _extract_rfc(cert)
        assert rfc == ""


# ─── Test: _extract_cert_info ────────────────────────────────────────

class TestExtractCertInfo:
    def test_returns_certificado_info(self, valid_cert):
        info = _extract_cert_info(valid_cert)
        assert isinstance(info, CertificadoInfo)

    def test_vigente_cert(self, valid_cert):
        info = _extract_cert_info(valid_cert)
        assert info.estado == EstadoCertificado.VIGENTE.value

    def test_expired_cert(self, expired_cert):
        info = _extract_cert_info(expired_cert)
        assert info.estado == EstadoCertificado.VENCIDO.value

    def test_por_vencer_cert(self, key_pair):
        cert = _generate_cert(key_pair, days_valid=15)
        info = _extract_cert_info(cert)
        assert info.estado == EstadoCertificado.POR_VENCER.value

    def test_rsa_2048(self, valid_cert):
        info = _extract_cert_info(valid_cert)
        assert info.algoritmo == "RSA-2048"


# ─── Test: _wipe_key ────────────────────────────────────────────────

class TestWipeKey:
    def test_does_not_crash(self, key_pair):
        """Wiping a key should not raise any errors."""
        _wipe_key(key_pair)

    def test_none_does_not_crash(self):
        _wipe_key(None)


# ─── Test: Namespace Constants ───────────────────────────────────────

class TestConstants:
    def test_ns_soap(self):
        assert "xmlsoap.org" in NS_SOAP

    def test_ns_wsu(self):
        assert "wss-wssecurity-utility" in NS_WSU

    def test_ns_wsse(self):
        assert "wss-wssecurity-secext" in NS_WSSE

    def test_ns_dsig(self):
        assert "xmldsig" in NS_DSIG


# ─── Test: Module Exports ───────────────────────────────────────────

class TestModuleExports:
    def test_all_functions_importable(self):
        from src.tools.sat_efirma import (
            load_certificate, load_private_key,
            validate_certificate_pair, generate_sat_auth_token,
            sign_soap_body,
        )
        assert all(callable(f) for f in [
            load_certificate, load_private_key,
            validate_certificate_pair, generate_sat_auth_token,
            sign_soap_body,
        ])

    def test_all_classes_importable(self):
        from src.tools.sat_efirma import (
            CertificadoInfo, EstadoCertificado, TipoCertificado,
        )
        assert CertificadoInfo is not None

    def test_all_exceptions_importable(self):
        from src.tools.sat_efirma import (
            EFirmaPasswordError, EFirmaCertificateError,
            EFirmaExpiredError, EFirmaSigningError,
            EFirmaKeyMismatchError,
        )
        assert all(issubclass(e, Exception) for e in [
            EFirmaPasswordError, EFirmaCertificateError,
            EFirmaExpiredError, EFirmaSigningError,
            EFirmaKeyMismatchError,
        ])
