# Standard libraries
from typing import Any

# 3pps
import polars as pl
import yfinance as yf

# Own modules
from ..domain.constants import ETF_LIST_NAME, ISIN_MAPPING
from ..domain.portfolio import DatasetOutputFormat


def get_ticker_from_isin(isin: str) -> str | None:
    """
    Busca el ticker de Yahoo Finance a partir de un ISIN.

    Utiliza la API de búsqueda de yfinance limitando a un único resultado
    para obtener el símbolo más relevante.

    Args:
        isin: Código ISIN del instrumento financiero.

    Returns:
        Símbolo del ticker en Yahoo Finance, o ``None`` si no se encuentra
        ningún resultado.
    """

    busqueda = yf.Search(isin, max_results=1, news_count=0)
    if busqueda.quotes:
        result: str = busqueda.quotes[0]["symbol"]
        return result
    return None


def dolar_to_euro() -> float:
    """
    Obtiene el tipo de cambio USD→EUR actual desde Yahoo Finance.

    Consulta el par ``USDEUR=X`` para obtener el último precio disponible.

    Returns:
        Tipo de cambio USD→EUR como float.

    Raises:
        Exception: Si no se puede obtener el tipo de cambio (sin conexión,
            ticker no disponible).
    """

    price: float = yf.Ticker("USDEUR=X").fast_info["lastPrice"]
    return price


def obtain_product_type(product: str) -> str:
    """
    Clasifica un producto como ETF o Acción según su nombre.

    Compara la primera palabra del nombre del producto contra la lista de
    proveedores de ETF conocidos (``ETF_LIST_NAME``).

    Args:
        product: Nombre descriptivo del producto tal como aparece en Degiro.

    Returns:
        ``"ETF"`` si el proveedor coincide, ``"Accion"`` en caso contrario.
    """

    if product.split(" ", maxsplit=1)[0].lower() in ETF_LIST_NAME:
        return "ETF"
    return "Accion"


def obtain_yahoo_info(df_input: pl.DataFrame) -> pl.DataFrame:
    """
    Enriquece el DataFrame de posiciones con precios actuales de Yahoo Finance.

    Para cada posición, resuelve el ticker vía ISIN, obtiene el último precio,
    lo convierte a EUR si la divisa es USD, y calcula el importe invertido.

    Args:
        df_input: DataFrame con columnas ``Producto``, ``Symbol/ISIN`` y
            ``Cantidad`` (salida de ``parse_portfolio_xlsx``).

    Returns:
        DataFrame con columnas adicionales: tipo de producto, precio unitario
        en EUR y cantidad invertida en EUR.

    Raises:
        Exception: Si no se puede obtener información de algún ticker.
    """

    dolar_to_euro_conv: float = dolar_to_euro()
    data: list[dict[str, Any]] = []
    output = DatasetOutputFormat()

    for product, isin, quantity in df_input.iter_rows():
        isin_yahoo = ISIN_MAPPING.get(isin, isin)
        isin_data = yf.Ticker(get_ticker_from_isin(isin_yahoo))
        product_type: str = obtain_product_type(product=product)

        try:
            currency = isin_data.fast_info["currency"]
            last_price = isin_data.fast_info["lastPrice"]
        except Exception:
            currency = isin_data.info.get("currency")
            last_price = isin_data.info.get("regularMarketPreviousClose")
        finally:
            last_price_adjusted: float = (
                last_price * dolar_to_euro_conv if currency == "USD" else last_price
            )
            quantity_invested: float = quantity * last_price_adjusted

        data.append(
            {
                output.product_column_name: product,
                output.isin_column_name: isin,
                output.product_type_column_name: product_type,
                output.quantity_column_name: quantity,
                output.product_price_column_name: last_price_adjusted,
                output.quantity_invested_column_name: quantity_invested,
            }
        )

    return pl.DataFrame(data)


def compute_portfolio_percentage(df_input: pl.DataFrame) -> pl.DataFrame:
    """
    Añade columnas de total invertido y porcentaje de cartera por posición.

    Calcula la suma total invertida y el peso relativo de cada posición
    sobre el total de la cartera.

    Args:
        df_input: DataFrame con columna ``Invertido €`` (salida de
            ``obtain_yahoo_info``).

    Returns:
        DataFrame con columnas adicionales ``Total €`` (suma global) y
        ``Porcentaje Cartera`` (peso de cada posición en %).
    """

    output = DatasetOutputFormat()
    return df_input.with_columns(
        pl.col(output.quantity_invested_column_name)
        .sum()
        .alias(output.total_quantity_invested_column_name)
    ).with_columns(
        (
            (
                pl.col(output.quantity_invested_column_name)
                / pl.col(output.total_quantity_invested_column_name)
            )
            * 100
        ).alias(output.percentage_wallet_column_name)
    )
