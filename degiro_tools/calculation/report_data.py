# Standard libraries
from collections import deque
from decimal import ROUND_HALF_UP, Decimal

# Own modules
from ..domain.constants import CENT_QUANTIZE
from ..domain.models import Lot, ReportData, Sale
from .tax import calculate_irpf_quota


def build_report_data(
    sales: list[Sale],
    lots: dict[str, deque[Lot]],
    connectivity_fees: Decimal,
    *,
    include_tax: bool,
) -> ReportData:
    """
    Precompute the report aggregates from sales and open portfolio.

    Computes the total gain/loss, breaks down the IRPF quota (when
    applicable) and derives the final net return.

    Args:
        sales: Sales matched by FIFO.
        lots: Open portfolio per ISIN.
        connectivity_fees: Absolute total of connectivity fees.
        include_tax: If ``False`` omit quota and net return.

    Returns:
        ``ReportData`` with every field precomputed and ready to
        render.
    """

    total_gain_loss = sum((s.gain_loss for s in sales), Decimal(0))

    irpf_quota = (
        calculate_irpf_quota(total_gain_loss)
        if include_tax and total_gain_loss > 0
        else None
    )

    net_return: Decimal | None = None
    if irpf_quota is not None:
        total_quota = sum((bracket.quota for bracket in irpf_quota), Decimal(0))
        net_return = (total_gain_loss - total_quota - connectivity_fees).quantize(
            CENT_QUANTIZE, rounding=ROUND_HALF_UP
        )

    return ReportData(
        sales=sales,
        total_gain_loss=total_gain_loss,
        irpf_quota=irpf_quota,
        connectivity_fees=connectivity_fees,
        net_return=net_return,
        pending_lots=lots,
        include_tax=include_tax,
    )
