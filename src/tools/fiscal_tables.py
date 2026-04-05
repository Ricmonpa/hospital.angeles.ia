"""OpenDoc - Centralized Fiscal Tables 2026.

Single source of truth for all Mexican tax constants, tariffs, and rates.
Updated annually when INEGI publishes new UMA values and SAT updates tariffs.

To upgrade to 2027: edit ONLY this file. All other modules import from here.

Sources:
- LISR 2026 (Art. 96, 113-E, 113-F, 152)
- LIVA 2026 (Art. 1, 1-C, 2-A)
- Ley del Seguro Social 2026
- INEGI UMA 2026 (DOF publicación enero 2026)
- RMF 2026 (Resolución Miscelánea Fiscal)
"""


# ─── Fiscal Year ──────────────────────────────────────────────────────

EJERCICIO_FISCAL = 2026


# ─── UMA (Unidad de Medida y Actualización) ──────────────────────────
# Published by INEGI each January. Base for IMSS, deductions, fines.

UMA_DIARIA_2026 = 113.14        # Approximate — updated annually by INEGI
UMA_MENSUAL_2026 = UMA_DIARIA_2026 * 30.4
UMA_ANUAL_2026 = UMA_DIARIA_2026 * 365   # = 41,296.10


# ─── Salario Mínimo ──────────────────────────────────────────────────

SALARIO_MINIMO_DIARIO_2026 = 278.80       # Zona general
SALARIO_MINIMO_MENSUAL_2026 = SALARIO_MINIMO_DIARIO_2026 * 30.4


# ─── ISR Monthly Tariff (Art. 96 LISR — Personas Físicas) ────────────
# Used by: monthly_tax_calculator, payroll_calculator, deduction_optimizer

TARIFA_ISR_MENSUAL = [
    # (limite_inferior, limite_superior, cuota_fija, tasa_marginal %)
    (0.01, 746.04, 0.00, 1.92),
    (746.05, 6_332.05, 14.32, 6.40),
    (6_332.06, 11_128.01, 371.83, 10.88),
    (11_128.02, 12_935.82, 893.63, 16.00),
    (12_935.83, 15_487.71, 1_182.88, 17.92),
    (15_487.72, 31_236.49, 1_639.32, 21.36),
    (31_236.50, 49_233.00, 4_005.14, 23.52),
    (49_233.01, 93_993.90, 8_233.40, 30.00),
    (93_993.91, 125_325.20, 21_661.67, 32.00),
    (125_325.21, 375_975.61, 31_667.70, 34.00),
    (375_975.62, float("inf"), 116_888.72, 35.00),
]


# ─── RESICO Monthly Tariff (Art. 113-E LISR) ─────────────────────────
# Used by: monthly_tax_calculator, deduction_optimizer

TARIFA_RESICO_MENSUAL = [
    # (limite_inferior, limite_superior, tasa_fija %)
    (0.01, 25_000.00, 1.00),
    (25_000.01, 50_000.00, 1.10),
    (50_000.01, 83_333.33, 1.50),
    (83_333.34, 208_333.33, 2.00),
    (208_333.34, 291_666.67, 2.50),
]


# ─── ISR Annual Tariff (Art. 152 LISR) ───────────────────────────────
# Used by: annual_tax_calculator

TARIFA_ISR_ANUAL = [
    # (limite_inferior, limite_superior, cuota_fija, tasa_marginal %)
    (0.01, 8_952.49, 0.00, 1.92),
    (8_952.50, 75_984.55, 171.88, 6.40),
    (75_984.56, 133_536.07, 4_461.94, 10.88),
    (133_536.08, 155_229.80, 10_723.55, 16.00),
    (155_229.81, 185_852.57, 14_194.54, 17.92),
    (185_852.58, 374_837.88, 19_682.13, 21.36),
    (374_837.89, 590_795.99, 48_061.74, 23.52),
    (590_796.00, 1_127_926.84, 98_867.70, 30.00),
    (1_127_926.85, 1_503_902.46, 260_107.00, 32.00),
    (1_503_902.47, 4_511_707.37, 380_322.76, 34.00),
    (4_511_707.38, float("inf"), 1_402_976.52, 35.00),
]


# ─── RESICO Annual Tariff (Art. 113-F LISR) ──────────────────────────
# Used by: annual_tax_calculator

TARIFA_RESICO_ANUAL = [
    # (limite_inferior, limite_superior, tasa_fija %)
    (0.01, 300_000.00, 1.00),
    (300_000.01, 600_000.00, 1.10),
    (600_000.01, 1_000_000.00, 1.50),
    (1_000_000.01, 2_500_000.00, 2.00),
    (2_500_000.01, 3_500_000.00, 2.50),
]


# ─── Subsidio al Empleo Mensual (Art. 10 transitorio) ────────────────
# Used by: payroll_calculator

SUBSIDIO_EMPLEO_MENSUAL = [
    # (limite_inferior, limite_superior, subsidio)
    (0.01, 1_768.96, 407.02),
    (1_768.97, 2_653.38, 406.83),
    (2_653.39, 3_472.84, 406.62),
    (3_472.85, 3_537.87, 392.77),
    (3_537.88, 4_446.15, 382.46),
    (4_446.16, 4_717.18, 354.23),
    (4_717.19, 5_335.42, 324.87),
    (5_335.43, 6_224.67, 294.63),
    (6_224.68, 7_113.90, 253.54),
    (7_113.91, 7_382.33, 217.61),
    (7_382.34, float("inf"), 0.00),
]


# ─── IVA Rates (Art. 1, 1-C, 2-A LIVA) ──────────────────────────────
# Used by: monthly_tax_calculator

IVA_TASA_GENERAL = 0.16
IVA_TASA_FRONTERA = 0.08
IVA_TASA_CERO = 0.00


# ─── State Tax (Impuesto Cedular — Guanajuato model) ─────────────────
# Used by: monthly_tax_calculator

CEDULAR_TASA_GTO = 0.02  # 2% sobre utilidad


# ─── Personal Deduction Limits ────────────────────────────────────────
# Used by: annual_tax_calculator

TOPE_DEDUCCIONES_PERSONALES_UMAS = 5
# Max personal deduction = min(15% of income, 5 × UMA_ANUAL)
TOPE_DEDUCCIONES_PERSONALES_PCT = 0.15


# ─── RESICO Limits ───────────────────────────────────────────────────

RESICO_TOPE_INGRESOS = 3_500_000.00


# ─── IMSS Topes ──────────────────────────────────────────────────────
# Used by: payroll_calculator

TOPE_SBC_25_UMA = UMA_DIARIA_2026 * 25   # Tope cotización IMSS


# ─── INFONAVIT / SAR ────────────────────────────────────────────────

INFONAVIT_TASA_PATRONAL = 0.05  # 5% sobre SBC
SAR_TASA_PATRONAL = 0.02        # 2% sobre SBC


# ─── Payroll Tax (ISN — Guanajuato) ─────────────────────────────────

ISN_TASA_GTO = 0.03             # 3% sobre nómina gravable


# ─── Retenciones ────────────────────────────────────────────────────

RETENCION_ISR_PM = 0.10         # 10% ISR retention from Personas Morales
RETENCION_IVA_PM = 0.1067       # 10.6667% IVA retention (2/3 del 16%)


# ─── Convenience Aliases ─────────────────────────────────────────────
# For backward compatibility with existing code

UMA_ANUAL_REAL_2026 = UMA_ANUAL_2026  # Used by annual_tax_calculator
