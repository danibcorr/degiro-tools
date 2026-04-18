# Standard libraries
import io
from collections import defaultdict, deque
from datetime import date
from decimal import Decimal

# 3pps
import pytest
from rich.console import Console

# Own modules
from degiro_calculator import Lote, Venta, imprimir_informe


@pytest.fixture
def ventas_simples() -> list[Venta]:
    """Devuelve una venta sintética con G/P positiva de 50 EUR."""

    return [
        Venta(
            fecha=date(2026, 3, 1),
            isin="IE0000000099",
            producto="TEST",
            cantidad=10,
            coste_adq=Decimal("100.00"),
            valor_trans=Decimal("150.00"),
            gp=Decimal("50.00"),
        )
    ]


@pytest.fixture
def lotes_un_pendiente() -> dict[str, deque[Lote]]:
    """Cartera con un único lote pendiente."""

    lotes: dict[str, deque[Lote]] = defaultdict(deque)
    lotes["IE0000000099"].append(
        Lote(cantidad=5, coste_unit=Decimal("10.00"), fecha=date(2026, 1, 15))
    )
    return lotes


def _make_console() -> tuple[Console, io.StringIO]:
    """Crea una consola rich sin color capturada en un StringIO."""

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, no_color=True, width=200)
    return console, buf


def test_imprimir_informe_incluye_secciones_con_tax(
    ventas_simples: list[Venta],
    lotes_un_pendiente: dict[str, deque[Lote]],
) -> None:
    """Verifica que con tax se imprimen todas las secciones clave."""

    console, buf = _make_console()
    imprimir_informe(
        ventas_simples,
        lotes_un_pendiente,
        comisiones_conectividad=Decimal("5.00"),
        incluir_tax=True,
        console=console,
    )
    out = buf.getvalue()

    assert "Ventas casadas" in out
    assert "TOTAL GANANCIA/PÉRDIDA PATRIMONIAL" in out
    assert "50.00" in out
    assert "Estimación cuota IRPF" in out
    assert "CUOTA ESTIMADA TOTAL" in out
    assert "9.50" in out
    assert "RENTABILIDAD NETA REAL" in out
    assert "Cartera abierta" in out
    assert "IE0000000099" in out


def test_imprimir_informe_no_tax_omite_bloques_fiscales(
    ventas_simples: list[Venta],
    lotes_un_pendiente: dict[str, deque[Lote]],
) -> None:
    """Verifica que ``--no-tax`` omite cuota IRPF y rentabilidad neta."""

    console, buf = _make_console()
    imprimir_informe(
        ventas_simples,
        lotes_un_pendiente,
        comisiones_conectividad=Decimal(0),
        incluir_tax=False,
        console=console,
    )
    out = buf.getvalue()

    assert "Estimación cuota IRPF" not in out
    assert "RENTABILIDAD NETA" not in out
    assert "TOTAL GANANCIA/PÉRDIDA PATRIMONIAL" in out


def test_imprimir_informe_sin_ventas() -> None:
    """Verifica que sin ventas se imprime total 0 y no hay rentabilidad neta."""

    console, buf = _make_console()
    imprimir_informe([], defaultdict(deque), incluir_tax=True, console=console)
    out = buf.getvalue()

    assert "TOTAL GANANCIA/PÉRDIDA PATRIMONIAL" in out
    assert "0.00" in out
    assert "Sin ventas en el ejercicio." in out
    assert "RENTABILIDAD NETA" not in out
    assert "Sin cuota" in out


def test_imprimir_informe_cartera_vacia(
    ventas_simples: list[Venta],
) -> None:
    """Verifica el mensaje cuando no quedan lotes pendientes."""

    console, buf = _make_console()
    imprimir_informe(
        ventas_simples, defaultdict(deque), incluir_tax=True, console=console
    )
    out = buf.getvalue()

    assert "Sin cartera abierta." in out


def test_imprimir_informe_comisiones_conectividad_oculto_si_cero(
    ventas_simples: list[Venta],
) -> None:
    """Verifica que el bloque de conectividad se omite cuando no hay comisiones."""

    console, buf = _make_console()
    imprimir_informe(
        ventas_simples,
        defaultdict(deque),
        comisiones_conectividad=Decimal(0),
        incluir_tax=True,
        console=console,
    )
    out = buf.getvalue()

    assert "Comisiones de conectividad" not in out


def test_imprimir_informe_perdida_no_muestra_rentabilidad_neta(
    lotes_un_pendiente: dict[str, deque[Lote]],
) -> None:
    """Verifica que una pérdida no genera cálculo de rentabilidad neta."""

    ventas = [
        Venta(
            fecha=date(2026, 3, 1),
            isin="IE0000000099",
            producto="TEST",
            cantidad=10,
            coste_adq=Decimal("200.00"),
            valor_trans=Decimal("150.00"),
            gp=Decimal("-50.00"),
        )
    ]

    console, buf = _make_console()
    imprimir_informe(ventas, lotes_un_pendiente, incluir_tax=True, console=console)
    out = buf.getvalue()

    assert "RENTABILIDAD NETA" not in out
    assert "Sin cuota" in out
