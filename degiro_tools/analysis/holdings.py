# Standard libraries
import logging
from pathlib import Path

# 3pps
import polars as pl
import yfinance as yf

# Own modules
from ..domain.constants import COUNTRY_MAP, SECTOR_MAP
from ..domain.holdings import Holding
from ..parsing.xlsx_parser import parse_portfolio_xlsx
from ..providers.holdings_csv import fetch_holdings, load_holdings_config
from ..providers.yahoo import get_ticker_from_isin, get_usd_eur_rate, is_etf

logger = logging.getLogger(__name__)


def get_position_values(df_portfolio: pl.DataFrame) -> dict[str, float]:
    """
    Get current market value in EUR for each portfolio position.

    Queries Yahoo Finance for the latest price of each ISIN and
    converts USD-denominated prices to EUR.

    Args:
        df_portfolio: DataFrame with columns Producto, Symbol/ISIN,
            Cantidad.

    Returns:
        Dict mapping ISIN to market value in EUR.
    """

    eur_rate: float | None = None
    values: dict[str, float] = {}

    for _product, isin, quantity in df_portfolio.iter_rows():
        try:
            ticker = get_ticker_from_isin(isin)

            if ticker is None:
                logger.warning("No ticker found for %s.", isin)
                continue

            fast_info = yf.Ticker(ticker).fast_info
            price = fast_info["lastPrice"]

            if fast_info["currency"] == "USD":
                if eur_rate is None:
                    eur_rate = get_usd_eur_rate()
                price *= eur_rate

        except (KeyError, AttributeError, ConnectionError):
            logger.warning("Price unavailable for %s.", isin)
            continue

        values[isin] = quantity * price

    return values


def fetch_stock_holding(product: str, isin: str) -> Holding:
    """
    Create a passthrough holding for an individual stock position.

    Enriches the stock with sector and country data from Yahoo
    Finance. If enrichment fails, returns the holding with empty
    sector and location fields.

    Args:
        product: Product name from Degiro.
        isin: ISIN of the stock.

    Returns:
        Holding with weight_pct=100 representing the stock itself.
    """

    sector = ""
    country = ""

    try:
        ticker = get_ticker_from_isin(isin)

        if ticker:
            info = yf.Ticker(ticker).info
            sector = info.get("sector", "")
            country = info.get("country", "")

    except (KeyError, AttributeError, ConnectionError):
        logger.warning("Could not enrich stock %s.", isin)

    return Holding(
        name=product,
        ticker=isin,
        sector=sector,
        weight_pct=100.0,
        location=country,
        source_isin=isin,
    )


def load_portfolio_holdings(xlsx_path: Path, config_path: Path) -> pl.DataFrame:
    """
    Build a unified DataFrame of all underlying holdings with their
    effective portfolio weights.

    Reads the holdings config JSON to locate CSV files for each ETF.
    Individual stocks pass through with weight_pct=100%. ETFs
    without a config entry emit a warning and are skipped.

    The returned DataFrame contains columns:
        - name, ticker, sector, location, source_isin, weight_pct
        - portfolio_weight (fraction of total portfolio value)
        - effective_pct (weight_pct/100 * portfolio_weight * 100)

    Args:
        xlsx_path: Path to Portfolio.xlsx exported from Degiro.
        config_path: Path to holdings JSON config mapping ISIN to
            CSV file paths.

    Returns:
        DataFrame with all holdings and their effective portfolio
        weight.
    """

    df_portfolio = parse_portfolio_xlsx(xlsx_path)
    holdings_map = load_holdings_config(config_path)

    # Compute portfolio weights from current market values
    values = get_position_values(df_portfolio)
    total_value = sum(values.values())

    weights = (
        {isin: val / total_value for isin, val in values.items()}
        if total_value > 0
        else {}
    )

    # Fetch holdings for each position
    all_holdings: list[Holding] = []

    for product, isin, _qty in df_portfolio.iter_rows():
        if isin in holdings_map:
            all_holdings.extend(fetch_holdings(isin, holdings_map[isin]))

        elif is_etf(product):
            logger.warning(
                "No holdings CSV configured for ETF %s (%s).",
                product.strip(),
                isin,
            )

        else:
            all_holdings.append(fetch_stock_holding(product, isin))

    # Build DataFrame with normalized sectors and countries
    df_holdings = pl.DataFrame(
        [
            {
                "name": h.name,
                "ticker": h.ticker,
                "sector": SECTOR_MAP.get(h.sector, h.sector),
                "location": COUNTRY_MAP.get(h.location, h.location),
                "source_isin": h.source_isin,
                "weight_pct": h.weight_pct,
            }
            for h in all_holdings
        ]
    )

    # Compute effective weights via join
    df_weights = pl.DataFrame(
        {
            "source_isin": list(weights.keys()),
            "portfolio_weight": list(weights.values()),
        }
    )

    df = (
        df_holdings.join(df_weights, on="source_isin", how="left")
        .with_columns(pl.col("portfolio_weight").fill_null(0.0))
        .with_columns(
            (pl.col("weight_pct") / 100.0 * pl.col("portfolio_weight") * 100.0).alias(
                "effective_pct"
            )
        )
    )

    return df
