# Standard libraries
from datetime import date
from decimal import Decimal
from pathlib import Path

# 3pps
from openpyxl import Workbook

# Own modules
from degiro_tools import Operation, OperationType

# Header of the Degiro "Estado de cuenta" sheet. The two unlabeled
# columns (amount and balance) are written as empty cells, exactly as
# the real export does.
ACCOUNT_HEADER: list[str | None] = [
    "Fecha",
    "Hora",
    "Fecha valor",
    "Producto",
    "ISIN",
    "Descripción",
    "Tipo",
    "Variación",
    None,
    "Saldo",
    None,
    "ID Orden",
]


def account_row(  # noqa: PLR0913 - test row builder
    description: str,
    *,
    currency: str | None = None,
    amount: float | str | None = None,
    isin: str | None = None,
    order_id: str | None = None,
    date_str: str = "01-02-2026",
    time: str = "10:00",
    product: str = "PROD",
) -> list[object]:
    """
    Build a single Degiro account-statement row (12 columns).

    Amount is placed in the unlabeled column 8 as a native number,
    mirroring the real XLSX export.

    Args:
        description: Operation description (column 5).
        currency: Variation currency code (column 7).
        amount: Variation amount (column 8); native number or text.
        isin: ISIN identifier (column 4).
        order_id: Order ID (column 11).
        date_str: Operation date in ``dd-mm-yyyy`` format.
        time: Time in ``HH:MM`` format.
        product: Product name (column 3).

    Returns:
        List of twelve cell values ready to append to a worksheet.
    """

    return [
        date_str,
        time,
        date_str,
        product,
        isin,
        description,
        None,
        currency,
        amount,
        currency,
        0.0,
        order_id,
    ]


def write_account_xlsx(path: Path, rows: list[list[object]]) -> Path:
    """
    Write a Degiro Account.xlsx fixture with the given data rows.

    Args:
        path: Destination path for the workbook.
        rows: Data rows (each a list of twelve cell values).

    Returns:
        The path to the written workbook.
    """

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Estado de cuenta"
    sheet.append(ACCOUNT_HEADER)
    for row in rows:
        sheet.append(row)

    workbook.save(path)

    return path


def make(  # noqa: PLR0913 - test builder
    operation_type: OperationType,
    isin: str,
    quantity: int,
    amount: str,
    fee: str,
    day: int,
) -> Operation:
    """
    Build an ``Operation`` dated 2026-01-``day`` with Decimal money.
    """

    return Operation(
        date=date(2026, 1, day),
        time="10:00",
        isin=isin,
        product="TEST",
        operation_type=operation_type,
        quantity=quantity,
        amount_eur=Decimal(amount),
        fee_eur=Decimal(fee),
    )


def make_buy(
    isin: str, quantity: int, amount: str, fee: str, day: int = 1
) -> Operation:
    """
    Build a buy ``Operation`` for tests (date 2026-01-``day``).
    """

    return make(OperationType.BUY, isin, quantity, amount, fee, day)


def make_sell(
    isin: str, quantity: int, amount: str, fee: str, day: int = 1
) -> Operation:
    """
    Build a sell ``Operation`` for tests (date 2026-01-``day``).
    """

    return make(OperationType.SELL, isin, quantity, amount, fee, day)
