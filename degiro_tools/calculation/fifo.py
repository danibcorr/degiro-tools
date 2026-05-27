# Standard libraries
from collections import defaultdict, deque
from decimal import ROUND_HALF_UP, Decimal

# Own modules
from ..domain.constants import CENT_QUANTIZE
from ..domain.models import Lote, Operacion, TipoOperacion, Venta


def calcular_fifo(ops: list[Operacion]) -> tuple[list[Venta], dict[str, deque[Lote]]]:
    """
    Consume lotes FIFO por ISIN y casa las ventas con su coste de adquisición.

    Las comisiones de compra suman al coste (art. 35.1.b LIRPF) y las de venta
    restan del valor de transmisión (art. 35.2 LIRPF).

    Args:
        ops: Operaciones normalizadas ordenadas cronológicamente.

    Returns:
        Tupla con:
            - Lista de ventas casadas con G/P calculada.
            - Diccionario ISIN → cola de lotes pendientes (cartera abierta).

    Raises:
        ValueError: Si una venta no tiene lotes suficientes para consumir.
    """

    lotes: dict[str, deque[Lote]] = defaultdict(deque)

    ventas: list[Venta] = []
    for op in ops:
        if op.tipo == TipoOperacion.COMPRA:
            coste_total = abs(op.contravalor_eur) + abs(op.comision_eur)

            lotes[op.isin].append(
                Lote(
                    cantidad=op.cantidad,
                    coste_unit=coste_total / op.cantidad,
                    fecha=op.fecha,
                )
            )

            continue

        valor_trans = op.contravalor_eur - abs(op.comision_eur)
        cantidad_restante = op.cantidad
        coste_adq = Decimal(0)
        lotes_cola = lotes[op.isin]

        while cantidad_restante > 0:
            if not lotes_cola:
                raise ValueError(
                    f"FIFO sin lotes suficientes para venta {op.fecha} {op.isin}"
                )

            lote = lotes_cola[0]
            usar = min(cantidad_restante, lote.cantidad)
            coste_adq += Decimal(usar) * lote.coste_unit
            lote.cantidad -= usar
            cantidad_restante -= usar

            if lote.cantidad == 0:
                lotes_cola.popleft()

        ventas.append(
            Venta(
                fecha=op.fecha,
                isin=op.isin,
                producto=op.producto,
                cantidad=op.cantidad,
                coste_adq=coste_adq.quantize(CENT_QUANTIZE, rounding=ROUND_HALF_UP),
                valor_trans=valor_trans.quantize(CENT_QUANTIZE, rounding=ROUND_HALF_UP),
                gp=(valor_trans - coste_adq).quantize(
                    CENT_QUANTIZE, rounding=ROUND_HALF_UP
                ),
            )
        )

    return ventas, lotes
