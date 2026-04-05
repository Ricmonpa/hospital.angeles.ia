"""Tests for CFDI XML Parser — using real SAT invoice data."""

import pytest
from pathlib import Path

from src.tools.cfdi_parser import (
    parse_cfdi,
    parse_cfdi_string,
    CFDI,
    ConceptoCFDI,
    REGIMEN_FISCAL,
    USO_CFDI,
    TIPO_COMPROBANTE,
    FORMA_PAGO,
)


# Path to the real CFDI provided by the user
# Works both locally and inside Docker (via volume mount)
REAL_XML = Path(__file__).parent.parent / "data" / "templates" / "MOPR881228EF9FF22.xml"


class TestRealCFDI:
    """Tests against the real CFDI 3.3 XML from Ricardo Moncada."""

    @pytest.fixture
    def cfdi(self):
        assert REAL_XML.exists(), f"Real XML not found: {REAL_XML}"
        return parse_cfdi(REAL_XML)

    def test_version(self, cfdi):
        assert cfdi.version == "3.3"

    def test_folio(self, cfdi):
        assert cfdi.folio == "22"

    def test_fecha(self, cfdi):
        assert cfdi.fecha.startswith("2022-01-18")
        assert cfdi.fecha_dt is not None
        assert cfdi.fecha_dt.year == 2022
        assert cfdi.fecha_dt.month == 1

    def test_emisor(self, cfdi):
        assert cfdi.emisor_rfc == "MOPR881228EF9"
        assert "MONCADA" in cfdi.emisor_nombre.upper()
        assert cfdi.emisor_regimen == "612"
        assert "Empresariales" in cfdi.emisor_regimen_desc

    def test_receptor(self, cfdi):
        assert cfdi.receptor_rfc == "IIC200908QY6"
        assert "Innovación" in cfdi.receptor_nombre
        assert cfdi.receptor_uso_cfdi == "G03"
        assert "Gastos en general" in cfdi.receptor_uso_cfdi_desc

    def test_amounts(self, cfdi):
        assert cfdi.subtotal == 150_000.00
        assert cfdi.total == 150_000.00
        assert cfdi.moneda == "MXN"

    def test_payment(self, cfdi):
        assert cfdi.forma_pago == "03"
        assert "Transferencia" in cfdi.forma_pago_desc
        assert cfdi.metodo_pago == "PUE"

    def test_tipo_comprobante(self, cfdi):
        assert cfdi.tipo_comprobante == "I"
        assert cfdi.tipo_comprobante_desc == "Ingreso"

    def test_iva_exento(self, cfdi):
        assert cfdi.exento_iva is True
        assert cfdi.iva_trasladado == 0.0

    def test_conceptos(self, cfdi):
        assert len(cfdi.conceptos) == 1
        c = cfdi.conceptos[0]
        assert c.clave_prod_serv == "93151611"
        assert c.cantidad == 1.0
        assert c.clave_unidad == "E48"
        assert c.importe == 150_000.00
        assert "YOPETT" in c.descripcion
        assert c.exento is True

    def test_timbre_fiscal(self, cfdi):
        assert cfdi.timbre is not None
        assert cfdi.timbre.uuid == "C0172468-3CC7-4CA7-A5CD-C7A0E2CEA35D"
        assert cfdi.timbre.fecha_timbrado.startswith("2022-01-18")
        assert cfdi.timbre.rfc_prov_certif == "TSP080724QW6"

    def test_lugar_expedicion(self, cfdi):
        assert cfdi.lugar_expedicion == "37297"

    def test_impuestos_locales(self, cfdi):
        assert cfdi.impuestos_locales_traslados == 0.0
        assert cfdi.impuestos_locales_retenciones == 0.0

    def test_summary(self, cfdi):
        s = cfdi.summary()
        assert "MONCADA" in s.upper()
        assert "150,000.00" in s
        assert "Ingreso" in s

    def test_fiscal_summary(self, cfdi):
        fs = cfdi.fiscal_summary()
        assert "CFDI 3.3" in fs
        assert "MOPR881228EF9" in fs
        assert "IIC200908QY6" in fs
        assert "EXENTO" in fs
        assert "150,000.00" in fs

    def test_neto_a_cobrar(self, cfdi):
        # No retentions, so neto = total
        assert cfdi.neto_a_cobrar == 150_000.00


class TestCatalogos:
    """Test SAT catalogs are properly loaded."""

    def test_regimen_612(self):
        assert "612" in REGIMEN_FISCAL
        assert "Empresariales" in REGIMEN_FISCAL["612"]

    def test_regimen_625(self):
        assert "625" in REGIMEN_FISCAL
        assert "RESICO" in REGIMEN_FISCAL["625"]

    def test_uso_cfdi_d01(self):
        assert "D01" in USO_CFDI
        assert "médicos" in USO_CFDI["D01"]

    def test_uso_cfdi_g03(self):
        assert "G03" in USO_CFDI
        assert "Gastos en general" in USO_CFDI["G03"]

    def test_tipo_comprobante(self):
        assert TIPO_COMPROBANTE["I"] == "Ingreso"
        assert TIPO_COMPROBANTE["E"] == "Egreso"
        assert TIPO_COMPROBANTE["P"] == "Pago"

    def test_forma_pago_03(self):
        assert "Transferencia" in FORMA_PAGO["03"]

    def test_forma_pago_04(self):
        assert "crédito" in FORMA_PAGO["04"]


class TestEdgeCases:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_cfdi("/nonexistent/file.xml")

    def test_to_dict(self):
        if REAL_XML.exists():
            cfdi = parse_cfdi(REAL_XML)
            d = cfdi.to_dict()
            assert isinstance(d, dict)
            assert d["emisor_rfc"] == "MOPR881228EF9"
            assert "fecha_dt" not in d
