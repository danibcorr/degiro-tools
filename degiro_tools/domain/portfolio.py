# Standard libraries
from typing import Final

# Column names for the Degiro Portfolio XLSX input
INPUT_PRODUCT_COL: Final[str] = "Producto"
INPUT_ISIN_COL: Final[str] = "Symbol/ISIN"
INPUT_QUANTITY_COL: Final[str] = "Cantidad"

# Column names for the enriched portfolio output
OUTPUT_PRODUCT_COL: Final[str] = "Producto"
OUTPUT_ISIN_COL: Final[str] = "Symbol/ISIN"
OUTPUT_TYPE_COL: Final[str] = "Tipo"
OUTPUT_QUANTITY_COL: Final[str] = "Cantidad"
OUTPUT_PRICE_COL: Final[str] = "Precio €"
OUTPUT_INVESTED_COL: Final[str] = "Invertido €"
OUTPUT_TOTAL_COL: Final[str] = "Total €"
OUTPUT_PERCENTAGE_COL: Final[str] = "Porcentaje Cartera"
