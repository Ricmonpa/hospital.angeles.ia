"""OpenDoc - Receipt Vision Analyzer (Phase 3).

Uses Gemini Vision to extract structured data from Mexican invoices,
receipts, and fiscal documents uploaded via WhatsApp or the dashboard.

Extracts: Fecha, RFC Emisor, RFC Receptor, Monto Total, IVA, Concepto,
Folio Fiscal (UUID), and fiscal deductibility classification.
"""

import base64
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import google.generativeai as genai

from src.core.gemini_client import GeminiModel


# Prompt designed for Mexican fiscal documents
EXTRACTION_PROMPT = """Analiza esta imagen de un documento fiscal mexicano (factura, recibo, ticket, CFDI, o nota de venta).

Extrae los siguientes campos con precisión. Si un campo no es visible o legible, usa null.

Responde ÚNICAMENTE con un JSON válido, sin markdown, sin explicaciones:

{
  "fecha": "YYYY-MM-DD",
  "rfc_emisor": "RFC de quien emite (12 o 13 caracteres)",
  "rfc_receptor": "RFC de quien recibe",
  "razon_social_emisor": "Nombre o razón social del emisor",
  "concepto": "Descripción breve del bien o servicio",
  "subtotal": 0.00,
  "iva": 0.00,
  "total": 0.00,
  "moneda": "MXN",
  "metodo_pago": "PUE o PPD si visible",
  "uso_cfdi": "Clave de uso CFDI si visible (ej: G03, D01)",
  "folio_fiscal": "UUID del CFDI si visible",
  "tipo_comprobante": "Ingreso | Egreso | Traslado | Pago",
  "deducible": true,
  "categoria_fiscal": "Gastos Médicos | Honorarios | Gastos Generales | Inversiones | No Deducible",
  "notas": "Observaciones relevantes para el doctor"
}

REGLAS DE CLASIFICACIÓN FISCAL (LISR):
- Material médico, instrumental, equipo → "Gastos Médicos" (Deducible)
- Renta de consultorio, servicios profesionales → "Honorarios" (Deducible)
- Gasolina, papelería, servicios → "Gastos Generales" (Deducible si es indispensable)
- Equipo de cómputo, mobiliario > $5,000 → "Inversiones" (Depreciación)
- Alimentos, ropa personal, entretenimiento → "No Deducible" (excepto viáticos con tarjeta fuera de 50km)
"""


@dataclass
class ReceiptData:
    """Structured data extracted from a fiscal document."""
    fecha: Optional[str] = None
    rfc_emisor: Optional[str] = None
    rfc_receptor: Optional[str] = None
    razon_social_emisor: Optional[str] = None
    concepto: Optional[str] = None
    subtotal: Optional[float] = None
    iva: Optional[float] = None
    total: Optional[float] = None
    moneda: str = "MXN"
    metodo_pago: Optional[str] = None
    uso_cfdi: Optional[str] = None
    folio_fiscal: Optional[str] = None
    tipo_comprobante: Optional[str] = None
    deducible: Optional[bool] = None
    categoria_fiscal: Optional[str] = None
    notas: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        """One-line summary for WhatsApp response."""
        status = "Deducible" if self.deducible else "No Deducible"
        return (
            f"{self.fecha} | {self.razon_social_emisor or 'N/A'} | "
            f"${self.total or 0:,.2f} {self.moneda} | "
            f"{self.categoria_fiscal or 'Sin clasificar'} | {status}"
        )


def _encode_image(image_path: Path) -> dict:
    """Encode an image file for the Gemini Vision API."""
    suffix = image_path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }
    mime_type = mime_map.get(suffix)
    if not mime_type:
        raise ValueError(f"Unsupported image format: {suffix}. Use JPG, PNG, WEBP, or PDF.")

    image_bytes = image_path.read_bytes()
    return {
        "mime_type": mime_type,
        "data": base64.b64encode(image_bytes).decode("utf-8"),
    }


def _parse_response(text: str) -> ReceiptData:
    """Parse the Gemini JSON response into a ReceiptData object."""
    # Strip markdown code fences if Gemini wraps the response
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]  # remove first line
        cleaned = cleaned.rsplit("```", 1)[0]  # remove last fence
    cleaned = cleaned.strip()

    data = json.loads(cleaned)
    return ReceiptData(**data)


def analyze_receipt(
    image_path: str | Path,
    model: GeminiModel = GeminiModel.FLASH,
) -> ReceiptData:
    """Analyze a receipt/invoice image and extract structured fiscal data.

    Args:
        image_path: Path to the image file (JPG, PNG, WEBP, or PDF).
        model: Gemini model to use. Flash for speed, Pro for complex documents.

    Returns:
        ReceiptData with all extracted fields.

    Raises:
        FileNotFoundError: If the image file doesn't exist.
        ValueError: If the image format is unsupported.
        json.JSONDecodeError: If Gemini returns invalid JSON.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    image_data = _encode_image(path)

    vision_model = genai.GenerativeModel(
        model_name=model.value,
        generation_config=genai.GenerationConfig(
            temperature=0.1,  # Near-zero for maximum extraction precision
            max_output_tokens=1024,
        ),
    )

    response = vision_model.generate_content([
        EXTRACTION_PROMPT,
        {"inline_data": image_data},
    ])

    return _parse_response(response.text)


def analyze_receipt_bytes(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    model: GeminiModel = GeminiModel.FLASH,
) -> ReceiptData:
    """Analyze a receipt from raw bytes (for WhatsApp media downloads).

    Args:
        image_bytes: Raw image bytes.
        mime_type: MIME type of the image.
        model: Gemini model to use.

    Returns:
        ReceiptData with all extracted fields.
    """
    image_data = {
        "mime_type": mime_type,
        "data": base64.b64encode(image_bytes).decode("utf-8"),
    }

    vision_model = genai.GenerativeModel(
        model_name=model.value,
        generation_config=genai.GenerationConfig(
            temperature=0.1,
            max_output_tokens=1024,
        ),
    )

    response = vision_model.generate_content([
        EXTRACTION_PROMPT,
        {"inline_data": image_data},
    ])

    return _parse_response(response.text)
