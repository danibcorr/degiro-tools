# Standard libraries
import logging
from pathlib import Path
from typing import Final

# Own modules
from ...domain.holdings import Holding
from .helpers import (
    find_header_row_with,
    get_cell,
    index_of,
    parse_weight,
    read_xlsx_table,
)

_FALLBACK_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)

# Distinctive header labels that identify an Xtrackers/DWS export.
_SIGNATURE: Final[frozenset[str]] = frozenset({"Name", "ISIN", "Type of Security"})

# Value of the "Type of Security" column that marks an equity row.
_EQUITY_TYPE: Final[str] = "Renta Variable"

# Factor to turn the fractional "Weighting" column into a percentage.
_FRACTION_TO_PCT: Final[float] = 100.0


class XtrackersParser:
    """
    Parser for Xtrackers/DWS constituent XLSX exports.

    DWS constituent files start with a Spanish disclaimer row,
    followed by a header whose first cell is an empty index column.
    Only equity rows (``Type of Security`` equal to "Renta
    Variable") are kept; cash, rights and futures are discarded.

    Weight handling: when the fractional ``Weighting`` column is
    present its values are converted to percentages (multiplied by
    100). When no usable weight is available, each equity is
    assigned an equal weight (``100 / number_of_equities``) so that
    downstream overlap, sector and geography analysis still works.

    Country names are emitted in their raw Spanish form; the
    ``COUNTRY_MAP`` normalization applied downstream maps them to
    English. The sector is read from the ``Industry
    Classification`` column (whitespace-stripped) as a raw Spanish
    sub-industry label; the ``SECTOR_MAP`` normalization applied
    downstream maps it to the canonical GICS top-level sector.

    Attributes:
        name: Provider identifier.
    """

    name: Final[str] = "xtrackers"

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
        Detect an Xtrackers/DWS export by its header signature.

        Args:
            path: Path to the candidate holdings file.

        Returns:
            True if the file is an XLSX with the Xtrackers header.
        """

        if path.suffix.lower() != ".xlsx":
            return False

        table = read_xlsx_table(path)

        return find_header_row_with(table, _SIGNATURE) is not None

    def parse(self, path: Path, isin: str) -> list[Holding]:
        """
        Parse an Xtrackers/DWS XLSX file into equity holdings.

        Args:
            path: Path to the .xlsx file.
            isin: Source ETF ISIN for attribution.

        Returns:
            List of equity Holding objects.
        """

        table = read_xlsx_table(path)

        header_idx = find_header_row_with(table, _SIGNATURE)
        if header_idx is None:
            self._logger.warning("No Xtrackers header row found in %s.", path)
            return []

        headers = table[header_idx]
        name_idx = index_of(headers, "Name")
        country_idx = index_of(headers, "Country")
        sector_idx = index_of(headers, "Industry Classification")
        type_idx = index_of(headers, "Type of Security")
        weight_idx = index_of(headers, "Weighting")

        equity_rows = [
            cells
            for cells in table[header_idx + 1 :]
            if get_cell(cells, type_idx) == _EQUITY_TYPE and get_cell(cells, name_idx)
        ]

        if not equity_rows:
            self._logger.warning("No equity rows found in %s.", path)
            return []

        weights = self.resolve_weights(equity_rows, weight_idx)

        return [
            Holding(
                name=get_cell(cells, name_idx),
                ticker="",
                sector=get_cell(cells, sector_idx).strip(),
                weight_pct=weight,
                location=get_cell(cells, country_idx),
                source_isin=isin,
            )
            for cells, weight in zip(equity_rows, weights, strict=True)
        ]

    @staticmethod
    def resolve_weights(
        equity_rows: list[list[str]], weight_idx: int | None
    ) -> list[float]:
        """
        Resolve equity weights with an all-or-nothing file decision.

        The choice between real and equal weights is made once for
        the whole file, never per row. Real weights are used only
        when the ``Weighting`` column is present and every equity
        row carries a parseable positive value; otherwise every
        equity gets the same equal weight (``100 / n``).

        Args:
            equity_rows: Equity rows kept from the file.
            weight_idx: Index of the Weighting column, or None.

        Returns:
            List of weight percentages aligned with ``equity_rows``.
        """

        # Changed: decide real-vs-equal once at file level - Reason:
        # the old per-row fallback mixed 100/n with fraction*100,
        # producing portfolio weights far above 100% on partial data.
        equal_weight = _FRACTION_TO_PCT / len(equity_rows)

        if weight_idx is None:
            return [equal_weight] * len(equity_rows)

        raw_weights = [
            parse_weight(get_cell(cells, weight_idx)) for cells in equity_rows
        ]

        if all(weight is not None and weight > 0 for weight in raw_weights):
            return [
                weight * _FRACTION_TO_PCT
                for weight in raw_weights
                if weight is not None
            ]

        return [equal_weight] * len(equity_rows)
