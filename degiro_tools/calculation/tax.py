# Standard libraries
from decimal import ROUND_HALF_UP, Decimal

# Own modules
from ..domain.constants import CENT_QUANTIZE
from ..domain.models import TramoCuota

TRAMOS_AHORRO: tuple[tuple[Decimal | None, Decimal], ...] = (
    (Decimal("6000"), Decimal("0.19")),
    (Decimal("50000"), Decimal("0.21")),
    (Decimal("200000"), Decimal("0.23")),
    (Decimal("300000"), Decimal("0.27")),
    (None, Decimal("0.30")),
)


def calcular_cuota_irpf(total_gp: Decimal) -> list[TramoCuota]:
    """
    Desglosa la cuota IRPF por tramos de la base del ahorro.

    Args:
        total_gp: Ganancia patrimonial total positiva en EUR.

    Returns:
        Lista de tramos aplicados con base y cuota. Vacía si ``total_gp <= 0``.
    """

    if total_gp <= 0:
        return []

    desglose: list[TramoCuota] = []
    desde = Decimal(0)
    restante = total_gp

    for hasta, tipo in TRAMOS_AHORRO:
        amplitud = (hasta - desde) if hasta is not None else restante
        base_en_tramo = min(restante, amplitud)

        if base_en_tramo <= 0:
            break

        cuota = (base_en_tramo * tipo).quantize(CENT_QUANTIZE, rounding=ROUND_HALF_UP)
        desglose.append(
            TramoCuota(
                desde=desde.quantize(CENT_QUANTIZE),
                hasta=hasta.quantize(CENT_QUANTIZE) if hasta is not None else None,
                tipo=tipo,
                base=base_en_tramo.quantize(CENT_QUANTIZE, rounding=ROUND_HALF_UP),
                cuota=cuota,
            )
        )
        restante -= base_en_tramo
        desde = hasta if hasta is not None else desde

        if restante <= 0:
            break

    return desglose
