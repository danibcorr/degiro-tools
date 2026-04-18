# Standard libraries
from decimal import Decimal

# 3pps
import pytest

# Own modules
from degiro_calculator import calcular_cuota_irpf

EXPECTED_TRAMOS_10K = 2
EXPECTED_TRAMOS_60K = 3


@pytest.mark.parametrize("total", [Decimal(0), Decimal("-50"), Decimal("-0.01")])
def test_sin_ganancia_devuelve_lista_vacia(total: Decimal) -> None:
    """
    Verifica que una ganancia nula o negativa produce un desglose vacío.
    """

    assert calcular_cuota_irpf(total) == []


def test_un_tramo_100_eur() -> None:
    """
    Verifica el cálculo de cuota en el primer tramo (100 EUR al 19%).
    """

    desglose = calcular_cuota_irpf(Decimal("100"))

    assert len(desglose) == 1
    t = desglose[0]
    assert t.tipo == Decimal("0.19")
    assert t.base == Decimal("100.00")
    assert t.cuota == Decimal("19.00")


def test_limite_primer_tramo_6000() -> None:
    """
    Verifica que 6.000 EUR exactos se quedan en el primer tramo al 19%.
    """

    desglose = calcular_cuota_irpf(Decimal("6000"))
    assert len(desglose) == 1
    # 6000 * 0.19 = 1140
    assert sum(t.cuota for t in desglose) == Decimal("1140.00")


def test_dos_tramos_10000() -> None:
    """
    Verifica que 10.000 EUR se distribuyen entre los dos primeros tramos.
    """

    # 6000 @ 19% = 1140 + 4000 @ 21% = 840 → 1980
    desglose = calcular_cuota_irpf(Decimal("10000"))

    assert len(desglose) == EXPECTED_TRAMOS_10K
    assert sum(t.cuota for t in desglose) == Decimal("1980.00")
    assert desglose[1].tipo == Decimal("0.21")
    assert desglose[1].base == Decimal("4000.00")


def test_tres_tramos_60000() -> None:
    """
    Verifica que 60.000 EUR se distribuyen entre los tres primeros tramos.
    """

    # 6000@19 + 44000@21 + 10000@23 = 1140 + 9240 + 2300 = 12680
    desglose = calcular_cuota_irpf(Decimal("60000"))

    assert len(desglose) == EXPECTED_TRAMOS_60K
    assert sum(t.cuota for t in desglose) == Decimal("12680.00")


@pytest.mark.parametrize(
    ("total", "n_tramos", "cuota_esperada"),
    [
        # frontera exacta tramo 1
        (Decimal("6000"), 1, Decimal("1140.00")),
        # apenas cruza a tramo 2 (0.01·0.21 = 0.0021 → quantize 0.00)
        (Decimal("6000.01"), 2, Decimal("1140.00")),
        # frontera exacta tramo 2 (6000@19 + 44000@21 = 1140 + 9240)
        (Decimal("50000"), 2, Decimal("10380.00")),
        # frontera exacta tramo 3 (+150000@23 = 34500)
        (Decimal("200000"), 3, Decimal("44880.00")),
        # frontera exacta tramo 4 (+100000@27 = 27000)
        (Decimal("300000"), 4, Decimal("71880.00")),
        # apenas cruza a tramo 5 (0.01·0.30 = 0.003 → quantize 0.00)
        (Decimal("300000.01"), 5, Decimal("71880.00")),
    ],
)
def test_frontera_tramos_irpf(
    total: Decimal, n_tramos: int, cuota_esperada: Decimal
) -> None:
    """
    Verifica n.º de tramos y cuota total en las fronteras de cada tramo del ahorro.
    """

    desglose = calcular_cuota_irpf(total)

    assert len(desglose) == n_tramos
    assert sum(t.cuota for t in desglose) == cuota_esperada


def test_ultimo_tramo_sin_hasta() -> None:
    """
    Verifica que el último tramo activo (>300 000) deja ``hasta=None``.
    """

    desglose = calcular_cuota_irpf(Decimal("400000"))

    assert desglose[-1].hasta is None
    assert desglose[-1].tipo == Decimal("0.30")
