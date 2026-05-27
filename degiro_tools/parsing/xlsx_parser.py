# Standard libraries
from dataclasses import asdict
from pathlib import Path

# 3pps
import polars as pl

# Own modules
from ..domain.portfolio import DatasetInputFormat


def parse_portfolio_xlsx(path: Path) -> pl.DataFrame:
    """
    Lee un XLSX de Portfolio Degiro y devuelve las posiciones con cantidad > 0.

    Selecciona únicamente las columnas definidas en ``DatasetInputFormat`` y
    descarta filas sin cantidad (posiciones cerradas o vacías).

    Args:
        path: Ruta al fichero Portfolio.xlsx exportado desde Degiro.

    Returns:
        DataFrame de Polars con columnas ``Producto``, ``Symbol/ISIN`` y
        ``Cantidad``, filtrado a posiciones activas.

    Raises:
        FileNotFoundError: Si el fichero no existe en la ruta indicada.
        polars.exceptions.SchemaError: Si el XLSX no contiene las columnas
            esperadas.
    """

    config = DatasetInputFormat()
    return (
        pl.read_excel(path)
        .select(list(asdict(config).values()))
        .filter(pl.col(config.quantity_column_name).is_not_null())
    )
