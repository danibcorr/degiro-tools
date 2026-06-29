# Standard libraries
import logging
from typing import Final

# 3pps
import yfinance as yf
from yfinance.exceptions import YFException

# Own modules
from ..domain.constants import ETF_LIST_NAME, ISIN_MAPPING

_FALLBACK_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

# Errors yfinance may raise on missing response fields or on network /
# HTTP failures. OSError is the common base of ConnectionError,
# TimeoutError, requests.RequestException and curl_cffi.RequestsError,
# so it covers every transport-level failure; KeyError / AttributeError
# cover missing payload fields and YFException covers yfinance-specific
# errors. Catching these lets callers degrade gracefully instead of
# crashing on real network problems.
_YAHOO_ERRORS: Final[tuple[type[Exception], ...]] = (
    KeyError,
    AttributeError,
    OSError,
    YFException,
)

# Currency code whose prices must be converted to EUR.
_USD: Final[str] = "USD"


def get_ticker_from_isin(isin: str, logger: logging.Logger | None = None) -> str | None:
    """
    Resolve a Yahoo Finance ticker symbol from an ISIN.

    Applies manual overrides from ISIN_MAPPING first, then falls
    back to yfinance search. Network or HTTP failures are logged and
    yield None instead of propagating.

    Args:
        isin: ISIN code of the instrument.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        Ticker symbol, or None if not found or the lookup failed.
    """

    log = logger if logger is not None else _FALLBACK_LOGGER
    resolved_isin = ISIN_MAPPING.get(isin, isin)

    try:
        search = yf.Search(resolved_isin, max_results=1, news_count=0)
    except _YAHOO_ERRORS as err:
        log.warning("Ticker search failed for %s: %s.", isin, err)
        return None

    if search.quotes:
        result: str = search.quotes[0]["symbol"]
        return result

    return None


def get_usd_eur_rate(logger: logging.Logger | None = None) -> float | None:
    """
    Get the current USD to EUR exchange rate from Yahoo Finance.

    Args:
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        USD to EUR conversion rate, or None if the rate could not be
        retrieved (a warning is logged in that case).
    """

    log = logger if logger is not None else _FALLBACK_LOGGER

    try:
        price: float = yf.Ticker("USDEUR=X").fast_info["lastPrice"]
        return price
    except _YAHOO_ERRORS as err:
        log.warning("Could not fetch USD/EUR exchange rate: %s.", err)
        return None


def fetch_price_and_currency(
    ticker: str, logger: logging.Logger | None = None
) -> tuple[float | None, str]:
    """
    Fetch the last price and currency for a Yahoo ticker.

    Tries the lightweight ``fast_info`` endpoint first and falls back
    to the fuller ``info`` payload (using the previous regular-market
    close) when fast data is unavailable. All failures are logged.

    Args:
        ticker: Yahoo Finance ticker symbol.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        Tuple of last price and currency code. The price is None when
        no quote could be retrieved; the currency is an empty string
        in that case.
    """

    log = logger if logger is not None else _FALLBACK_LOGGER
    ticker_data = yf.Ticker(ticker)

    try:
        fast_info = ticker_data.fast_info
        return fast_info["lastPrice"], fast_info["currency"]
    except _YAHOO_ERRORS as err:
        log.debug(
            "fast_info unavailable for %s (%s); falling back to info.",
            ticker,
            err,
        )

    try:
        info = ticker_data.info
        return info.get("regularMarketPreviousClose"), info.get("currency", "")
    except _YAHOO_ERRORS as err:
        log.warning("Could not fetch price for %s: %s.", ticker, err)
        return None, ""


def get_price_eur(
    isin: str, eur_rate: float | None, logger: logging.Logger | None = None
) -> float | None:
    """
    Resolve an ISIN to its last price expressed in EUR.

    Resolves the Yahoo ticker for the ISIN, fetches its last price
    and currency, and converts USD-denominated prices to EUR using
    ``eur_rate``. Every failure path logs a warning and yields None
    so callers can skip the position without crashing. This is the
    shared price-access helper used by both the portfolio valuation
    and the holdings analysis flows.

    Args:
        isin: ISIN code of the instrument.
        eur_rate: USD to EUR conversion rate, or None when it could
            not be retrieved.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        Last price in EUR, or None if the price (or a required
        conversion rate) could not be obtained.
    """

    log = logger if logger is not None else _FALLBACK_LOGGER
    ticker = get_ticker_from_isin(isin, logger=logger)

    if ticker is None:
        log.warning("No ticker found for %s.", isin)
        return None

    price, currency = fetch_price_and_currency(ticker, logger=logger)

    if price is None:
        log.warning("Price unavailable for %s.", isin)
        return None

    if currency == _USD:
        if eur_rate is None:
            log.warning(
                "Price for %s is in USD but no USD/EUR rate is available; "
                "skipping position.",
                isin,
            )
            return None

        price *= eur_rate

    return price


def get_stock_sector_country(
    isin: str, logger: logging.Logger | None = None
) -> tuple[str, str]:
    """
    Fetch the sector and domicile country for a single stock.

    Resolves the Yahoo ticker for the ISIN and reads its ``info``
    payload. Network or HTTP failures are logged and yield empty
    strings so enrichment never crashes the caller.

    Args:
        isin: ISIN code of the stock.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        Tuple of sector and country. Both are empty strings when the
        data could not be retrieved.
    """

    log = logger if logger is not None else _FALLBACK_LOGGER
    ticker = get_ticker_from_isin(isin, logger=logger)

    if ticker is None:
        log.warning("No ticker found for %s.", isin)
        return "", ""

    try:
        info = yf.Ticker(ticker).info
        return info.get("sector", ""), info.get("country", "")
    except _YAHOO_ERRORS as err:
        log.warning("Could not enrich stock %s: %s.", isin, err)
        return "", ""


def is_etf(product_name: str) -> bool:
    """
    Determine if a product is an ETF based on its provider name.

    Checks whether the normalized (lowercased) product name starts
    with, or contains as a whitespace-delimited phrase, any known
    ETF provider in ETF_LIST_NAME. This correctly handles
    multi-word brands such as "global x" or "goldman sachs", which
    a first-token comparison would miss.

    Args:
        product_name: Product name from the portfolio.

    Returns:
        True if the product matches a known ETF provider name.
    """

    normalized = product_name.lower().strip()
    padded = f" {normalized} "

    return any(
        normalized.startswith(brand) or f" {brand} " in padded
        for brand in ETF_LIST_NAME
    )
