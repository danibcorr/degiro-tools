# Standard libraries
from collections import deque
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class OperationType(StrEnum):
    """
    Stock operation type recognized by the parser.

    Inherits from ``str`` to keep compatibility with direct
    comparisons against the ``"Compra"``/``"Venta"`` literals used by
    existing renderers and by the Degiro XLSX statement data.
    """

    BUY = "Compra"
    SELL = "Venta"


@dataclass(frozen=True)
class Operation:
    """
    Normalized buy or sell operation in the broker's real EUR.

    Attributes:
        date: Operation date.
        time: Time in ``HH:MM`` format.
        isin: ISIN identifier of the instrument.
        product: Descriptive product name.
        operation_type: ``OperationType.BUY`` or ``OperationType.SELL``.
        quantity: Number of units.
        amount_eur: Consideration in EUR (sign included).
        fee_eur: Fees attributable to the operation (sign included).
    """

    date: date
    time: str
    isin: str
    product: str
    operation_type: OperationType
    quantity: int
    amount_eur: Decimal
    fee_eur: Decimal


@dataclass(frozen=True)
class Sale:
    """
    Sale matched against FIFO lots with its acquisition cost.

    Attributes:
        date: Sale date.
        isin: ISIN identifier of the instrument.
        product: Descriptive product name.
        quantity: Units sold.
        acquisition_cost: FIFO acquisition cost imputed in EUR.
        transfer_value: Transfer value net of fees in EUR.
        gain_loss: Capital gain or loss
            (``transfer_value - acquisition_cost``).
    """

    date: date
    isin: str
    product: str
    quantity: int
    acquisition_cost: Decimal
    transfer_value: Decimal
    gain_loss: Decimal


@dataclass
class Lot:
    """
    Purchase lot pending consumption by FIFO.

    Mutable: the quantity is decremented as sales consume it.

    Attributes:
        quantity: Units remaining in the lot.
        unit_cost: Unit cost in EUR (includes the purchase fee).
        date: Date of the original purchase.
    """

    quantity: int
    unit_cost: Decimal
    date: date


@dataclass(frozen=True)
class TaxBracket:
    """
    Savings-base bracket (art. 66 LIRPF) with its base and quota.

    Attributes:
        lower: Lower bound of the bracket in EUR.
        upper: Upper bound of the bracket in EUR, or ``None`` if last.
        rate: Applied tax rate (e.g. ``0.19``).
        base: Taxable base covered by this bracket in EUR.
        quota: Resulting quota (``base * rate``) in EUR.
    """

    lower: Decimal
    upper: Decimal | None
    rate: Decimal
    base: Decimal
    quota: Decimal


@dataclass(frozen=True)
class ReportData:
    """
    Precomputed report aggregates, decoupled from the output format.

    Holds all the information required to render the report in any
    format (stdout, JSON, Excel) without recomputing.

    Attributes:
        sales: Sales matched by FIFO.
        total_gain_loss: Sum of capital gain/loss for the period.
        irpf_quota: Bracket breakdown, or ``None`` if ``include_tax``
            is ``False`` or ``total_gain_loss <= 0``.
        connectivity_fees: Absolute total of connectivity fees.
        net_return: Return after taxes and custody fees, or ``None``
            when not applicable (``include_tax`` ``False`` or
            ``total_gain_loss <= 0``).
        pending_lots: Open portfolio after applying FIFO.
        include_tax: Whether the report must render the IRPF block.
    """

    sales: list[Sale]
    total_gain_loss: Decimal
    irpf_quota: list[TaxBracket] | None
    connectivity_fees: Decimal
    net_return: Decimal | None
    pending_lots: dict[str, deque[Lot]]
    include_tax: bool
