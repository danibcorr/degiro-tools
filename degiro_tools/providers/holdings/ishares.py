# Standard libraries
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Final

# 3pps
import defusedxml.ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

# Own modules
from ...domain.holdings import Holding
from .helpers import (
    build_holdings_from_rows,
    extract_xml_rows,
    find_header_row,
    resolve_indices,
)

_FALLBACK_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

# Number of leading bytes inspected for content-based detection.
_SNIFF_BYTES: Final[int] = 4096

# Fields resolved from the iShares header via the alias catalogue.
_FIELDS: Final[list[str]] = [
    "name",
    "ticker",
    "sector",
    "weight",
    "location",
    "asset_class",
]


class ISharesParser:
    """
    Parser for iShares XML SpreadsheetML exports (.xls).

    iShares exports .xls files that are actually XML in Microsoft's
    SpreadsheetML format. The header is located via the generic
    alias catalogue and only equity rows are kept.

    Attributes:
        name: Provider identifier.
    """

    name: Final[str] = "ishares"

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
        Detect SpreadsheetML content by sniffing the file header.

        Args:
            path: Path to the candidate holdings file.

        Returns:
            True if the file looks like a SpreadsheetML document.
        """

        if path.suffix.lower() != ".xls":
            return False

        try:
            head = path.read_bytes()[:_SNIFF_BYTES].lower()
        except OSError:
            return False

        return b"spreadsheet" in head and b"<?xml" in head

    def parse(self, path: Path, isin: str) -> list[Holding]:
        """
        Parse an iShares SpreadsheetML file into holdings.

        Args:
            path: Path to the .xls file.
            isin: Source ETF ISIN for attribution.

        Returns:
            List of equity Holding objects.
        """

        content = path.read_text(encoding="utf-8-sig").lstrip("\ufeff")

        # Fix common XML issues in iShares exports
        content = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", content)

        try:
            # Changed: parse with defusedxml instead of stdlib ElementTree
            # - Reason: harden against XXE / billion-laughs entity attacks
            # on externally downloaded files (Bandit B314).
            root = DefusedET.fromstring(content)
        except (ET.ParseError, DefusedXmlException):
            self._logger.warning("Could not parse XML in %s.", path)
            return []

        table = extract_xml_rows(root)

        header_idx = find_header_row(table)
        if header_idx is None:
            self._logger.warning("No header row found in XML file %s.", path)
            return []

        headers = table[header_idx]
        indices = resolve_indices(headers, _FIELDS)

        if indices["name"] is None or indices["weight"] is None:
            self._logger.warning("Missing Name/Weight columns in %s.", path)
            return []

        return build_holdings_from_rows(
            table, header_idx, indices, isin, filter_equity=True
        )
