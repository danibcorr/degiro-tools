# Standard libraries
import importlib.metadata

# Own modules
from .calculation import (
    SAVINGS_BRACKETS,
    build_report_data,
    calculate_fifo,
    calculate_irpf_quota,
)
from .domain import Lot, Operation, OperationType, ReportData, Sale, TaxBracket
from .parsing import parse_account_xlsx
from .reporting import print_report

__version__: str = importlib.metadata.version("degiro_tools")

__all__: list[str] = [
    "Lot",
    "Operation",
    "OperationType",
    "ReportData",
    "SAVINGS_BRACKETS",
    "Sale",
    "TaxBracket",
    "__version__",
    "build_report_data",
    "calculate_fifo",
    "calculate_irpf_quota",
    "parse_account_xlsx",
    "print_report",
]
