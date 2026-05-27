# Standard libraries
from datetime import date
from decimal import Decimal
from pathlib import Path

# 3pps
import pytest

# Own modules
from degiro_tools import Operacion, TipoOperacion, parse_csv

FIXTURE = Path(__file__).parent / "fixtures" / "sample.csv"

EXPECTED_OPS_COUNT = 4
EXPECTED_EUR_COMPRA_CANTIDAD = 10
EXPECTED_USD_COMPRA_CANTIDAD = 10
EXPECTED_VENTA_CANTIDAD = 15

ParsedCsv = tuple[list[Operacion], Decimal]


@pytest.fixture(scope="module")
def parsed() -> ParsedCsv:
    """
    Parsea el CSV de fixture una vez por módulo y reutiliza el resultado.

    Returns:
        Tupla ``(ops, comisiones_conectividad)`` devuelta por ``parse_csv``.
    """

    return parse_csv(FIXTURE)


def test_parse_cuenta_operaciones(parsed: ParsedCsv) -> None:
    """
    Verifica que el parser detecta 4 operaciones (1 EUR + 2 USD compra + 1 venta).
    """

    ops, _ = parsed
    # 1 compra EUR directo + 2 compras USD + 1 venta USD = 4
    assert len(ops) == EXPECTED_OPS_COUNT


def test_parse_orden_cronologico(parsed: ParsedCsv) -> None:
    """
    Verifica que las operaciones se devuelven ordenadas por fecha y hora.
    """

    ops, _ = parsed
    fechas = [o.fecha for o in ops]

    assert fechas == sorted(fechas)
    assert ops[0].fecha == date(2026, 2, 1)
    assert ops[-1].fecha == date(2026, 6, 10)


def test_parse_compra_eur_directo(parsed: ParsedCsv) -> None:
    """
    Verifica que una compra en EUR se parsea con contravalor y comisión directos.
    """

    ops, _ = parsed
    eur_compra = next(o for o in ops if o.isin == "IE0000000099")

    assert eur_compra.tipo == TipoOperacion.COMPRA
    assert eur_compra.cantidad == EXPECTED_EUR_COMPRA_CANTIDAD
    assert eur_compra.contravalor_eur == Decimal("-100.00")
    assert eur_compra.comision_eur == Decimal("-1.00")


def test_parse_compra_usd_usa_contravalor_eur_real(parsed: ParsedCsv) -> None:
    """
    Verifica que una compra en USD usa el contravalor EUR del cambio de divisa.
    """

    ops, _ = parsed
    # primera compra USD: 10 ud @ 20 USD → 200 EUR reales del cambio
    usd_compra = next(
        o
        for o in ops
        if o.isin == "US0000000001"
        and o.tipo == TipoOperacion.COMPRA
        and o.cantidad == EXPECTED_USD_COMPRA_CANTIDAD
        and o.fecha == date(2026, 2, 15)
    )

    assert usd_compra.contravalor_eur == Decimal("-200.00")
    assert usd_compra.comision_eur == Decimal("-1.00")


def test_parse_venta_usd(parsed: ParsedCsv) -> None:
    """
    Verifica que una venta en USD se parsea con su contravalor EUR y comisión.
    """

    ops, _ = parsed
    venta = next(o for o in ops if o.tipo == TipoOperacion.VENTA)

    assert venta.isin == "US0000000001"
    assert venta.cantidad == EXPECTED_VENTA_CANTIDAD
    assert venta.contravalor_eur == Decimal("450.00")
    assert venta.comision_eur == Decimal("-1.00")


def test_parse_comision_conectividad_aparte(parsed: ParsedCsv) -> None:
    """
    Verifica que las comisiones de conectividad se agregan aparte de operaciones.
    """

    _, comisiones_conectividad = parsed
    assert comisiones_conectividad == Decimal("2.50")


HEADER = (
    "Fecha,Hora,Fecha valor,Producto,ISIN,Descripción,Tipo,Variación,,Saldo,,ID Orden\n"
)


def _write_csv(tmp_path: Path, body: str) -> Path:
    """
    Escribe un CSV con cabecera estándar y devuelve la ruta.

    Args:
        tmp_path: Directorio temporal de pytest.
        body: Filas (sin cabecera) ya formateadas.

    Returns:
        Ruta al CSV creado.
    """

    path = tmp_path / "test.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def test_parse_usd_sin_cambio_de_divisa_lanza_error(tmp_path: Path) -> None:
    """
    Verifica que una operación USD sin fila 'Cambio de Divisa' EUR falla.
    """

    body = (
        "01-02-2026,10:00,01-02-2026,FAKE,US0000000099,"
        '"Compra 10 Fake@10 USD (US0000000099)",,USD,"-100,00",USD,"0,00",ORD-1\n'
    )
    csv_path = _write_csv(tmp_path, body)

    with pytest.raises(ValueError, match="Sin contravalor EUR"):
        parse_csv(csv_path)


def test_parse_fila_huerfana_sin_isin_ni_orden(tmp_path: Path) -> None:
    """
    Verifica que las filas sin ISIN ni ID Orden se descartan.
    """

    # fila sin ISIN ni ID Orden (y sin texto de conectividad) → descarte silencioso
    body = (
        '01-02-2026,10:00,01-02-2026,,,Texto sin clasificar,,EUR,"-1,00",EUR,"0,00",\n'
    )
    csv_path = _write_csv(tmp_path, body)

    ops, comisiones = parse_csv(csv_path)
    assert ops == []
    assert comisiones == Decimal(0)


def test_parse_grupo_sin_header_compra_venta(tmp_path: Path) -> None:
    """
    Verifica que un grupo sin fila principal Compra/Venta se descarta.
    """

    # mismo ID Orden pero solo una comisión, sin fila 'Compra 10 Fake@...'
    body = (
        "01-02-2026,10:00,01-02-2026,FAKE,IE0000000077,"
        'Costes de transacción,,EUR,"-1,00",EUR,"0,00",ORD-X\n'
    )
    csv_path = _write_csv(tmp_path, body)

    ops, _ = parse_csv(csv_path)
    assert ops == []


def test_parse_csv_solo_cabecera(tmp_path: Path) -> None:
    """
    Verifica que un CSV vacío (solo cabecera) devuelve listas/decimales nulos.
    """

    csv_path = _write_csv(tmp_path, "")

    ops, comisiones = parse_csv(csv_path)
    assert ops == []
    assert comisiones == Decimal(0)
