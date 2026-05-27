# Standard libraries
from dataclasses import dataclass


@dataclass
class DatasetInputFormat:
    """
    Configuración de nombres de columna del XLSX de Portfolio de Degiro.

    Define las columnas que se seleccionan del fichero de entrada para
    identificar cada posición y su cantidad.

    Attributes:
        product_column_name: Nombre de la columna con el nombre del producto.
        isin_column_name: Nombre de la columna con el ISIN del instrumento.
        quantity_column_name: Nombre de la columna con la cantidad de unidades.
    """

    product_column_name: str = "Producto"
    isin_column_name: str = "Symbol/ISIN"
    quantity_column_name: str = "Cantidad"


@dataclass
class DatasetOutputFormat:
    """
    Configuración de nombres de columna del DataFrame de salida de portfolio.

    Define los nombres de todas las columnas generadas durante el proceso de
    enriquecimiento y cálculo de porcentajes.

    Attributes:
        product_column_name: Nombre del producto.
        isin_column_name: ISIN del instrumento.
        product_type_column_name: Clasificación (ETF o Accion).
        quantity_column_name: Cantidad de unidades.
        product_price_column_name: Precio unitario actual en EUR.
        quantity_invested_column_name: Importe invertido en EUR.
        total_quantity_invested_column_name: Suma total invertida en EUR.
        percentage_wallet_column_name: Peso de la posición sobre el total (%).
    """

    product_column_name: str = "Producto"
    isin_column_name: str = "Symbol/ISIN"
    product_type_column_name: str = "Tipo"
    quantity_column_name: str = "Cantidad"
    product_price_column_name: str = "Precio €"
    quantity_invested_column_name: str = "Invertido €"
    total_quantity_invested_column_name: str = "Total €"
    percentage_wallet_column_name: str = "Porcentaje Cartera"
