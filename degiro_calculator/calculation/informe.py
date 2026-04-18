# Standard libraries
from collections import deque
from decimal import ROUND_HALF_UP, Decimal

# Own modules
from ..domain.constants import CENT_QUANTIZE
from ..domain.models import InformeData, Lote, Venta
from .tax import calcular_cuota_irpf


def build_informe_data(
    ventas: list[Venta],
    lotes: dict[str, deque[Lote]],
    comisiones_conectividad: Decimal,
    *,
    incluir_tax: bool,
) -> InformeData:
    """
    Precomputa los agregados del informe a partir de ventas y cartera abierta.

    Calcula el total de G/P, desglosa la cuota IRPF (si procede) y deriva la
    rentabilidad neta final.

    Args:
        ventas: Ventas casadas por FIFO.
        lotes: Cartera abierta por ISIN.
        comisiones_conectividad: Total absoluto de comisiones de conectividad.
        incluir_tax: Si ``False`` omite cuota y rentabilidad neta.

    Returns:
        ``InformeData`` con todos los campos precomputados y listos para render.
    """

    total_gp = sum((v.gp for v in ventas), Decimal(0))

    cuota_irpf = calcular_cuota_irpf(total_gp) if incluir_tax and total_gp > 0 else None

    rentabilidad_neta: Decimal | None = None
    if cuota_irpf is not None:
        cuota_total = sum((t.cuota for t in cuota_irpf), Decimal(0))
        rentabilidad_neta = (total_gp - cuota_total - comisiones_conectividad).quantize(
            CENT_QUANTIZE, rounding=ROUND_HALF_UP
        )

    return InformeData(
        ventas=ventas,
        total_gp=total_gp,
        cuota_irpf=cuota_irpf,
        comisiones_conectividad=comisiones_conectividad,
        rentabilidad_neta=rentabilidad_neta,
        lotes_pendientes=lotes,
        incluir_tax=incluir_tax,
    )
