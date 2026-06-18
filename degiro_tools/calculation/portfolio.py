# Standard libraries
import logging
from typing import Any

# 3pps
import polars as pl
import yfinance as yf

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
from ..providers.yahoo import get_ticker_from_isin, get_usd_eur_rate, is_etf

logger = logging.getLogger(__name__)


def obtain_yahoo_info(df_input: pl.DataFrame) -> pl.DataFrame:
    """
    Enriquece el DataFrame de posiciones con precios actuales.

    Para cada posición, resuelve el ticker vía ISIN, obtiene el
    último precio, lo convierte a EUR si la divisa es USD, y calcula
    el importe invertido.

    Args:
        df_input: DataFrame con columnas Producto, Symbol/ISIN y
            Cantidad (salida de parse_portfolio_xlsx).

    Returns:
        DataFrame con columnas adicionales: tipo de producto, precio
        unitario en EUR y cantidad invertida en EUR.
    """

    eur_rate: float = get_usd_eur_rate()
    data: list[dict[str, Any]] = []

    for product, isin, quantity in df_input.iter_rows():
        ticker = get_ticker_from_isin(isin)

        if ticker is None:
            logger.warning("No ticker found for %s.", isin)
            continue

        ticker_data = yf.Ticker(ticker)
        last_price: float | None = None
        currency: str = ""

        try:
            currency = ticker_data.fast_info["currency"]
            last_price = ticker_data.fast_info["lastPrice"]
        except (KeyError, AttributeError, ConnectionError):
            info = ticker_data.info
            currency = info.get("currency", "")
            last_price = info.get("regularMarketPreviousClose")

        if last_price is None:
            logger.warning("No price available for %s.", isin)
            continue

        price_eur = last_price * eur_rate if currency == "USD" else last_price
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
    Añade columnas de total invertido y porcentaje de cartera.

    Args:
        df_input: DataFrame con columna Invertido EUR (salida de
            obtain_yahoo_info).

    Returns:
        DataFrame con columnas adicionales Total EUR y Porcentaje
        Cartera.
    """

    return df_input.with_columns(
        pl.col(OUTPUT_INVESTED_COL).sum().alias(OUTPUT_TOTAL_COL)
    ).with_columns(
        (pl.col(OUTPUT_INVESTED_COL) / pl.col(OUTPUT_TOTAL_COL) * 100).alias(
            OUTPUT_PERCENTAGE_COL
        )
    )
