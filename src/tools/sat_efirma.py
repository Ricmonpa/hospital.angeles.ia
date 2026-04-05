"""OpenDoc - e.firma (FIEL) Certificate Handler.

Loads SAT e.firma (.cer + .key) files, extracts certificate metadata,
and generates signed XML tokens for SAT SOAP web service authentication.

SECURITY RULES:
1. Private keys are decrypted only when needed and wiped after use
2. Passwords are never stored — only used during load_key()
3. All operations are memory-only (no temp files with key material)
4. Certificate metadata (RFC, name, serial) is safe to keep in memory

Based on: SAT CFDI 4.0 standard, WS-Security X.509 token profile.
"""

import base64
import gc
import hashlib
import uuid as uuid_module
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Union
from enum import Enum

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID

from lxml import etree


# ─── Enums ────────────────────────────────────────────────────────────

class EstadoCertificado(str, Enum):
    """Certificate validity state."""
    VIGENTE = "Vigente"
    VENCIDO = "Vencido"
    POR_VENCER = "Por Vencer"       # Within 30 days
    NO_CARGADO = "No Cargado"


class TipoCertificado(str, Enum):
    """Certificate type."""
    EFIRMA = "e.firma (FIEL)"
    CSD = "CSD (Sello Digital)"


# ─── Exceptions ───────────────────────────────────────────────────────

class EFirmaPasswordError(Exception):
    """Raised when the private key password is incorrect."""
    pass


class EFirmaCertificateError(Exception):
    """Raised when the .cer file is invalid or unreadable."""
    pass


class EFirmaExpiredError(Exception):
    """Raised when the certificate has expired."""
    pass


class EFirmaSigningError(Exception):
    """Raised when XML signing fails."""
    pass


class EFirmaKeyMismatchError(Exception):
    """Raised when .cer and .key don't match (different key pairs)."""
    pass


# ─── Dataclasses ──────────────────────────────────────────────────────

@dataclass
class CertificadoInfo:
    """Metadata extracted from an e.firma certificate (.cer)."""
    rfc: str
    nombre_titular: str
    numero_serie: str                  # Certificate serial (hex)
    tipo: str                          # TipoCertificado value
    estado: str                        # EstadoCertificado value
    fecha_inicio_vigencia: str         # ISO date
    fecha_fin_vigencia: str            # ISO date
    dias_restantes: int
    emisor_certificado: str            # Issuer CN
    algoritmo: str                     # e.g., "RSA-2048"
    huella_digital: str                # SHA-256 fingerprint (hex)

    def to_dict(self) -> dict:
        return asdict(self)

    def resumen_whatsapp(self) -> str:
        """WhatsApp-friendly certificate summary."""
        icon = "✅" if self.estado == EstadoCertificado.VIGENTE.value else \
               "⚠️" if self.estado == EstadoCertificado.POR_VENCER.value else "❌"
        lines = [
            f"━━━ CERTIFICADO {self.tipo} ━━━",
            f"{icon} Estado: {self.estado}",
            f"👤 {self.nombre_titular}",
            f"📋 RFC: {self.rfc}",
            f"🔢 Serie: {self.numero_serie}",
            f"📅 Vigencia: {self.fecha_inicio_vigencia} → {self.fecha_fin_vigencia}",
            f"⏳ Días restantes: {self.dias_restantes}",
        ]
        if 0 < self.dias_restantes <= 30:
            lines.append("⚠️ ¡Renueva pronto en sat.gob.mx!")
        elif self.dias_restantes <= 0:
            lines.append("🚨 VENCIDO — Requiere renovación inmediata")
        return "\n".join(lines)


# ─── XML Namespace Constants ─────────────────────────────────────────

NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
NS_WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
NS_DSIG = "http://www.w3.org/2000/09/xmldsig#"
NS_C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"

BST_VALUE_TYPE = (
    "http://docs.oasis-open.org/wss/2004/01/"
    "oasis-200401-wss-x509-token-profile-1.0#X509v3"
)
BST_ENCODING_TYPE = (
    "http://docs.oasis-open.org/wss/2004/01/"
    "oasis-200401-wss-soap-message-security-1.0#Base64Binary"
)


# ─── Core Functions ───────────────────────────────────────────────────

def load_certificate(
    cer_path: Union[str, Path],
) -> tuple:
    """Load and parse a .cer (X.509 DER) certificate file.

    Args:
        cer_path: Path to the .cer file.

    Returns:
        Tuple of (CertificadoInfo, x509.Certificate object).

    Raises:
        EFirmaCertificateError: If the file is invalid.
        FileNotFoundError: If cer_path doesn't exist.
    """
    path = Path(cer_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo .cer no encontrado: {path}")

    cer_bytes = path.read_bytes()
    if not cer_bytes:
        raise EFirmaCertificateError("Archivo .cer vacío")

    # Try DER format first, then PEM
    cert = None
    try:
        cert = x509.load_der_x509_certificate(cer_bytes, default_backend())
    except Exception:
        try:
            cert = x509.load_pem_x509_certificate(cer_bytes, default_backend())
        except Exception as e:
            raise EFirmaCertificateError(
                f"No se pudo leer el certificado. "
                f"Asegúrate de que sea un archivo .cer válido del SAT: {e}"
            )

    info = _extract_cert_info(cert)
    return info, cert


def load_private_key(
    key_path: Union[str, Path],
    password: str,
) -> rsa.RSAPrivateKey:
    """Load and decrypt a .key (PKCS#8 DER encrypted) private key file.

    Args:
        key_path: Path to the .key file.
        password: Decryption password (NOT stored).

    Returns:
        RSAPrivateKey object.

    Raises:
        EFirmaPasswordError: If password is wrong.
        FileNotFoundError: If key_path doesn't exist.
    """
    path = Path(key_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo .key no encontrado: {path}")

    key_bytes = path.read_bytes()
    if not key_bytes:
        raise EFirmaPasswordError("Archivo .key vacío")

    pwd_bytes = password.encode("utf-8") if password else None

    # Try DER (most common SAT format)
    try:
        private_key = serialization.load_der_private_key(
            key_bytes, password=pwd_bytes, backend=default_backend()
        )
    except (ValueError, TypeError):
        # Try PEM as fallback
        try:
            private_key = serialization.load_pem_private_key(
                key_bytes, password=pwd_bytes, backend=default_backend()
            )
        except (ValueError, TypeError) as e:
            raise EFirmaPasswordError(
                f"No se pudo descifrar la llave privada. "
                f"Verifica la contraseña: {e}"
            )

    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise EFirmaPasswordError(
            "La llave privada no es RSA. "
            "El SAT solo emite llaves RSA para e.firma."
        )

    return private_key


def validate_certificate_pair(
    cer_path: Union[str, Path],
    key_path: Union[str, Path],
    password: str,
) -> CertificadoInfo:
    """Validate that a .cer and .key pair match and are usable.

    Performs:
    1. Load and parse the certificate
    2. Load and decrypt the private key
    3. Verify the public key in the cert matches the private key
    4. Check certificate validity (not expired)
    5. Wipe private key from memory

    Returns:
        CertificadoInfo with full certificate details.

    Raises:
        EFirmaKeyMismatchError: If .cer and .key don't match.
        EFirmaExpiredError: If certificate is expired.
    """
    info, cert = load_certificate(cer_path)
    private_key = load_private_key(key_path, password)

    try:
        # Verify public keys match
        cert_pub = cert.public_key().public_numbers()
        key_pub = private_key.public_key().public_numbers()
        if cert_pub != key_pub:
            raise EFirmaKeyMismatchError(
                "El certificado (.cer) y la llave privada (.key) no corresponden. "
                "Asegúrate de usar el par correcto."
            )

        # Check expiry
        if info.estado == EstadoCertificado.VENCIDO.value:
            raise EFirmaExpiredError(
                f"El certificado venció el {info.fecha_fin_vigencia}. "
                f"Renueva tu e.firma en sat.gob.mx."
            )
    finally:
        _wipe_key(private_key)

    return info


def generate_sat_auth_token(
    cert: x509.Certificate,
    private_key: rsa.RSAPrivateKey,
    token_uuid: Optional[str] = None,
    validity_seconds: int = 300,
) -> str:
    """Generate a signed XML security token for SAT SOAP authentication.

    Creates a WS-Security SecurityToken with:
    - Timestamp (Created + Expires)
    - BinarySecurityToken (base64-encoded certificate)
    - Signed digest (SHA-1 + RSA PKCS#1 v1.5)

    The SAT authentication service uses SHA-1 for signature digests
    (legacy requirement — their endpoint rejects SHA-256).

    Args:
        cert: X.509 certificate object.
        private_key: Decrypted RSA private key.
        token_uuid: Optional UUID (auto-generated if None).
        validity_seconds: Token lifetime (default 5 minutes).

    Returns:
        Complete SOAP envelope XML string.

    Raises:
        EFirmaSigningError: If signing fails.
    """
    if token_uuid is None:
        token_uuid = str(uuid_module.uuid4())

    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=validity_seconds)
    created_str = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    expires_str = expires.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Certificate as base64
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    cert_b64 = base64.b64encode(cert_der).decode("ascii")

    bst_id = f"uuid-{token_uuid}"
    ts_id = "_0"

    try:
        # Build the Timestamp element for signing
        ts_xml = (
            f'<u:Timestamp xmlns:u="{NS_WSU}" u:Id="{ts_id}">'
            f'<u:Created>{created_str}</u:Created>'
            f'<u:Expires>{expires_str}</u:Expires>'
            f'</u:Timestamp>'
        )

        # Canonicalize timestamp for digest
        ts_element = etree.fromstring(ts_xml.encode("utf-8"))
        ts_c14n = etree.tostring(ts_element, method="c14n", exclusive=True)

        # Digest of timestamp
        digest = hashlib.sha1(ts_c14n).digest()
        digest_b64 = base64.b64encode(digest).decode("ascii")

        # Build SignedInfo
        signed_info_xml = (
            f'<SignedInfo xmlns="{NS_DSIG}">'
            f'<CanonicalizationMethod Algorithm="{NS_C14N}"/>'
            f'<SignatureMethod Algorithm="{NS_DSIG}rsa-sha1"/>'
            f'<Reference URI="#{ts_id}">'
            f'<Transforms>'
            f'<Transform Algorithm="{NS_C14N}"/>'
            f'</Transforms>'
            f'<DigestMethod Algorithm="{NS_DSIG}sha1"/>'
            f'<DigestValue>{digest_b64}</DigestValue>'
            f'</Reference>'
            f'</SignedInfo>'
        )

        # Canonicalize SignedInfo for signing
        si_element = etree.fromstring(signed_info_xml.encode("utf-8"))
        si_c14n = etree.tostring(si_element, method="c14n", exclusive=True)

        # Sign with RSA-SHA1 (SAT requirement)
        signature_bytes = private_key.sign(
            si_c14n,
            padding.PKCS1v15(),
            hashes.SHA1(),
        )
        sig_b64 = base64.b64encode(signature_bytes).decode("ascii")

        # Assemble the full SOAP envelope
        envelope = (
            f'<s:Envelope xmlns:s="{NS_SOAP}" '
            f'xmlns:u="{NS_WSU}">'
            f'<s:Header>'
            f'<o:Security xmlns:o="{NS_WSSE}" s:mustUnderstand="1">'
            f'<u:Timestamp u:Id="{ts_id}">'
            f'<u:Created>{created_str}</u:Created>'
            f'<u:Expires>{expires_str}</u:Expires>'
            f'</u:Timestamp>'
            f'<o:BinarySecurityToken u:Id="{bst_id}" '
            f'ValueType="{BST_VALUE_TYPE}" '
            f'EncodingType="{BST_ENCODING_TYPE}">'
            f'{cert_b64}'
            f'</o:BinarySecurityToken>'
            f'<Signature xmlns="{NS_DSIG}">'
            f'<SignedInfo>'
            f'<CanonicalizationMethod Algorithm="{NS_C14N}"/>'
            f'<SignatureMethod Algorithm="{NS_DSIG}rsa-sha1"/>'
            f'<Reference URI="#{ts_id}">'
            f'<Transforms>'
            f'<Transform Algorithm="{NS_C14N}"/>'
            f'</Transforms>'
            f'<DigestMethod Algorithm="{NS_DSIG}sha1"/>'
            f'<DigestValue>{digest_b64}</DigestValue>'
            f'</Reference>'
            f'</SignedInfo>'
            f'<SignatureValue>{sig_b64}</SignatureValue>'
            f'<KeyInfo>'
            f'<o:SecurityTokenReference>'
            f'<o:Reference URI="#{bst_id}" ValueType="{BST_VALUE_TYPE}"/>'
            f'</o:SecurityTokenReference>'
            f'</KeyInfo>'
            f'</Signature>'
            f'</o:Security>'
            f'</s:Header>'
            f'<s:Body>'
            f'<Autentica xmlns="http://DescargaMasivaTerceros.gob.mx"/>'
            f'</s:Body>'
            f'</s:Envelope>'
        )

        return envelope

    except Exception as e:
        raise EFirmaSigningError(f"Error al generar token de autenticación: {e}")


def sign_soap_body(
    body_xml: str,
    cert: x509.Certificate,
    private_key: rsa.RSAPrivateKey,
    body_id: str = "_1",
) -> str:
    """Sign a SOAP body element for SAT service requests.

    Used for signing Solicitud, Verificación, and Descarga requests.
    Uses SHA-256 (newer SAT endpoints accept this).

    Args:
        body_xml: The SOAP body content XML string.
        cert: X.509 certificate.
        private_key: RSA private key.
        body_id: ID attribute for the body element.

    Returns:
        Signature XML block to insert into the SOAP header.

    Raises:
        EFirmaSigningError: If signing fails.
    """
    try:
        body_element = etree.fromstring(body_xml.encode("utf-8"))
        body_c14n = etree.tostring(body_element, method="c14n", exclusive=True)

        # Digest
        digest = hashlib.sha256(body_c14n).digest()
        digest_b64 = base64.b64encode(digest).decode("ascii")

        # SignedInfo
        signed_info_xml = (
            f'<SignedInfo xmlns="{NS_DSIG}">'
            f'<CanonicalizationMethod Algorithm="{NS_C14N}"/>'
            f'<SignatureMethod Algorithm="{NS_DSIG}rsa-sha256"/>'
            f'<Reference URI="#{body_id}">'
            f'<Transforms>'
            f'<Transform Algorithm="{NS_C14N}"/>'
            f'</Transforms>'
            f'<DigestMethod Algorithm="{NS_DSIG}sha256"/>'
            f'<DigestValue>{digest_b64}</DigestValue>'
            f'</Reference>'
            f'</SignedInfo>'
        )

        si_element = etree.fromstring(signed_info_xml.encode("utf-8"))
        si_c14n = etree.tostring(si_element, method="c14n", exclusive=True)

        signature_bytes = private_key.sign(
            si_c14n,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        sig_b64 = base64.b64encode(signature_bytes).decode("ascii")

        cert_der = cert.public_bytes(serialization.Encoding.DER)
        cert_b64 = base64.b64encode(cert_der).decode("ascii")

        return (
            f'<Signature xmlns="{NS_DSIG}">'
            f'{signed_info_xml}'
            f'<SignatureValue>{sig_b64}</SignatureValue>'
            f'<KeyInfo>'
            f'<X509Data>'
            f'<X509Certificate>{cert_b64}</X509Certificate>'
            f'</X509Data>'
            f'</KeyInfo>'
            f'</Signature>'
        )

    except EFirmaSigningError:
        raise
    except Exception as e:
        raise EFirmaSigningError(f"Error al firmar SOAP body: {e}")


def _wipe_key(private_key) -> None:
    """Best-effort memory wipe of a private key reference.

    Python cannot guarantee memory erasure, but we:
    1. Delete the reference
    2. Call gc.collect() to encourage cleanup
    """
    del private_key
    gc.collect()


# ─── Internal Helpers ─────────────────────────────────────────────────

def _extract_cert_info(cert: x509.Certificate) -> CertificadoInfo:
    """Extract metadata from an X.509 certificate."""
    now = datetime.now(timezone.utc)

    # Extract RFC from subject
    rfc = _extract_rfc(cert)

    # Extract name
    nombre = ""
    try:
        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn_attrs:
            nombre = cn_attrs[0].value
    except Exception:
        pass

    # Serial number
    serial_hex = format(cert.serial_number, "x").upper()

    # Validity
    not_before = cert.not_valid_before_utc if hasattr(cert, "not_valid_before_utc") \
        else cert.not_valid_before.replace(tzinfo=timezone.utc)
    not_after = cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc") \
        else cert.not_valid_after.replace(tzinfo=timezone.utc)

    dias = (not_after - now).days

    if dias <= 0:
        estado = EstadoCertificado.VENCIDO.value
    elif dias <= 30:
        estado = EstadoCertificado.POR_VENCER.value
    else:
        estado = EstadoCertificado.VIGENTE.value

    # Issuer
    emisor = ""
    try:
        issuer_cn = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        if issuer_cn:
            emisor = issuer_cn[0].value
    except Exception:
        emisor = "SAT"

    # Key algorithm
    pub_key = cert.public_key()
    if isinstance(pub_key, rsa.RSAPublicKey):
        bits = pub_key.key_size
        algoritmo = f"RSA-{bits}"
    else:
        algoritmo = "Desconocido"

    # Fingerprint
    huella = cert.fingerprint(hashes.SHA256()).hex().upper()

    # Determine cert type (e.firma vs CSD based on issuer OU)
    tipo = TipoCertificado.EFIRMA.value
    try:
        ou_attrs = cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)
        for ou in ou_attrs:
            if "CSD" in str(ou.value).upper() or "sello" in str(ou.value).lower():
                tipo = TipoCertificado.CSD.value
                break
    except Exception:
        pass

    return CertificadoInfo(
        rfc=rfc,
        nombre_titular=nombre,
        numero_serie=serial_hex,
        tipo=tipo,
        estado=estado,
        fecha_inicio_vigencia=not_before.strftime("%Y-%m-%d"),
        fecha_fin_vigencia=not_after.strftime("%Y-%m-%d"),
        dias_restantes=max(0, dias),
        emisor_certificado=emisor,
        algoritmo=algoritmo,
        huella_digital=huella,
    )


def _extract_rfc(cert: x509.Certificate) -> str:
    """Extract RFC from SAT certificate.

    SAT embeds the RFC in:
    1. Subject's SERIAL_NUMBER attribute (most common)
    2. Subject's x500UniqueIdentifier
    3. Common name (fallback)
    """
    # Try SERIAL_NUMBER OID first (SAT standard location)
    try:
        sn_attrs = cert.subject.get_attributes_for_oid(NameOID.SERIAL_NUMBER)
        if sn_attrs:
            val = sn_attrs[0].value.strip()
            if val and "/" in val:
                # Format: "MOPR881228EF9 / HXGE7101306F8"
                val = val.split("/")[0].strip()
            if 12 <= len(val) <= 13:
                return val.upper()
    except Exception:
        pass

    # Try x500UniqueIdentifier (OID 2.5.4.45)
    try:
        from cryptography.x509.oid import ObjectIdentifier
        uid_oid = ObjectIdentifier("2.5.4.45")
        uid_attrs = cert.subject.get_attributes_for_oid(uid_oid)
        if uid_attrs:
            val = uid_attrs[0].value.strip()
            if 12 <= len(val) <= 13:
                return val.upper()
    except Exception:
        pass

    # Fallback: parse from CN
    try:
        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn_attrs:
            cn = cn_attrs[0].value
            # CN sometimes contains RFC after a separator
            for sep in ["/", "|", " - "]:
                if sep in cn:
                    parts = cn.split(sep)
                    for part in parts:
                        part = part.strip()
                        if 12 <= len(part) <= 13 and part.isalnum():
                            return part.upper()
    except Exception:
        pass

    return ""
