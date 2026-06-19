# Standard libraries
import json
import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

# 3pps
import polars as pl

# Own modules
from ..domain.holdings import Holding

logger = logging.getLogger(__name__)

COLUMN_ALIASES: dict[str, list[str]] = {
    "name": [
        "Name",
        "Nombre",
        "Nombre de emisor",
        "Holding name",
        "Security",
    ],
    "ticker": ["Ticker", "Símbolo", "Symbol", "Code"],
    "sector": ["Sector", "Industry"],
    "weight": [
        "Weight (%)",
        "Peso (%)",
        "% de valor de mercado",
        "Weight",
    ],
    "location": ["Location", "Localización", "Región", "Country"],
    "asset_class": ["Asset Class", "Clase de activo"],
}


def resolve_column(headers: Sequence[str], field: str) -> str | None:
    """
    Find the actual column name matching a logical field.

    Checks the header list against known aliases for each field.
    Returns the first match found.

    Args:
        headers: List of column names from the file.
        field: Logical field name to resolve.

    Returns:
        Matching column name from headers, or None if not found.
    """

    aliases = COLUMN_ALIASES.get(field, [])

    for alias in aliases:
        if alias in headers:
            return alias

    return None


def parse_weight(value: str) -> float | None:
    """
    Parse a weight percentage string in either US or EU format.

    Handles formats like "5.34", "5,34", "4,2547 %", "4.2547%".

    Args:
        value: Raw weight string from the file.

    Returns:
        Parsed float value, or None if unparseable.
    """

    cleaned = value.strip().replace("%", "").replace("\xa0", "").strip()

    if not cleaned:
        return None

    # European format: 1.234,56 -> remove dots, replace comma with dot
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        return float(cleaned)
    except ValueError:
        return None


def find_header_row(table: list[list[str]]) -> int | None:
    """
    Find the index of the header row in a table of string rows.

    Scans each row looking for any cell that matches a known column
    alias from ``COLUMN_ALIASES``.

    Args:
        table: List of rows, each row a list of cell strings.

    Returns:
        Index of the header row, or None if not found.
    """

    all_aliases = [
        alias for alias_list in COLUMN_ALIASES.values() for alias in alias_list
    ]

    for i, cells in enumerate(table):
        if any(alias in cells for alias in all_aliases):
            return i

    return None


def resolve_indices(
    headers: list[str],
    fields: list[str],
) -> dict[str, int | None]:
    """
    Resolve column indices for multiple logical fields.

    Args:
        headers: Row of column header strings.
        fields: Logical field names to resolve.

    Returns:
        Dict mapping field name to column index (or None if the
        field was not found in headers).
    """

    result: dict[str, int | None] = {}

    for field in fields:
        col = resolve_column(headers, field)
        result[field] = headers.index(col) if col else None

    return result


def extract_xml_rows(root: ET.Element) -> list[list[str]]:
    """
    Extract all rows from an XML SpreadsheetML document.

    Args:
        root: Parsed XML root element.

    Returns:
        List of rows, each row a list of cell text values.
    """

    ns = "urn:schemas-microsoft-com:office:spreadsheet"
    table: list[list[str]] = []

    for row in root.findall(f".//{{{ns}}}Row"):
        cells: list[str] = []
        for cell in row.findall(f"{{{ns}}}Cell"):
            data = cell.find(f"{{{ns}}}Data")
            cells.append(data.text if data is not None and data.text else "")
        table.append(cells)

    return table


def get_cell(cells: list[str], idx: int | None) -> str:
    """
    Safely extract a cell value by index.

    Args:
        cells: Row of string values.
        idx: Column index, or None if the column was not resolved.

    Returns:
        Cell value, or empty string if index is None or out of
        range.
    """

    if idx is not None and len(cells) > idx:
        return cells[idx]

    return ""


def is_non_equity(cells: list[str], asset_idx: int | None) -> bool:
    """
    Check whether a row should be excluded as non-equity.

    Args:
        cells: Row of string values.
        asset_idx: Index of the asset_class column, or None.

    Returns:
        True if the row has an asset class that is not Equity.
    """

    asset_val = get_cell(cells, asset_idx)

    return bool(asset_val and asset_val != "Equity")


def build_holdings_from_rows(
    table: list[list[str]],
    header_idx: int,
    indices: dict[str, int | None],
    isin: str,
    *,
    filter_equity: bool = False,
) -> list[Holding]:
    """
    Iterate data rows and build Holding objects.

    Shared logic for both XML and XLSX parsers. Skips rows without
    a valid positive weight or without a name.

    Args:
        table: All rows as lists of strings.
        header_idx: Index of the header row (data starts at +1).
        indices: Dict mapping field names to column indices.
        isin: Source ETF ISIN for attribution.
        filter_equity: If True, skip rows where asset_class column
            is present and not "Equity".

    Returns:
        List of Holding objects.
    """

    weight_idx = indices["weight"]
    if weight_idx is None:
        return []

    name_idx = indices["name"]
    ticker_idx = indices.get("ticker")
    sector_idx = indices.get("sector")
    location_idx = indices.get("location")
    asset_idx = indices.get("asset_class")

    holdings: list[Holding] = []

    for cells in table[header_idx + 1 :]:
        if len(cells) <= weight_idx:
            continue

        if filter_equity and is_non_equity(cells, asset_idx):
            continue

        weight = parse_weight(cells[weight_idx])
        if weight is None or weight <= 0:
            continue

        name = get_cell(cells, name_idx)
        if not name or name == "null":
            continue

        holdings.append(
            Holding(
                name=name,
                ticker=get_cell(cells, ticker_idx),
                sector=get_cell(cells, sector_idx),
                weight_pct=weight,
                location=get_cell(cells, location_idx),
                source_isin=isin,
            )
        )

    return holdings


def parse_xml_spreadsheet(path: Path, isin: str) -> list[Holding]:
    """
    Parse an iShares XML SpreadsheetML file (.xls) into holdings.

    iShares exports .xls files that are actually XML in Microsoft's
    SpreadsheetML format. This parser extracts rows from the XML
    structure and maps columns by alias.

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
        root = ET.fromstring(content)
    except ET.ParseError:
        logger.warning("Could not parse XML in %s.", path)
        return []

    table = extract_xml_rows(root)

    header_idx = find_header_row(table)
    if header_idx is None:
        logger.warning("No header row found in XML file %s.", path)
        return []

    headers = table[header_idx]
    indices = resolve_indices(
        headers,
        ["name", "ticker", "sector", "weight", "location", "asset_class"],
    )

    if indices["name"] is None or indices["weight"] is None:
        logger.warning("Missing Name/Weight columns in %s.", path)
        return []

    return build_holdings_from_rows(
        table, header_idx, indices, isin, filter_equity=True
    )


def parse_excel(path: Path, isin: str) -> list[Holding]:
    """
    Parse a standard XLSX holdings file (e.g. Vanguard) into holdings.

    Reads the first sheet, detects the header row by scanning for
    known column aliases, and parses subsequent rows.

    Args:
        path: Path to the .xlsx file.
        isin: Source ETF ISIN for attribution.

    Returns:
        List of Holding objects.
    """

    df_raw = pl.read_excel(path, has_header=False, infer_schema_length=0)

    table: list[list[str]] = [
        [str(v) if v else "" for v in df_raw.row(i)] for i in range(len(df_raw))
    ]

    header_idx = find_header_row(table)
    if header_idx is None:
        logger.warning("No header row found in %s.", path)
        return []

    headers = table[header_idx]
    indices = resolve_indices(
        headers, ["name", "ticker", "sector", "weight", "location"]
    )

    if indices["name"] is None or indices["weight"] is None:
        logger.warning("Missing Name/Weight columns in %s.", path)
        return []

    return build_holdings_from_rows(table, header_idx, indices, isin)


def parse_holdings_file(path: Path, isin: str) -> list[Holding]:
    """
    Parse a holdings file in any supported format.

    Detects the file type by extension and content, then dispatches
    to the appropriate parser (XML SpreadsheetML or XLSX).

    Args:
        path: Path to the holdings file (.xls or .xlsx).
        isin: Source ETF ISIN for attribution.

    Returns:
        List of Holding objects.
    """

    suffix = path.suffix.lower()

    if suffix == ".xls":
        return parse_xml_spreadsheet(path, isin)

    if suffix == ".xlsx":
        return parse_excel(path, isin)

    # Try as plain text CSV
    if suffix == ".csv":
        return parse_xml_spreadsheet(path, isin)

    logger.warning("Unsupported file format: %s.", path)
    return []


def load_holdings_config(config_path: Path) -> dict[str, Path]:
    """
    Load the ISIN-to-file-path mapping from a JSON config.

    The JSON must be a flat object mapping ISIN strings to file
    paths pointing to holdings files (.xls, .xlsx, or .csv).
    Relative paths are resolved against the config file's directory.

    Args:
        config_path: Path to the JSON configuration file.

    Returns:
        Dict mapping ISIN to resolved Path of the holdings file.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """

    if not config_path.exists():
        error_message = (
            f"Holdings config not found: {config_path}\n"
            f"Create a JSON file mapping ISIN to holdings file, e.g.:\n"
            f'{{"IE00B4L5Y983": "holdings/msci_world.xls"}}'
        )
        raise FileNotFoundError(error_message)

    raw = config_path.read_text(encoding="utf-8")
    data: dict[str, str] = json.loads(raw)
    base_dir = config_path.parent

    return {isin: base_dir / file_path for isin, file_path in data.items()}


def fetch_holdings(isin: str, file_path: Path) -> list[Holding]:
    """
    Load holdings for an ETF from its local file.

    Args:
        isin: ISIN of the ETF.
        file_path: Path to the holdings file.

    Returns:
        List of Holding objects. Empty list if file is missing or
        unparseable.
    """

    if not file_path.exists():
        logger.warning("Holdings file not found: %s.", file_path)
        return []

    return parse_holdings_file(file_path, isin)
