"""Generate a realistic Mexican test invoice (CFDI) image for Gemini Vision testing.

Run: python -m tests.generate_test_invoice
Creates: data/templates/test_factura.png
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT_PATH = Path(__file__).parent.parent / "data" / "templates" / "test_factura.png"


def generate_invoice():
    """Create a synthetic Mexican CFDI-like invoice image."""

    W, H = 800, 1100
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    # Use default font (available everywhere)
    try:
        font_title = ImageFont.truetype("arial.ttf", 22)
        font_header = ImageFont.truetype("arial.ttf", 16)
        font_body = ImageFont.truetype("arial.ttf", 13)
        font_small = ImageFont.truetype("arial.ttf", 11)
    except OSError:
        font_title = ImageFont.load_default()
        font_header = font_title
        font_body = font_title
        font_small = font_title

    y = 30

    # Header - Company info
    draw.rectangle([20, 20, W - 20, 160], outline="black", width=2)
    draw.text((40, y), "DISTRIBUIDORA MEDICA DEL NORTE", fill="navy", font=font_title)
    y += 30
    draw.text((40, y), "SA DE CV", fill="navy", font=font_header)
    y += 25
    draw.text((40, y), "RFC: DMN200315AB9", fill="black", font=font_body)
    y += 20
    draw.text((40, y), "Av. Constitución 1502, Col. Centro", fill="gray", font=font_small)
    y += 16
    draw.text((40, y), "Monterrey, Nuevo León, C.P. 64000", fill="gray", font=font_small)
    y += 16
    draw.text((40, y), "Tel: (81) 8374-5500", fill="gray", font=font_small)

    # CFDI Badge
    draw.rectangle([550, 30, W - 30, 100], fill="navy")
    draw.text((570, 40), "CFDI 4.0", fill="white", font=font_title)
    draw.text((570, 70), "FACTURA", fill="white", font=font_header)

    # Folio & Date
    y = 180
    draw.text((40, y), "Folio Fiscal (UUID):", fill="black", font=font_header)
    draw.text((220, y), "A1B2C3D4-E5F6-7890-ABCD-EF1234567890", fill="navy", font=font_body)
    y += 25
    draw.text((40, y), "Fecha de Emisión:", fill="black", font=font_header)
    draw.text((220, y), "2025-03-15T10:30:00", fill="black", font=font_body)
    y += 25
    draw.text((40, y), "Lugar de Expedición:", fill="black", font=font_header)
    draw.text((220, y), "64000", fill="black", font=font_body)

    # Receptor info
    y += 40
    draw.rectangle([20, y, W - 20, y + 100], outline="gray", width=1)
    draw.text((40, y + 10), "DATOS DEL RECEPTOR", fill="navy", font=font_header)
    draw.text((40, y + 35), "RFC: GARJ850101HDF", fill="black", font=font_body)
    draw.text((40, y + 55), "Dr. Juan García Ramírez", fill="black", font=font_body)
    draw.text((40, y + 75), "Uso CFDI: D01 - Honorarios médicos, dentales y gastos hospitalarios",
              fill="black", font=font_small)

    # Concepts table
    y += 120
    # Table header
    draw.rectangle([20, y, W - 20, y + 30], fill="navy")
    cols = [40, 100, 400, 530, 660]
    headers = ["Cant.", "Clave SAT", "Descripción", "P. Unitario", "Importe"]
    for col, header in zip(cols, headers):
        draw.text((col, y + 7), header, fill="white", font=font_body)

    # Row 1
    y += 30
    draw.rectangle([20, y, W - 20, y + 35], outline="lightgray", width=1)
    row1 = ["5", "42142901", "Guantes de nitrilo caja x100 pzas", "$172.41", "$862.07"]
    for col, val in zip(cols, row1):
        draw.text((col, y + 10), val, fill="black", font=font_body)

    # Row 2
    y += 35
    draw.rectangle([20, y, W - 20, y + 35], outline="lightgray", width=1)
    row2 = ["2", "42132201", "Cubrebocas N95 caja x50 pzas", "$129.31", "$258.62"]
    for col, val in zip(cols, row2):
        draw.text((col, y + 10), val, fill="black", font=font_body)

    # Totals
    y += 60
    draw.line([480, y, W - 30, y], fill="black", width=1)
    y += 10
    draw.text((500, y), "Subtotal:", fill="black", font=font_header)
    draw.text((650, y), "$1,120.69", fill="black", font=font_header)
    y += 25
    draw.text((500, y), "IVA (16%):", fill="black", font=font_header)
    draw.text((650, y), "$179.31", fill="black", font=font_header)
    y += 25
    draw.rectangle([490, y - 5, W - 20, y + 25], fill="navy")
    draw.text((500, y), "TOTAL:", fill="white", font=font_title)
    draw.text((640, y), "$1,300.00", fill="white", font=font_title)

    # Payment info
    y += 50
    draw.text((40, y), "Método de Pago: PUE - Pago en una sola exhibición",
              fill="black", font=font_body)
    y += 20
    draw.text((40, y), "Forma de Pago: 04 - Tarjeta de crédito",
              fill="black", font=font_body)
    y += 20
    draw.text((40, y), "Moneda: MXN - Peso Mexicano",
              fill="black", font=font_body)
    y += 20
    draw.text((40, y), "Tipo de Comprobante: I - Ingreso",
              fill="black", font=font_body)

    # QR Code placeholder
    y += 40
    draw.rectangle([40, y, 170, y + 130], outline="black", width=2)
    draw.text((60, y + 55), "QR CFDI", fill="gray", font=font_header)

    # Digital seal
    draw.text((190, y + 10), "Sello Digital del CFDI:", fill="black", font=font_small)
    draw.text((190, y + 28), "kA9B2mX8pQ3rT...||", fill="gray", font=font_small)
    draw.text((190, y + 46), "Sello del SAT:", fill="black", font=font_small)
    draw.text((190, y + 64), "Yw7Lm3Np5Kf8v...||", fill="gray", font=font_small)
    draw.text((190, y + 86), "Cadena Original del Timbre:", fill="black", font=font_small)
    draw.text((190, y + 104), "||1.1|A1B2C3D4-E5F6...|2025-03-15T10:30:00||",
              fill="gray", font=font_small)

    # Footer
    draw.line([20, H - 50, W - 20, H - 50], fill="gray", width=1)
    draw.text((40, H - 40), "Este documento es una representación impresa de un CFDI",
              fill="gray", font=font_small)

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(OUTPUT_PATH), "PNG", quality=95)
    print(f"[OpenDoc] Test invoice saved to: {OUTPUT_PATH}")
    return OUTPUT_PATH


if __name__ == "__main__":
    generate_invoice()
