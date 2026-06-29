# Standard libraries
import logging
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final, TypedDict

# 3pps
import polars as pl

# Own modules
from ..domain.models import Operation, OperationType
from .columns import (
    CURRENCY_COL,
    DATE_COL,
    DESCRIPTION_COL,
    ISIN_COL,
    ORDER_ID_COL,
    TIME_COL,
    VARIATION_COL,
)

_FALLBACK_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

# Worksheet holding the Degiro account statement inside Account.xlsx.
ACCOUNT_SHEET_NAME: Final[str] = "Estado de cuenta"

# Largest column index accessed unconditionally while reading a data row.
# Rows shorter than this are truncated/malformed and are skipped.
MIN_ROW_LEN: Final[int] = VARIATION_COL + 1

OPERATION_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^(Compra|Venta)\s+(\d+)\s+.*@([\d.,]+)\s+\w+"
)
FEE_DESCRIPTIONS: Final[tuple[str, ...]] = (
    "Costes de transacción",
    "Comisión",
    "Tasa",
    "Impuesto",
    "Spanish Transaction Tax",
    "Transaction Tax",
)


class AccountRow(TypedDict):
    """
    Normalized account-statement row with an exact Decimal amount.

    Attributes:
        date: Operation date in ``dd-mm-yyyy`` format.
        time: Time in ``HH:MM`` format.
        isin: ISIN identifier of the instrument, empty when absent.
        description: Operation description.
        variation: Exact variation amount in its own currency (sign
            included).
        currency: Variation currency code, empty when absent.
    """

    date: str
    time: str
    isin: str
    description: str
    variation: Decimal
    currency: str


def amount_to_decimal(text: str) -> Decimal:
    """
    Convert a Degiro XLSX amount cell to an exact Decimal.

    The XLSX export stores amounts as native numbers that Polars
    renders as dot-decimal text (for example ``"-1734.6"``) when the
    sheet is read as strings. Converting straight from that text keeps
    full precision and avoids both the European thousand/decimal
    ambiguity and IEEE-754 float artifacts.

    Args:
        text: Raw amount cell, empty when the cell is blank.

    Returns:
        Equivalent Decimal value, or ``Decimal(0)`` if the string is
        empty.

    Raises:
        ValueError: If the string is not a valid amount.
    """

    if not text:
        return Decimal(0)

    try:
        return Decimal(text)

    except InvalidOperation as err:
        error_message = f"Invalid amount: {text!r}"
        raise ValueError(error_message) from err


def parse_date(text: str) -> date:
    """
    Parse dates in ``dd-mm-yyyy`` or ``dd-mm-yy`` format.

    Args:
        text: String with the date to parse.

    Returns:
        Corresponding ``date`` object.

    Raises:
        ValueError: If the string matches none of the accepted
            formats.
    """

    for fmt in ("%d-%m-%Y", "%d-%m-%y"):
        try:
            return datetime.strptime(text, fmt).date()

        except ValueError:
            continue

    raise ValueError(f"Unrecognized date: {text}")


def group_key(row: list[str]) -> object | None:
    """
    Return the grouping key of the row or ``None`` if it must be
    ignored.

    Uses the Order ID when present; otherwise groups by
    ``(date, time, ISIN)``.

    Args:
        row: Raw account-statement row as a list of strings.

    Returns:
        Grouping key (Order ID or tuple) or ``None`` if the row is
        discarded.
    """

    order_id = row[ORDER_ID_COL] if len(row) > ORDER_ID_COL else ""
    if order_id:
        return order_id

    isin = row[ISIN_COL]
    if isin:
        return (row[DATE_COL], row[TIME_COL], isin)

    return None


def read_account_rows(path: Path) -> list[list[str]]:
    """
    Read the account-statement sheet as rows of plain strings.

    Reads the sheet with ``infer_schema_length=0`` so every cell is
    returned as text, preserving the full decimal precision of the
    amount columns. Empty cells are normalized to empty strings and
    the header row is excluded.

    Args:
        path: Path to the Account.xlsx file exported from Degiro.

    Returns:
        List of rows, each a list of cell strings.
    """

    frame = pl.read_excel(
        path,
        sheet_name=ACCOUNT_SHEET_NAME,
        infer_schema_length=0,
    )

    return [
        ["" if cell is None else str(cell) for cell in row] for row in frame.iter_rows()
    ]


def read_operation_groups(
    path: Path,
    logger: logging.Logger | None = None,
) -> tuple[dict[object, list[AccountRow]], Decimal]:
    """
    Group the XLSX rows by operation and sum the connectivity fees.

    Args:
        path: Path to the Account.xlsx file exported from Degiro.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        Tuple containing:
            - Dict key -> list of rows (dicts with normalized fields).
            - Absolute total of market connectivity fees (EUR).
    """

    log = logger if logger is not None else _FALLBACK_LOGGER
    groups: dict[object, list[AccountRow]] = defaultdict(list)
    connectivity_fees = Decimal(0)

    for row in read_account_rows(path):
        # Defensive guard: rows shorter than the columns we read are
        # malformed and would raise IndexError mid-parse.
        if len(row) < MIN_ROW_LEN:
            log.warning(
                "Skipping malformed row with %d columns (expected >= %d): %r.",
                len(row),
                MIN_ROW_LEN,
                row,
            )
            continue

        try:
            variation = amount_to_decimal(row[VARIATION_COL])

        except ValueError:
            log.warning(
                "Skipping row with invalid amount %r: %r.",
                row[VARIATION_COL],
                row,
            )
            continue

        description = row[DESCRIPTION_COL]
        if "Comisión de conectividad con el mercado" in description:
            connectivity_fees += abs(variation)
            continue

        key = group_key(row)
        if key is None:
            continue

        groups[key].append(
            AccountRow(
                date=row[DATE_COL],
                time=row[TIME_COL],
                isin=row[ISIN_COL],
                description=description,
                variation=variation,
                currency=row[CURRENCY_COL],
            )
        )

    return groups, connectivity_fees


def resolve_eur_amount(header: AccountRow, rows: list[AccountRow]) -> Decimal:
    """
    Obtain the real EUR consideration of an operation.

    Prioritizes the ``Cambio de Divisa`` row in EUR; if it does not
    exist and the header is already in EUR, uses its variation
    directly.

    Args:
        header: Row containing the operation description.
        rows: Rows of the operation group.

    Returns:
        Consideration in EUR (sign included) as ``Decimal``.

    Raises:
        ValueError: If the operation has no recognizable EUR
            consideration.
    """

    fx_eur = next(
        (
            r
            for r in rows
            if "Cambio de Divisa" in r["description"] and r["currency"] == "EUR"
        ),
        None,
    )
    if fx_eur is not None:
        return fx_eur["variation"]

    if header["currency"] == "EUR":
        return header["variation"]

    raise ValueError(
        f"No EUR amount for operation {header['date']} "
        f"{header['time']} {header['isin']}"
    )


def build_partial_executions(
    headers: list[AccountRow],
    rows: list[AccountRow],
    total_fee: Decimal,
) -> list[Operation]:
    """
    Build operations from partial executions of a single order.

    Distributes fees and currency exchange proportionally by share
    quantity.

    Args:
        headers: Buy/sell rows of the group.
        rows: All rows of the group (includes fees and currency
            exchange).
        total_fee: Sum of the group fees.

    Returns:
        List of operations, one per partial execution.

    Raises:
        ValueError: If the EUR consideration cannot be resolved.
    """

    total_qty = sum(
        int(OPERATION_REGEX.match(h["description"]).group(2))  # type: ignore[union-attr, misc]
        for h in headers
    )

    total_fx_eur: Decimal | None = next(
        (
            r["variation"]
            for r in rows
            if "Cambio de Divisa" in r["description"] and r["currency"] == "EUR"
        ),
        None,
    )

    ops: list[Operation] = []
    for header in headers:
        match = OPERATION_REGEX.match(header["description"])

        assert match is not None

        qty = int(match.group(2))
        ratio = Decimal(qty) / Decimal(total_qty)

        if total_fx_eur is not None:
            amount = total_fx_eur * ratio
        elif header["currency"] == "EUR":
            amount = header["variation"]
        else:
            raise ValueError(
                f"No EUR amount for operation {header['date']} "
                f"{header['time']} {header['isin']}"
            )

        ops.append(
            Operation(
                date=parse_date(header["date"]),
                time=header["time"],
                isin=header["isin"],
                product=header["description"].split("@")[0].split(" ", 2)[2].strip(),
                operation_type=OperationType(match.group(1)),
                quantity=qty,
                amount_eur=amount,
                fee_eur=total_fee * ratio,
            )
        )

    return ops


def build_operation_from_group(rows: list[AccountRow]) -> list[Operation]:
    """
    Build one or more ``Operation`` objects from grouped rows.

    When an order has partial executions (several buy/sell rows with
    the same Order ID), generates one operation per execution and
    distributes the fees proportionally by share quantity.

    Args:
        rows: XLSX rows belonging to a single operation.

    Returns:
        List of normalized operations (empty if the group contains no
        recognizable buy/sell rows).

    Raises:
        ValueError: If the EUR consideration or the date cannot be
            resolved.
    """

    headers = [r for r in rows if OPERATION_REGEX.match(r["description"])]
    if not headers:
        return []

    total_fee = sum(
        (
            r["variation"]
            for r in rows
            if any(k in r["description"] for k in FEE_DESCRIPTIONS)
        ),
        Decimal(0),
    )

    if len(headers) == 1:
        header = headers[0]
        match = OPERATION_REGEX.match(header["description"])

        assert match is not None

        amount = resolve_eur_amount(header, rows)

        return [
            Operation(
                date=parse_date(header["date"]),
                time=header["time"],
                isin=header["isin"],
                product=header["description"].split("@")[0].split(" ", 2)[2].strip(),
                operation_type=OperationType(match.group(1)),
                quantity=int(match.group(2)),
                amount_eur=amount,
                fee_eur=total_fee,
            )
        ]

    return build_partial_executions(headers, rows, total_fee)


def parse_account_xlsx(
    path: Path, logger: logging.Logger | None = None
) -> tuple[list[Operation], Decimal]:
    """
    Parse a Degiro Account.xlsx statement.

    Reads the ``Estado de cuenta`` sheet and groups rows by Order ID
    (or by ``(Date, Time, ISIN)`` when there is no ID) to obtain the
    broker's real EUR consideration (the ``Cambio de Divisa`` row in
    EUR) and the associated fees. Amounts are read as exact Decimals
    so no monetary precision is lost.

    Args:
        path: Path to the Account.xlsx file exported from Degiro
            (account statement).
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        Tuple containing:
            - List of normalized buy/sell operations, sorted by date
              and time.
            - Absolute total of market connectivity fees (in EUR).

    Raises:
        ValueError: If an operation has no EUR consideration or the
            date is not valid.
    """

    groups, connectivity_fees = read_operation_groups(path, logger=logger)

    ops: list[Operation] = []
    for rows in groups.values():
        ops.extend(build_operation_from_group(rows))

    ops.sort(key=lambda o: (o.date, o.time))

    return ops, connectivity_fees
