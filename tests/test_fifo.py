# Standard libraries
from decimal import Decimal

# 3pps
import pytest

# Own modules
from degiro_tools import calcular_fifo
from tests.conftest import make_compra, make_venta

EXPECTED_PENDIENTES_CANTIDAD = 5


def test_fifo_venta_parcial_dos_lotes() -> None:
    """
    Verifica que una venta consume FIFO dos lotes y deja el resto pendiente.
    """

    # Compra 10 ud, contravalor 100 EUR + comisión 1 EUR → coste_unit 10.10
    # Compra 10 ud, contravalor 200 EUR + comisión 1 EUR → coste_unit 20.10
    # Venta 15 ud, contravalor 450 EUR – comisión 1 EUR → valor_trans 449.00
    # FIFO: 10·10.10 + 5·20.10 = 101.00 + 100.50 = 201.50 de coste
    # G/P = 449.00 - 201.50 = 247.50
    ops = [
        make_compra("X", 10, "-100", "-1", dia=1),
        make_compra("X", 10, "-200", "-1", dia=2),
        make_venta("X", 15, "450", "-1", dia=3),
    ]

    ventas, lotes = calcular_fifo(ops)

    assert len(ventas) == 1
    v = ventas[0]
    assert v.coste_adq == Decimal("201.50")
    assert v.valor_trans == Decimal("449.00")
    assert v.gp == Decimal("247.50")
    pendientes = list(lotes["X"])
    assert len(pendientes) == 1
    assert pendientes[0].cantidad == EXPECTED_PENDIENTES_CANTIDAD
    assert pendientes[0].coste_unit == Decimal("20.1")


def test_fifo_aislado_por_isin() -> None:
    """
    Verifica que las ventas de un ISIN no consumen lotes de otro ISIN.
    """

    ops = [
        make_compra("X", 5, "-50", "0", dia=1),
        make_compra("Y", 5, "-100", "0", dia=2),
        make_venta("X", 5, "75", "0", dia=3),
    ]

    ventas, lotes = calcular_fifo(ops)

    assert ventas[0].gp == Decimal("25.00")
    assert len(lotes["Y"]) == 1
    assert not lotes["X"]


def test_fifo_sin_lotes_suficientes_lanza_error() -> None:
    """
    Verifica que vender más unidades de las compradas lanza ``ValueError``.
    """

    ops = [
        make_compra("X", 5, "-50", "0", dia=1),
        make_venta("X", 10, "100", "0", dia=2),
    ]

    with pytest.raises(ValueError, match="FIFO sin lotes suficientes"):
        calcular_fifo(ops)


def test_fifo_venta_vacia_lote_exactamente() -> None:
    """Verifica que una venta que consume todo el lote lo retira de la cola."""

    ops = [
        make_compra("X", 10, "-100", "0", dia=1),
        make_venta("X", 10, "150", "0", dia=2),
    ]

    ventas, lotes = calcular_fifo(ops)

    assert len(ventas) == 1
    assert ventas[0].gp == Decimal("50.00")
    assert len(lotes["X"]) == 0
