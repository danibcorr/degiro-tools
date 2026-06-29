# Standard libraries
import logging
from pathlib import Path
from typing import Final

# 3pps
import polars as pl

# Own modules
from ..domain.holdings import Holding, normalize_holding
from ..parsing.xlsx_parser import parse_portfolio_xlsx
from ..providers.holdings import fetch_holdings, load_holdings_config
from ..providers.yahoo import (
    get_price_eur,
    get_stock_sector_country,
    get_usd_eur_rate,
    is_etf,
)

_FALLBACK_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

# Explicit schema for the assembled holdings DataFrame. Declaring it
# keeps column names and dtypes stable even when the join with the
# weights frame yields no rows (e.g. nothing could be priced), so
# downstream consumers never hit a schema-less ColumnNotFoundError.
_HOLDINGS_SCHEMA: Final[dict[str, pl.DataType]] = {
    "name": pl.Utf8(),
    "ticker": pl.Utf8(),
    "sector": pl.Utf8(),
    "location": pl.Utf8(),
    "source_isin": pl.Utf8(),
    "weight_pct": pl.Float64(),
}


def get_position_values(
    df_portfolio: pl.DataFrame, logger: logging.Logger | None = None
) -> dict[str, float]:
    """
    Get current market value in EUR for each portfolio position.

    Queries Yahoo Finance (via the shared price helper) for the
    latest price of each ISIN and converts USD-denominated prices to
    EUR. Positions whose price cannot be retrieved are skipped.

    Args:
        df_portfolio: DataFrame with columns Producto, Symbol/ISIN,
            Cantidad.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        Dict mapping ISIN to market value in EUR. Only successfully
        priced positions are present.
    """

    eur_rate = get_usd_eur_rate(logger=logger)
    values: dict[str, float] = {}

    for _product, isin, quantity in df_portfolio.iter_rows():
        price = get_price_eur(isin, eur_rate, logger=logger)

        if price is None:
            continue

        values[isin] = quantity * price

    return values


def fetch_stock_holding(
    product: str, isin: str, logger: logging.Logger | None = None
) -> Holding:
    """
    Create a passthrough holding for an individual stock position.

    Enriches the stock with sector and country data from Yahoo
    Finance and canonicalizes it through the shared normalization
    step. If enrichment fails, the holding keeps empty sector and
    location fields.

    Args:
        product: Product name from Degiro.
        isin: ISIN of the stock.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        Canonical Holding with weight_pct=100 representing the stock
        itself.
    """

    sector, country = get_stock_sector_country(isin, logger=logger)

    return normalize_holding(
        Holding(
            name=product,
            ticker=isin,
            sector=sector,
            weight_pct=100.0,
            location=country,
            source_isin=isin,
        )
    )


def compute_portfolio_weights(
    df_portfolio: pl.DataFrame, logger: logging.Logger | None = None
) -> dict[str, float]:
    """
    Compute each position's share of the priced portfolio value.

    Market values are fetched and normalized into weight fractions
    over the successfully-priced positions only. Positions whose
    price could not be retrieved are excluded from the weight base,
    so the returned fractions sum to ~1.0 across priced positions
    (or the mapping is empty when nothing could be priced).

    Args:
        df_portfolio: DataFrame with columns Producto, Symbol/ISIN,
            Cantidad.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        Dict mapping ISIN to its weight fraction of the priced
        portfolio value. Empty when no position could be priced.
    """

    values = get_position_values(df_portfolio, logger=logger)
    total_value = sum(values.values())

    if total_value <= 0:
        return {}

    return {isin: value / total_value for isin, value in values.items()}


def collect_holdings(
    df_portfolio: pl.DataFrame,
    holdings_map: dict[str, Path],
    logger: logging.Logger | None = None,
) -> list[Holding]:
    """
    Build the flat list of underlying holdings for every position.

    Configured ETFs expand into their underlying holdings; individual
    stocks pass through with weight_pct=100%. ETFs without a config
    entry emit a warning and are skipped. All returned holdings are
    canonical (normalization is applied at the providers boundary).

    Args:
        df_portfolio: DataFrame with columns Producto, Symbol/ISIN,
            Cantidad.
        holdings_map: Mapping of ISIN to its holdings file path.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        List of Holding objects across all expandable positions.
    """

    log = logger if logger is not None else _FALLBACK_LOGGER
    all_holdings: list[Holding] = []

    for product, isin, _qty in df_portfolio.iter_rows():
        if isin in holdings_map:
            all_holdings.extend(fetch_holdings(isin, holdings_map[isin], logger=logger))

        elif is_etf(product):
            log.warning(
                "No holdings file configured for ETF %s (%s).",
                product.strip(),
                isin,
            )

        else:
            all_holdings.append(fetch_stock_holding(product, isin, logger=logger))

    return all_holdings


def build_holdings_dataframe(
    all_holdings: list[Holding],
    weights: dict[str, float],
    logger: logging.Logger | None = None,
) -> pl.DataFrame:
    """
    Assemble the final holdings DataFrame with effective weights.

    Holdings are assumed already canonical. Effective weights are
    computed only for holdings whose source position was priced; any
    holding whose source ISIN is absent from ``weights`` is dropped
    from the result (inner join) and a prominent warning lists the
    missing ISINs. Effective weights are therefore relative to the
    priced holdings, never silently diluted to zero.

    Args:
        all_holdings: Canonical holdings across all positions.
        weights: Mapping of source ISIN to portfolio weight fraction
            over the priced positions.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        DataFrame with columns name, ticker, sector, location,
        source_isin, weight_pct, portfolio_weight and effective_pct.

    Raises:
        ValueError: If no holdings could be loaded for any position.
    """

    log = logger if logger is not None else _FALLBACK_LOGGER

    if not all_holdings:
        error_message = (
            "No holdings could be loaded for any position. Check the "
            "portfolio file and the holdings JSON configuration."
        )
        log.error(error_message)
        raise ValueError(error_message)

    priced_isins = set(weights)
    holding_isins = {holding.source_isin for holding in all_holdings}
    missing_isins = sorted(holding_isins - priced_isins)

    if missing_isins:
        log.warning(
            "Effective weights are relative to priced holdings only. "
            "No price for %d position(s): %s. Their holdings are excluded "
            "from the portfolio weight base.",
            len(missing_isins),
            ", ".join(missing_isins),
        )

    df_holdings = pl.DataFrame(
        [
            {
                "name": h.name,
                "ticker": h.ticker,
                "sector": h.sector,
                "location": h.location,
                "source_isin": h.source_isin,
                "weight_pct": h.weight_pct,
            }
            for h in all_holdings
        ],
        schema=_HOLDINGS_SCHEMA,
    )

    df_weights = pl.DataFrame(
        {
            "source_isin": list(weights.keys()),
            "portfolio_weight": list(weights.values()),
        },
        schema={"source_isin": pl.Utf8(), "portfolio_weight": pl.Float64()},
    )

    df_priced = df_holdings.join(df_weights, on="source_isin", how="inner")
    effective_pct = (
        pl.col("weight_pct") / 100.0 * pl.col("portfolio_weight") * 100.0
    ).alias("effective_pct")

    return df_priced.with_columns(effective_pct)


def load_portfolio_holdings(
    xlsx_path: Path, config_path: Path, logger: logging.Logger | None = None
) -> pl.DataFrame:
    """
    Build a unified DataFrame of all underlying holdings with their
    effective portfolio weights.

    Reads the holdings config JSON to locate files for each ETF.
    Individual stocks pass through with weight_pct=100%. ETFs without
    a config entry emit a warning and are skipped. Holdings arrive
    already canonical from the providers boundary.

    Effective weights are computed over the successfully-priced
    positions only: holdings whose source position has no price are
    excluded and reported via a warning, so the remaining effective
    weights stay relative to the priced holdings.

    The returned DataFrame contains columns:
        - name, ticker, sector, location, source_isin, weight_pct
        - portfolio_weight (fraction of priced portfolio value)
        - effective_pct (weight_pct/100 * portfolio_weight * 100)

    Args:
        xlsx_path: Path to Portfolio.xlsx exported from Degiro.
        config_path: Path to holdings JSON config mapping ISIN to
            holdings file paths.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        DataFrame with all priced holdings and their effective
        portfolio weight.

    Raises:
        ValueError: If no holdings could be loaded for any position.
    """

    df_portfolio = parse_portfolio_xlsx(xlsx_path)
    holdings_map = load_holdings_config(config_path)

    weights = compute_portfolio_weights(df_portfolio, logger=logger)
    all_holdings = collect_holdings(df_portfolio, holdings_map, logger=logger)

    return build_holdings_dataframe(all_holdings, weights, logger=logger)
