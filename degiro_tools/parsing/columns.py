# Standard libraries
from typing import Final

# Column indices for the Degiro "Estado de cuenta" CSV export.
# Fecha,Hora,Fecha valor,Producto,ISIN,Descripción,FX,Divisa,
# Variación,...,ID Orden

FECHA_COL: Final[int] = 0
HORA_COL: Final[int] = 1
ISIN_COL: Final[int] = 4
DESCRIPCION_COL: Final[int] = 5
DIVISA_COL: Final[int] = 7
VARIACION_COL: Final[int] = 8
ID_ORDEN_COL: Final[int] = 11
