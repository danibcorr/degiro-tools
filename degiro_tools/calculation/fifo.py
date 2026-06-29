# Standard libraries
from collections import defaultdict, deque
from decimal import ROUND_HALF_UP, Decimal

# Own modules
from ..domain.constants import CENT_QUANTIZE
from ..domain.models import Lot, Operation, OperationType, Sale


def calculate_fifo(ops: list[Operation]) -> tuple[list[Sale], dict[str, deque[Lot]]]:
    """
    Consume lots FIFO per ISIN and match sales to their cost.

    Purchase fees add to the cost (art. 35.1.b LIRPF) and sale fees
    subtract from the transfer value (art. 35.2 LIRPF).

    Args:
        ops: Normalized operations sorted chronologically.

    Returns:
        Tuple containing:
            - List of matched sales with computed gain/loss.
            - Dict ISIN -> queue of pending lots (open portfolio).

    Raises:
        ValueError: If an operation has zero quantity or if a sale
            does not have enough lots to consume.
    """

    lots: dict[str, deque[Lot]] = defaultdict(deque)

    sales: list[Sale] = []
    for op in ops:
        if op.quantity == 0:
            # Changed: reject zero-quantity operations explicitly -
            # Reason: a zero-quantity buy divided by zero when computing
            # the unit cost, raising a cryptic ZeroDivisionError.
            raise ValueError(f"Operation with zero quantity: {op.date} {op.isin}")

        if op.operation_type == OperationType.BUY:
            total_cost = abs(op.amount_eur) + abs(op.fee_eur)

            lots[op.isin].append(
                Lot(
                    quantity=op.quantity,
                    unit_cost=total_cost / op.quantity,
                    date=op.date,
                )
            )

            continue

        transfer_value = op.amount_eur - abs(op.fee_eur)
        remaining_quantity = op.quantity
        acquisition_cost = Decimal(0)
        lots_queue = lots[op.isin]

        while remaining_quantity > 0:
            if not lots_queue:
                raise ValueError(
                    f"FIFO without enough lots for sale {op.date} {op.isin}"
                )

            lot = lots_queue[0]
            used = min(remaining_quantity, lot.quantity)
            acquisition_cost += Decimal(used) * lot.unit_cost
            lot.quantity -= used
            remaining_quantity -= used

            if lot.quantity == 0:
                lots_queue.popleft()

        sales.append(
            Sale(
                date=op.date,
                isin=op.isin,
                product=op.product,
                quantity=op.quantity,
                acquisition_cost=acquisition_cost.quantize(
                    CENT_QUANTIZE, rounding=ROUND_HALF_UP
                ),
                transfer_value=transfer_value.quantize(
                    CENT_QUANTIZE, rounding=ROUND_HALF_UP
                ),
                gain_loss=(transfer_value - acquisition_cost).quantize(
                    CENT_QUANTIZE, rounding=ROUND_HALF_UP
                ),
            )
        )

    return sales, lots
