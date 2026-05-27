# Standard libraries
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

# 3pps
import polars as pl
import yfinance as yf
from yfinance.base import TickerBase

ISIN_MAPPING: Final[dict[str, str]] = {"IE000I8KRLL9": "SEMI.AS"}


ETF_LIST_NAME: Final[tuple[str, ...]] = (
    "ishares",
    "vanguard",
    "xtrackers",
    "spdr",
    "amundi",
    "lyxor",
    "invesco",
    "hsbc",
    "fidelity",
    "wisdomtree",
    "vaneck",
    "schwab",
    "global x",
    "state street",
    "dimensional",
    "first trust",
    "j.p. morgan",
    "goldman sachs",
    "ubs",
    "franklin templeton",
)


@dataclass
class DatasetInputFormat:
    product_column_name: str = "Producto"
    isin_column_name: str = "Symbol/ISIN"
    quantity_column_name: str = "Cantidad"


@dataclass
class DatasetOutputFormat:
    product_column_name: str = "Producto"
    isin_column_name: str = "Symbol/ISIN"
    product_type_column_name: str = "Tipo"
    quantity_column_name: str = "Cantidad"
    product_price_column_name: str = "Precio €"
    quantity_invested_column_name: str = "Invertido €"
    total_quantity_invested_column_name: str = "Total €"
    percentage_wallet_column_name: str = "Porcentaje Cartera"


def get_ticker_from_isin(isin: str) -> str | None:
    """
    _summary_

    Args:
        isin (str): _description_

    Returns:
        str | None: _description_
    """

    # Configuramos para que solo traiga 1 resultado y nada de noticias
    busqueda = yf.Search(isin, max_results=1, news_count=0)

    if busqueda.quotes:
        # El primer resultado suele ser el más relevante
        return busqueda.quotes[0]["symbol"]

    return None


def read_degiro_xlsx(path: Path) -> pl.DataFrame:
    """
    _summary_

    Args:
        path (Path): _description_

    Returns:
        pl.DataFrame: _description_
    """

    input_dataset_config = DatasetInputFormat()

    return (
        pl.read_excel(path)
        .select(list(asdict(input_dataset_config).values()))
        .filter(pl.col(input_dataset_config.quantity_column_name).is_not_null())
    )


def dolar_to_euro() -> float:
    """
    _summary_

    Returns:
        float: _description_
    """

    return yf.Ticker("USDEUR=X").fast_info["lastPrice"]


def obtain_product_type(product: str) -> str:
    """_summary_

    Returns:
        str: _description_
    """

    if product.split(" ")[0].lower() in ETF_LIST_NAME:
        return "ETF"
    else:
        return "Accion"


def obtain_yahoo_info(df_input: pl.DataFrame) -> pl.DataFrame:
    """
    _summary_

    Args:
        df_input (pl.DataFrame): _description_

    Returns:
        pl.DataFrame: _description_
    """

    dolar_to_euro_conv: float = dolar_to_euro()

    data: list[dict[str, Any]] = []
    currency: str
    last_price: float

    for product, isin, quantity in df_input.iter_rows():
        isin_yahoo = ISIN_MAPPING.get(isin, isin)

        isin_data: TickerBase = yf.Ticker(get_ticker_from_isin(isin_yahoo))
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
                DatasetOutputFormat.product_column_name: product,
                DatasetOutputFormat.isin_column_name: isin,
                DatasetOutputFormat.product_type_column_name: product_type,
                DatasetOutputFormat.quantity_column_name: quantity,
                DatasetOutputFormat.product_price_column_name: last_price_adjusted,
                DatasetOutputFormat.quantity_invested_column_name: quantity_invested,
            }
        )

    return pl.DataFrame(data)


def compute_portfolio_percentage(df_input: pl.DataFrame) -> pl.DataFrame:
    """
    _summary_

    Args:
        df_input (pl.DataFrame): _description_

    Returns:
        pl.DataFrame: _description_
    """

    return df_input.with_columns(
        pl.col(DatasetOutputFormat.quantity_invested_column_name)
        .sum()
        .alias(DatasetOutputFormat.total_quantity_invested_column_name)
    ).with_columns(
        (
            (
                pl.col(DatasetOutputFormat.quantity_invested_column_name)
                / pl.col(DatasetOutputFormat.total_quantity_invested_column_name)
            )
            * 100
        ).alias(DatasetOutputFormat.percentage_wallet_column_name)
    )


def main(file_input_path: Path) -> None:
    """
    _summary_

    Args:
        file_input_path (Path): _description_
    """

    df: pl.DataFrame = read_degiro_xlsx(path=file_input_path)

    df_with_info: pl.DataFrame = obtain_yahoo_info(df_input=df)

    df_output: pl.DataFrame = compute_portfolio_percentage(df_input=df_with_info)

    print(df_output)


if __name__ == "__main__":
    main(file_input_path=Path("Portfolio.xlsx"))
