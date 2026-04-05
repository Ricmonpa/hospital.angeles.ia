"""Integration test: Generate test invoice → Gemini Vision → Verify extraction.

Run: python -m tests.test_vision_integration

Requires: GOOGLE_API_KEY in .env
"""

import os
import sys

import google.generativeai as genai
from dotenv import load_dotenv

from tests.generate_test_invoice import generate_invoice
from src.tools.receipt_vision_analyzer import analyze_receipt

load_dotenv()


def main():
    # 1. Configure API
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[ERROR] GOOGLE_API_KEY not set. Check your .env file.")
        sys.exit(1)
    genai.configure(api_key=api_key)
    print("[OpenDoc] API key configured.")

    # 2. Generate test invoice
    print("[OpenDoc] Generating test invoice...")
    invoice_path = generate_invoice()

    # 3. Analyze with Gemini Vision
    print(f"[OpenDoc] Sending {invoice_path.name} to Gemini Vision (Flash)...")
    result = analyze_receipt(invoice_path)

    # 4. Display results
    print("\n" + "=" * 60)
    print("  RECEIPT VISION ANALYZER - RESULTS")
    print("=" * 60)
    print(f"  Fecha:           {result.fecha}")
    print(f"  RFC Emisor:      {result.rfc_emisor}")
    print(f"  RFC Receptor:    {result.rfc_receptor}")
    print(f"  Razón Social:    {result.razon_social_emisor}")
    print(f"  Concepto:        {result.concepto}")
    print(f"  Subtotal:        ${result.subtotal:,.2f}" if result.subtotal else "  Subtotal:        N/A")
    print(f"  IVA:             ${result.iva:,.2f}" if result.iva else "  IVA:             N/A")
    print(f"  Total:           ${result.total:,.2f}" if result.total else "  Total:           N/A")
    print(f"  Método Pago:     {result.metodo_pago}")
    print(f"  Uso CFDI:        {result.uso_cfdi}")
    print(f"  Folio Fiscal:    {result.folio_fiscal}")
    print(f"  Tipo:            {result.tipo_comprobante}")
    print(f"  Categoría:       {result.categoria_fiscal}")
    print(f"  Deducible:       {'SI' if result.deducible else 'NO'}")
    print(f"  Notas:           {result.notas}")
    print("=" * 60)
    print(f"\n  WhatsApp Summary: {result.summary()}")
    print("=" * 60)

    # 5. Validate critical fields
    errors = []
    if result.total is None:
        errors.append("Total not extracted")
    if result.rfc_emisor is None:
        errors.append("RFC Emisor not extracted")
    if result.fecha is None:
        errors.append("Fecha not extracted")
    if result.deducible is None:
        errors.append("Deductibility not classified")

    if errors:
        print(f"\n[WARNING] Missing fields: {', '.join(errors)}")
        sys.exit(1)
    else:
        print("\n[OpenDoc] Phase 3 PASSED. All critical fields extracted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
