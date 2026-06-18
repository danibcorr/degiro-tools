# Standard libraries
import logging

# 3pps
import yfinance as yf

# Own modules
from ..domain.constants import ETF_LIST_NAME, ISIN_MAPPING

logger = logging.getLogger(__name__)


def get_ticker_from_isin(isin: str) -> str | None:
    """
    Resolve a Yahoo Finance ticker symbol from an ISIN.

    Applies manual overrides from ISIN_MAPPING first, then falls
    back to yfinance search.

    Args:
        isin: ISIN code of the instrument.

    Returns:
        Ticker symbol, or None if not found.
    """

    resolved_isin = ISIN_MAPPING.get(isin, isin)
    search = yf.Search(resolved_isin, max_results=1, news_count=0)

    if search.quotes:
        result: str = search.quotes[0]["symbol"]
        return result

    return None


def get_usd_eur_rate() -> float:
    """
    Get the current USD to EUR exchange rate from Yahoo Finance.

    Returns:
        USD to EUR conversion rate as float.
    """

    price: float = yf.Ticker("USDEUR=X").fast_info["lastPrice"]
    return price


def is_etf(product_name: str) -> bool:
    """
    Determine if a product is an ETF based on its name prefix.

    Checks whether the first word of the product name matches any
    known ETF provider (iShares, Vanguard, Amundi, etc.).

    Args:
        product_name: Product name from the portfolio.

    Returns:
        True if the product matches a known ETF provider name.
    """

    first_word = product_name.split(" ", maxsplit=1)[0].lower()
    return first_word in ETF_LIST_NAME
