"""OpenDoc - RFC Validator (Registro Federal de Contribuyentes).

Validates Mexican RFC strings using the official SAT algorithm:
1. Format validation (pattern matching)
2. Check digit (dígito verificador) algorithm
3. Date validation (embedded YYMMDD)
4. Classification (Persona Física vs Persona Moral)

RFC Format:
- Persona Física (PF): 4 letters + 6 digits (YYMMDD) + 3 homoclave = 13 chars
- Persona Moral (PM): 3 letters + 6 digits (YYMMDD) + 3 homoclave = 12 chars

The check digit algorithm uses modular arithmetic with the SAT's character-to-number
mapping and a specific divisor (11).

Based on: CFF Art. 27, Anexo 1 RMF 2026, SAT CURP-RFC specification.
"""

import re
from dataclasses import dataclass
from typing import Optional
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────

class TipoPersona(str, Enum):
    """Type of taxpayer."""
    FISICA = "Persona Física"
    MORAL = "Persona Moral"


class ResultadoRFC(str, Enum):
    """RFC validation result status."""
    VALIDO = "Válido"
    INVALIDO = "Inválido"
    GENERICO = "Genérico"          # XAXX010101000, XEXX010101000


# ─── Generic RFCs ────────────────────────────────────────────────────

# SAT-defined generic RFCs for special cases
RFC_GENERICO_NACIONAL = "XAXX010101000"    # Público en general (nacional)
RFC_GENERICO_EXTRANJERO = "XEXX010101000"  # Operaciones con extranjeros

RFCS_GENERICOS = {RFC_GENERICO_NACIONAL, RFC_GENERICO_EXTRANJERO}


# ─── SAT Character Mapping ──────────────────────────────────────────
# Official SAT mapping for check digit calculation.
# Maps each valid character to its numeric value.

_CHAR_VALUES = {
    "0": 0,  "1": 1,  "2": 2,  "3": 3,  "4": 4,
    "5": 5,  "6": 6,  "7": 7,  "8": 8,  "9": 9,
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14,
    "F": 15, "G": 16, "H": 17, "I": 18, "J": 19,
    "K": 20, "L": 21, "M": 22, "N": 23, "&": 24,
    "O": 25, "P": 26, "Q": 27, "R": 28, "S": 29,
    "T": 30, "U": 31, "V": 32, "W": 33, "X": 34,
    "Y": 35, "Z": 36, " ": 37, "Ñ": 38,
}

# Reverse: check digit number → character
_DIGIT_MAP = "0123456789A"


# ─── Data Class ──────────────────────────────────────────────────────

@dataclass
class ValidacionRFC:
    """Result of RFC validation."""
    rfc: str
    es_valido: bool
    estatus: str                    # ResultadoRFC value
    tipo_persona: str = ""          # TipoPersona value
    digito_esperado: str = ""       # Expected check digit
    digito_encontrado: str = ""     # Actual check digit
    errores: list = None
    fecha_nacimiento: str = ""      # Extracted YYMMDD as date string
    nombre_parcial: str = ""        # Extracted name portion

    def __post_init__(self):
        if self.errores is None:
            self.errores = []

    def resumen_whatsapp(self) -> str:
        """WhatsApp-friendly validation summary."""
        if self.estatus == ResultadoRFC.GENERICO.value:
            return (
                f"━━━ RFC GENÉRICO ━━━\n"
                f"📋 {self.rfc}\n"
                f"ℹ️ RFC genérico del SAT (público en general / extranjeros)"
            )

        icon = "✅" if self.es_valido else "❌"
        lines = [
            f"━━━ VALIDACIÓN RFC ━━━",
            f"{icon} {self.rfc} — {self.estatus}",
        ]
        if self.tipo_persona:
            lines.append(f"👤 {self.tipo_persona}")
        if self.fecha_nacimiento:
            lines.append(f"📅 Fecha constitución: {self.fecha_nacimiento}")

        if self.errores:
            lines.append("")
            for e in self.errores:
                lines.append(f"🚨 {e}")

        if self.es_valido and self.digito_esperado:
            lines.append(f"🔐 Dígito verificador: {self.digito_esperado} ✓")

        return "\n".join(lines)


# ─── Patterns ────────────────────────────────────────────────────────

# Persona Física: 4 letters + 6 digits + 3 alphanum
_RE_PF = re.compile(
    r"^[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}$"
)

# Persona Moral: 3 letters + 6 digits + 3 alphanum
_RE_PM = re.compile(
    r"^[A-ZÑ&]{3}\d{6}[A-Z0-9]{3}$"
)


# ─── Check Digit Algorithm ──────────────────────────────────────────

def _calculate_check_digit(rfc_12: str) -> str:
    """Calculate the check digit (dígito verificador) for an RFC.

    Uses the official SAT algorithm:
    1. Pad Persona Moral RFCs (12 chars) with a leading space to get 12 chars
    2. Map each character to its numeric value
    3. Multiply each value by its positional weight (13, 12, 11, ... 2)
    4. Sum all products
    5. Remainder = sum % 11
    6. Check digit = 11 - remainder (with special cases for 0 and 10)

    Args:
        rfc_12: First 12 characters of RFC (without check digit).
                For PM (11 chars), a leading space is prepended.

    Returns:
        Single character: the expected check digit (0-9 or 'A').
    """
    # Normalize: PM has 11 chars before check digit, pad to 12
    if len(rfc_12) == 11:
        rfc_12 = " " + rfc_12

    if len(rfc_12) != 12:
        return "?"

    # Map characters to values and multiply by positional weights
    total = 0
    for i, char in enumerate(rfc_12):
        value = _CHAR_VALUES.get(char.upper())
        if value is None:
            return "?"
        weight = 13 - i  # Weights: 13, 12, 11, ..., 2
        total += value * weight

    remainder = total % 11

    if remainder == 0:
        return "0"
    else:
        digit_value = 11 - remainder
        if digit_value == 10:
            return "A"
        return str(digit_value)


# ─── Date Validation ─────────────────────────────────────────────────

def _validate_rfc_date(date_str: str) -> tuple:
    """Validate the YYMMDD portion of an RFC.

    Args:
        date_str: 6-digit string (YYMMDD)

    Returns:
        (is_valid: bool, formatted_date: str, error: str)
    """
    if len(date_str) != 6 or not date_str.isdigit():
        return False, "", "Fecha no válida en RFC"

    yy = int(date_str[:2])
    mm = int(date_str[2:4])
    dd = int(date_str[4:6])

    # Month validation
    if mm < 1 or mm > 12:
        return False, "", f"Mes inválido: {mm:02d}"

    # Day validation (approximate — allows 29 for all months)
    max_days = {
        1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
        7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31,
    }
    if dd < 1 or dd > max_days.get(mm, 31):
        return False, "", f"Día inválido: {dd:02d} para mes {mm:02d}"

    # Year: RFC uses 2-digit year. Assume 00-30 = 2000s, 31-99 = 1900s
    full_year = 2000 + yy if yy <= 30 else 1900 + yy
    formatted = f"{full_year}-{mm:02d}-{dd:02d}"

    return True, formatted, ""


# ─── Main Validation Function ───────────────────────────────────────

def validate_rfc(rfc: str) -> ValidacionRFC:
    """Validate a Mexican RFC string.

    Performs:
    1. Length check (12 for PM, 13 for PF)
    2. Format pattern matching
    3. Date validation (embedded YYMMDD)
    4. Check digit verification (SAT algorithm)

    Args:
        rfc: RFC string to validate (e.g., "GALM850101ABC")

    Returns:
        ValidacionRFC with full validation results.
    """
    errores = []

    # Clean input
    rfc_clean = rfc.strip().upper()

    # Check for generic RFCs
    if rfc_clean in RFCS_GENERICOS:
        return ValidacionRFC(
            rfc=rfc_clean,
            es_valido=True,
            estatus=ResultadoRFC.GENERICO.value,
            tipo_persona="Genérico SAT",
        )

    # Length check
    if len(rfc_clean) == 13:
        tipo = TipoPersona.FISICA
        name_part = rfc_clean[:4]
        date_part = rfc_clean[4:10]
        homoclave = rfc_clean[10:13]
    elif len(rfc_clean) == 12:
        tipo = TipoPersona.MORAL
        name_part = rfc_clean[:3]
        date_part = rfc_clean[3:9]
        homoclave = rfc_clean[9:12]
    else:
        errores.append(
            f"Longitud incorrecta: {len(rfc_clean)} caracteres "
            f"(esperado 12 para PM o 13 para PF)"
        )
        return ValidacionRFC(
            rfc=rfc_clean,
            es_valido=False,
            estatus=ResultadoRFC.INVALIDO.value,
            errores=errores,
        )

    # Pattern check
    if tipo == TipoPersona.FISICA:
        if not _RE_PF.match(rfc_clean):
            errores.append(
                "Formato inválido para Persona Física. "
                "Esperado: 4 letras + 6 dígitos + 3 caracteres alfanuméricos"
            )
    else:
        if not _RE_PM.match(rfc_clean):
            errores.append(
                "Formato inválido para Persona Moral. "
                "Esperado: 3 letras + 6 dígitos + 3 caracteres alfanuméricos"
            )

    # Date validation
    date_valid, fecha_formatted, date_error = _validate_rfc_date(date_part)
    if not date_valid:
        errores.append(date_error)

    # Check digit
    rfc_without_check = rfc_clean[:-1]
    check_found = rfc_clean[-1]
    check_expected = _calculate_check_digit(rfc_without_check)

    if check_expected == "?":
        errores.append("No se pudo calcular dígito verificador (caracteres inválidos)")
    elif check_found != check_expected:
        errores.append(
            f"Dígito verificador incorrecto: encontrado '{check_found}', "
            f"esperado '{check_expected}'"
        )

    es_valido = len(errores) == 0

    return ValidacionRFC(
        rfc=rfc_clean,
        es_valido=es_valido,
        estatus=ResultadoRFC.VALIDO.value if es_valido else ResultadoRFC.INVALIDO.value,
        tipo_persona=tipo.value,
        digito_esperado=check_expected if check_expected != "?" else "",
        digito_encontrado=check_found,
        errores=errores,
        fecha_nacimiento=fecha_formatted,
        nombre_parcial=name_part,
    )


def validate_rfc_batch(rfcs: list) -> list:
    """Validate a list of RFCs.

    Args:
        rfcs: List of RFC strings.

    Returns:
        List of ValidacionRFC results.
    """
    return [validate_rfc(rfc) for rfc in rfcs]


def is_valid_rfc(rfc: str) -> bool:
    """Quick check if RFC is valid.

    Args:
        rfc: RFC string.

    Returns:
        True if RFC passes all validations.
    """
    return validate_rfc(rfc).es_valido


def classify_rfc(rfc: str) -> str:
    """Classify an RFC as PF, PM, or Generic.

    Args:
        rfc: RFC string.

    Returns:
        TipoPersona value or "Genérico SAT" or "Inválido".
    """
    result = validate_rfc(rfc)
    if result.estatus == ResultadoRFC.GENERICO.value:
        return "Genérico SAT"
    if result.es_valido:
        return result.tipo_persona
    return "Inválido"
