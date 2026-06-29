# Standard libraries
import logging
from typing import Any, Final

# 3pps
import polars as pl

# Own modules
from ..domain.portfolio import (
    OUTPUT_INVESTED_COL,
    OUTPUT_ISIN_COL,
    OUTPUT_PERCENTAGE_COL,
    OUTPUT_PRICE_COL,
    OUTPUT_PRODUCT_COL,
    OUTPUT_QUANTITY_COL,
    OUTPUT_TOTAL_COL,
    OUTPUT_TYPE_COL,
)
from ..providers.yahoo import get_price_eur, get_usd_eur_rate, is_etf

_FALLBACK_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


def obtain_yahoo_info(
    df_input: pl.DataFrame, logger: logging.Logger | None = None
) -> pl.DataFrame:
    """
    Enrich the positions DataFrame with current prices.

    For each position, resolves the ticker via ISIN, fetches the
    latest price, converts it to EUR when the currency is USD, and
    computes the invested amount.

    Args:
        df_input: DataFrame with columns Producto, Symbol/ISIN and
            Cantidad (output of parse_portfolio_xlsx).
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        DataFrame with additional columns: product type, unit price
        in EUR and invested amount in EUR.
    """

    log = logger if logger is not None else _FALLBACK_LOGGER
    eur_rate: float | None = get_usd_eur_rate(logger=logger)
    data: list[dict[str, Any]] = []

    for product, isin, quantity in df_input.iter_rows():
        price_eur = get_price_eur(isin, eur_rate, logger=logger)

        if price_eur is None:
            log.warning("No price available for %s.", isin)
            continue

        invested = quantity * price_eur

        data.append(
            {
                OUTPUT_PRODUCT_COL: product,
                OUTPUT_ISIN_COL: isin,
                OUTPUT_TYPE_COL: "ETF" if is_etf(product) else "Accion",
                OUTPUT_QUANTITY_COL: quantity,
                OUTPUT_PRICE_COL: price_eur,
                OUTPUT_INVESTED_COL: invested,
            }
        )

    return pl.DataFrame(data)


def compute_portfolio_percentage(df_input: pl.DataFrame) -> pl.DataFrame:
    """
    Add total invested and portfolio percentage columns.

    Args:
        df_input: DataFrame with the Invertido EUR column (output of
            obtain_yahoo_info).

    Returns:
        DataFrame with additional columns Total EUR and Porcentaje
        Cartera.
    """

    return df_input.with_columns(
        pl.col(OUTPUT_INVESTED_COL).sum().alias(OUTPUT_TOTAL_COL)
    ).with_columns(
        # Changed: guard against a zero total - Reason: an empty or
        # all-zero portfolio used to yield NaN/inf percentages.
        pl.when(pl.col(OUTPUT_TOTAL_COL) == 0)
        .then(pl.lit(0.0))
        .otherwise(pl.col(OUTPUT_INVESTED_COL) / pl.col(OUTPUT_TOTAL_COL) * 100)
        .alias(OUTPUT_PERCENTAGE_COL)
    )
