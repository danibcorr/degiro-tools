# Standard libraries
import logging
from pathlib import Path
from typing import Final

# Own modules
from ...domain.holdings import Holding
from .helpers import (
    build_holdings_from_rows,
    find_header_row_with,
    index_of,
    read_xlsx_table,
)

_FALLBACK_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

# Distinctive header labels that identify a Vanguard holdings export.
_SIGNATURE: Final[frozenset[str]] = frozenset(
    {"Holding name", "% of market value", "Region"}
)


class VanguardParser:
    """
    Parser for Vanguard XLSX holdings exports.

    Vanguard files carry several metadata rows before a header row
    with columns ``Ticker``, ``Holding name``, ``% of market
    value``, ``Sector`` and ``Region``. Weights are percentage
    strings such as "4.2547%" and the region is a two-letter ISO
    country code.

    Attributes:
        name: Provider identifier.
    """

    name: Final[str] = "vanguard"

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """
        Initialize the parser with an optional injected logger.

        Args:
            logger: Optional logger for diagnostics; falls back to a
                module-level logger when omitted.
        """

        self._logger = logger if logger is not None else _FALLBACK_LOGGER

    def can_parse(self, path: Path) -> bool:
        """
        Detect a Vanguard export by its header signature.

        Args:
            path: Path to the candidate holdings file.

        Returns:
            True if the file is an XLSX with the Vanguard header.
        """

        if path.suffix.lower() != ".xlsx":
            return False

        table = read_xlsx_table(path)

        return find_header_row_with(table, _SIGNATURE) is not None

    def parse(self, path: Path, isin: str) -> list[Holding]:
        """
        Parse a Vanguard XLSX file into holdings.

        Args:
            path: Path to the .xlsx file.
            isin: Source ETF ISIN for attribution.

        Returns:
            List of Holding objects.
        """

        table = read_xlsx_table(path)

        header_idx = find_header_row_with(table, _SIGNATURE)
        if header_idx is None:
            self._logger.warning("No Vanguard header row found in %s.", path)
            return []

        headers = table[header_idx]
        indices: dict[str, int | None] = {
            "name": index_of(headers, "Holding name"),
            "ticker": index_of(headers, "Ticker"),
            "sector": index_of(headers, "Sector"),
            "weight": index_of(headers, "% of market value"),
            "location": index_of(headers, "Region"),
            "asset_class": None,
        }

        return build_holdings_from_rows(table, header_idx, indices, isin)
