"""Fiscal and SAT tools for Hospital Ángeles IA (Agente Contable)."""

from .fiscal_tables import (
    EJERCICIO_FISCAL,
    UMA_DIARIA_2026 as _UMA_D,  # also re-exported via payroll_calculator
    UMA_ANUAL_2026 as _UMA_A,
    RESICO_TOPE_INGRESOS,
)
from .rfc_validator import (
    validate_rfc,
    validate_rfc_batch,
    is_valid_rfc,
    classify_rfc,
    ValidacionRFC,
    TipoPersona,
    ResultadoRFC,
    RFC_GENERICO_NACIONAL,
    RFC_GENERICO_EXTRANJERO,
)
from .receipt_vision_analyzer import analyze_receipt, analyze_receipt_bytes, ReceiptData
from .cfdi_parser import (
    parse_cfdi,
    parse_cfdi_string,
    CFDI,
    CLAVES_MEDICAS_SAT,
    is_medical_service,
    get_medical_service_name,
)
from .fiscal_classifier import (
    classify_cfdi,
    classify_cfdi_offline,
    full_cfdi_analysis,
    ClasificacionFiscal,
    Deducibilidad,
    CategoriaFiscal,
)
from .sat_portal_navigator import (
    full_sat_navigation,
    navigate_cfdi_recibidos,
    navigate_cfdi_emitidos,
    navigate_constancia,
    navigate_buzon_tributario,
    process_downloaded_cfdis,
    SATSession,
    CFDIDownloadResult,
    ConstanciaSituacionFiscal,
    BuzonTributarioResult,
    SATPortalResult,
    SATReadOnlyViolation,
    SATSessionExpired,
    SATCaptchaDetected,
)
from .deduction_optimizer import (
    analyze_deduction,
    calculate_depreciation,
    validate_payment,
    compare_regimes,
    classify_expense_by_sat_code,
    calculate_personal_deduction_limit,
    calculate_isr_612_mensual,
    calculate_isr_resico_mensual,
    format_deduction_whatsapp,
    format_strategy_whatsapp,
    AnalisisDeduccion,
    DepreciacionAnual,
    ValidacionPago,
    EstrategiaAnual,
    TipoDeduccion,
    SubcategoriaGasto,
    TASAS_DEPRECIACION,
    SAT_CODE_DEDUCTION_MAP,
)
from .monthly_tax_calculator import (
    calculate_provisional_612,
    calculate_provisional_resico,
    calculate_annual_projection,
    IngresosMensuales,
    DeduccionesMensuales,
    IVAMensual,
    ResultadoProvisional,
    TARIFA_ISR_MENSUAL,
    TARIFA_RESICO_MENSUAL,
    IVA_TASA_GENERAL,
    CEDULAR_TASA_GTO,
)
from .diot_generator import (
    generate_diot,
    group_operations_by_rfc,
    create_operation_from_cfdi,
    OperacionTercero,
    ResumenTercero,
    ReporteDIOT,
    TipoTercero,
)
from .payroll_calculator import (
    calculate_payroll,
    calculate_employee_payroll,
    calculate_isr_withholding,
    calculate_imss_quotas,
    Empleado,
    NominaEmpleado,
    ResumenNomina,
    DesgloseCuotasIMSS,
    CUOTAS_IMSS,
    UMA_DIARIA_2026,
    SALARIO_MINIMO_DIARIO_2026,
    INFONAVIT_TASA_PATRONAL,
    ISN_TOTAL_GTO,
)
from .tax_calendar import (
    generate_monthly_calendar,
    generate_annual_calendar,
    get_upcoming_deadlines,
    get_overdue_obligations,
    format_monthly_calendar_whatsapp,
    format_upcoming_whatsapp,
    EventoCalendario,
    ObligacionFiscal,
    OBLIGACIONES_MENSUALES,
    OBLIGACIONES_BIMESTRALES,
    OBLIGACIONES_ANUALES,
)
from .annual_tax_calculator import (
    calculate_annual_612,
    calculate_annual_resico,
    compare_annual_regimes,
    IngresosAnuales,
    DeduccionesAnuales as DeduccionesAnualesDecl,
    DeduccionesPersonales,
    ResultadoAnual,
    TARIFA_ISR_ANUAL,
    TARIFA_RESICO_ANUAL,
)
from .cfdi_validator import (
    validate_cfdi,
    validate_cfdi_batch,
    ResultadoValidacion,
    ErrorCFDI,
    SeveridadError,
    TipoValidacion,
)
from .fiscal_alerts import (
    generate_fiscal_health_report,
    check_certificate_expiry,
    check_resico_income_cap,
    check_deduction_patterns,
    check_missing_filings,
    check_employee_compliance,
    AlertaFiscal,
    ReporteAlertas,
    NivelAlerta,
    CategoriaAlerta,
)
from .pdf_report_generator import (
    generate_monthly_pdf,
    generate_annual_pdf,
    generate_diot_pdf,
    generate_fiscal_health_pdf,
    generate_deduction_pdf,
    generate_pdf_report,
    ConfiguracionPDF,
    ResultadoPDF,
    TipoReporte,
)
from .depreciation_schedule import (
    generate_depreciation_schedule,
    generate_asset_registry,
    get_monthly_depreciation,
    ActivoFijo,
    LineaDepreciacion,
    TablaDepreciacion,
    ResumenRegistro,
)
from .fiscal_reconciliation import (
    reconcile_fiscal_year,
    quick_reconcile,
    NivelDiscrepancia,
    AreaReconciliacion,
    Discrepancia,
    MesConciliado,
    ResultadoConciliacion,
    MESES_NOMBRES,
)
from .sat_efirma import (
    load_certificate,
    load_private_key,
    validate_certificate_pair,
    generate_sat_auth_token,
    sign_soap_body,
    CertificadoInfo,
    EstadoCertificado,
    TipoCertificado,
    EFirmaPasswordError,
    EFirmaCertificateError,
    EFirmaExpiredError,
    EFirmaSigningError,
    EFirmaKeyMismatchError,
)
from .sat_ws_client import (
    authenticate as sat_ws_authenticate,
    solicitar_descarga,
    verificar_solicitud,
    descargar_paquete,
    descarga_masiva_completa,
    verificar_cfdi,
    preparar_cancelacion,
    ejecutar_cancelacion,
    download_cfdis_with_fallback,
    SATAuthToken,
    SolicitudDescarga,
    VerificacionCFDI,
    ResultadoCancelacion,
    DescargaMasivaResult,
    EstadoSolicitud,
    EstadoCFDI,
    EstadoCancelacion,
    SATWSAuthError,
    SATWSSolicitudError,
    SATWSDownloadError,
    SATWSCancelacionRequiresConfirmation,
    SATWSServiceUnavailable,
)
from .sat_audit_logger import (
    get_audit_logger,
    log_navigation_step,
    log_session_summary,
    export_audit_trail,
)

__all__ = [
    # Receipt Vision
    "analyze_receipt", "analyze_receipt_bytes", "ReceiptData",
    # CFDI Parser
    "parse_cfdi", "parse_cfdi_string", "CFDI",
    "CLAVES_MEDICAS_SAT", "is_medical_service", "get_medical_service_name",
    # Fiscal Classifier
    "classify_cfdi", "classify_cfdi_offline", "full_cfdi_analysis",
    "ClasificacionFiscal", "Deducibilidad", "CategoriaFiscal",
    # SAT Portal Navigator
    "full_sat_navigation", "navigate_cfdi_recibidos", "navigate_cfdi_emitidos",
    "navigate_constancia", "navigate_buzon_tributario", "process_downloaded_cfdis",
    "SATSession", "CFDIDownloadResult", "ConstanciaSituacionFiscal",
    "BuzonTributarioResult", "SATPortalResult",
    "SATReadOnlyViolation", "SATSessionExpired", "SATCaptchaDetected",
    # Deduction Optimizer
    "analyze_deduction", "calculate_depreciation", "validate_payment",
    "compare_regimes", "classify_expense_by_sat_code",
    "calculate_personal_deduction_limit",
    "calculate_isr_612_mensual", "calculate_isr_resico_mensual",
    "format_deduction_whatsapp", "format_strategy_whatsapp",
    "AnalisisDeduccion", "DepreciacionAnual", "ValidacionPago",
    "EstrategiaAnual", "TipoDeduccion", "SubcategoriaGasto",
    "TASAS_DEPRECIACION", "SAT_CODE_DEDUCTION_MAP",
    # Monthly Tax Calculator
    "calculate_provisional_612", "calculate_provisional_resico",
    "calculate_annual_projection",
    "IngresosMensuales", "DeduccionesMensuales", "IVAMensual",
    "ResultadoProvisional",
    "TARIFA_ISR_MENSUAL", "TARIFA_RESICO_MENSUAL",
    "IVA_TASA_GENERAL", "CEDULAR_TASA_GTO",
    # DIOT Generator
    "generate_diot", "group_operations_by_rfc", "create_operation_from_cfdi",
    "OperacionTercero", "ResumenTercero", "ReporteDIOT", "TipoTercero",
    # Payroll Calculator
    "calculate_payroll", "calculate_employee_payroll",
    "calculate_isr_withholding", "calculate_imss_quotas",
    "Empleado", "NominaEmpleado", "ResumenNomina", "DesgloseCuotasIMSS",
    "CUOTAS_IMSS", "UMA_DIARIA_2026", "SALARIO_MINIMO_DIARIO_2026",
    "INFONAVIT_TASA_PATRONAL", "ISN_TOTAL_GTO",
    # Tax Calendar
    "generate_monthly_calendar", "generate_annual_calendar",
    "get_upcoming_deadlines", "get_overdue_obligations",
    "format_monthly_calendar_whatsapp", "format_upcoming_whatsapp",
    "EventoCalendario", "ObligacionFiscal",
    "OBLIGACIONES_MENSUALES", "OBLIGACIONES_BIMESTRALES", "OBLIGACIONES_ANUALES",
    # Annual Tax Calculator
    "calculate_annual_612", "calculate_annual_resico", "compare_annual_regimes",
    "IngresosAnuales", "DeduccionesAnualesDecl", "DeduccionesPersonales",
    "ResultadoAnual", "TARIFA_ISR_ANUAL", "TARIFA_RESICO_ANUAL",
    # CFDI Validator
    "validate_cfdi", "validate_cfdi_batch",
    "ResultadoValidacion", "ErrorCFDI", "SeveridadError", "TipoValidacion",
    # Fiscal Alerts
    "generate_fiscal_health_report",
    "check_certificate_expiry", "check_resico_income_cap",
    "check_deduction_patterns", "check_missing_filings", "check_employee_compliance",
    "AlertaFiscal", "ReporteAlertas", "NivelAlerta", "CategoriaAlerta",
    # PDF Report Generator
    "generate_monthly_pdf", "generate_annual_pdf", "generate_diot_pdf",
    "generate_fiscal_health_pdf", "generate_deduction_pdf", "generate_pdf_report",
    "ConfiguracionPDF", "ResultadoPDF", "TipoReporte",
    # Fiscal Tables (centralized)
    "EJERCICIO_FISCAL", "RESICO_TOPE_INGRESOS",
    # RFC Validator
    "validate_rfc", "validate_rfc_batch", "is_valid_rfc", "classify_rfc",
    "ValidacionRFC", "TipoPersona", "ResultadoRFC",
    "RFC_GENERICO_NACIONAL", "RFC_GENERICO_EXTRANJERO",
    # Depreciation Schedule
    "generate_depreciation_schedule", "generate_asset_registry",
    "get_monthly_depreciation",
    "ActivoFijo", "LineaDepreciacion", "TablaDepreciacion", "ResumenRegistro",
    # Fiscal Reconciliation
    "reconcile_fiscal_year", "quick_reconcile",
    "NivelDiscrepancia", "AreaReconciliacion",
    "Discrepancia", "MesConciliado", "ResultadoConciliacion",
    "MESES_NOMBRES",
    # SAT e.firma
    "load_certificate", "load_private_key", "validate_certificate_pair",
    "generate_sat_auth_token", "sign_soap_body",
    "CertificadoInfo", "EstadoCertificado", "TipoCertificado",
    "EFirmaPasswordError", "EFirmaCertificateError",
    "EFirmaExpiredError", "EFirmaSigningError", "EFirmaKeyMismatchError",
    # SAT Web Services (SOAP)
    "sat_ws_authenticate", "solicitar_descarga", "verificar_solicitud",
    "descargar_paquete", "descarga_masiva_completa",
    "verificar_cfdi", "preparar_cancelacion", "ejecutar_cancelacion",
    "download_cfdis_with_fallback",
    "SATAuthToken", "SolicitudDescarga", "VerificacionCFDI",
    "ResultadoCancelacion", "DescargaMasivaResult",
    "EstadoSolicitud", "EstadoCFDI", "EstadoCancelacion",
    "SATWSAuthError", "SATWSSolicitudError", "SATWSDownloadError",
    "SATWSCancelacionRequiresConfirmation", "SATWSServiceUnavailable",
    # Audit Logger
    "get_audit_logger", "log_navigation_step", "log_session_summary",
    "export_audit_trail",
]
