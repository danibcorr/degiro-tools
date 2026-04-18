# Standard libraries
import importlib.metadata

# Own modules
from .calculation import (
    TRAMOS_AHORRO,
    build_informe_data,
    calcular_cuota_irpf,
    calcular_fifo,
)
from .domain import InformeData, Lote, Operacion, TipoOperacion, TramoCuota, Venta
from .parsing import parse_csv
from .reporting import imprimir_informe

__version__: str = importlib.metadata.version("degiro_calculator")

__all__: list[str] = [
    "InformeData",
    "Lote",
    "Operacion",
    "TRAMOS_AHORRO",
    "TipoOperacion",
    "TramoCuota",
    "Venta",
    "__version__",
    "build_informe_data",
    "calcular_cuota_irpf",
    "calcular_fifo",
    "imprimir_informe",
    "parse_csv",
]
