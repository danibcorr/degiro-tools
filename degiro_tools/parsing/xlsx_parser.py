# Standard libraries
from pathlib import Path

# 3pps
import polars as pl

# Own modules
from ..domain.portfolio import INPUT_ISIN_COL, INPUT_PRODUCT_COL, INPUT_QUANTITY_COL


def parse_portfolio_xlsx(path: Path) -> pl.DataFrame:
    """
    Lee un XLSX de Portfolio Degiro y devuelve las posiciones activas.

    Selecciona únicamente las columnas de producto, ISIN y cantidad,
    descartando filas sin cantidad (posiciones cerradas o vacías).

    Args:
        path: Ruta al fichero Portfolio.xlsx exportado desde Degiro.

    Returns:
        DataFrame con columnas Producto, Symbol/ISIN y Cantidad,
        filtrado a posiciones con cantidad no nula.
    """

    return (
        pl.read_excel(path)
        .select([INPUT_PRODUCT_COL, INPUT_ISIN_COL, INPUT_QUANTITY_COL])
        .filter(pl.col(INPUT_QUANTITY_COL).is_not_null())
    )
