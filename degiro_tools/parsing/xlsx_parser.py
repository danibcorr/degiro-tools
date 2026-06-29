# Standard libraries
from pathlib import Path

# 3pps
import polars as pl

# Own modules
from ..domain.portfolio import INPUT_ISIN_COL, INPUT_PRODUCT_COL, INPUT_QUANTITY_COL


def parse_portfolio_xlsx(path: Path) -> pl.DataFrame:
    """
    Read a Degiro Portfolio XLSX and return the active positions.

    Selects only the product, ISIN and quantity columns, discarding
    rows without a quantity (closed or empty positions).

    Args:
        path: Path to the Portfolio.xlsx file exported from Degiro.

    Returns:
        DataFrame with columns Producto, Symbol/ISIN and Cantidad,
        filtered to positions with a non-null quantity.
    """

    return (
        pl.read_excel(path)
        .select([INPUT_PRODUCT_COL, INPUT_ISIN_COL, INPUT_QUANTITY_COL])
        .filter(pl.col(INPUT_QUANTITY_COL).is_not_null())
    )
