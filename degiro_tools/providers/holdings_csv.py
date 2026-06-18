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

    ns = "urn:schemas-microsoft-com:office:spreadsheet"
    all_rows = root.findall(f".//{{{ns}}}Row")

    # Extract cell values from each row
    table: list[list[str]] = []

    for row in all_rows:
        cells: list[str] = []
        for cell in row.findall(f"{{{ns}}}Cell"):
            data = cell.find(f"{{{ns}}}Data")
            cells.append(data.text if data is not None and data.text else "")
        table.append(cells)

    # Find header row (the one containing a known column name)
    header_idx = None
    for i, cells in enumerate(table):
        for alias_list in COLUMN_ALIASES.values():
            if any(alias in cells for alias in alias_list):
                header_idx = i
                break
        if header_idx is not None:
            break

    if header_idx is None:
        logger.warning("No header row found in XML file %s.", path)
        return []

    headers = table[header_idx]
    col_name = resolve_column(headers, "name")
    col_ticker = resolve_column(headers, "ticker")
    col_sector = resolve_column(headers, "sector")
    col_weight = resolve_column(headers, "weight")
    col_location = resolve_column(headers, "location")
    col_asset = resolve_column(headers, "asset_class")

    if col_name is None or col_weight is None:
        logger.warning("Missing Name/Weight columns in %s.", path)
        return []

    name_idx = headers.index(col_name)
    ticker_idx = headers.index(col_ticker) if col_ticker else None
    sector_idx = headers.index(col_sector) if col_sector else None
    weight_idx = headers.index(col_weight)
    location_idx = headers.index(col_location) if col_location else None
    asset_idx = headers.index(col_asset) if col_asset else None

    holdings: list[Holding] = []

    for cells in table[header_idx + 1 :]:
        if len(cells) <= weight_idx:
            continue

        # Filter to equities
        if asset_idx is not None and len(cells) > asset_idx:
            if cells[asset_idx] and cells[asset_idx] != "Equity":
                continue

        weight = parse_weight(cells[weight_idx])
        if weight is None or weight <= 0:
            continue

        name = cells[name_idx] if len(cells) > name_idx else ""
        if not name:
            continue

        holdings.append(
            Holding(
                name=name,
                ticker=cells[ticker_idx]
                if ticker_idx is not None and len(cells) > ticker_idx
                else "",
                sector=cells[sector_idx]
                if sector_idx is not None and len(cells) > sector_idx
                else "",
                weight_pct=weight,
                location=cells[location_idx]
                if location_idx is not None and len(cells) > location_idx
                else "",
                source_isin=isin,
            )
        )

    return holdings


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

    # Find header row
    header_idx = None
    for i, raw_row in enumerate(df_raw.iter_rows()):
        row_values = [str(v) if v else "" for v in raw_row]
        for alias_list in COLUMN_ALIASES.values():
            if any(alias in row_values for alias in alias_list):
                header_idx = i
                break
        if header_idx is not None:
            break

    if header_idx is None:
        logger.warning("No header row found in %s.", path)
        return []

    # Get headers and data
    header_row = [str(v) if v else "" for v in df_raw.row(header_idx)]

    col_name = resolve_column(header_row, "name")
    col_ticker = resolve_column(header_row, "ticker")
    col_sector = resolve_column(header_row, "sector")
    col_weight = resolve_column(header_row, "weight")
    col_location = resolve_column(header_row, "location")

    if col_name is None or col_weight is None:
        logger.warning("Missing Name/Weight columns in %s.", path)
        return []

    name_idx = header_row.index(col_name)
    ticker_idx = header_row.index(col_ticker) if col_ticker else None
    sector_idx = header_row.index(col_sector) if col_sector else None
    weight_idx = header_row.index(col_weight)
    location_idx = header_row.index(col_location) if col_location else None

    holdings: list[Holding] = []

    for i in range(header_idx + 1, len(df_raw)):
        row: list[str] = [str(v) if v else "" for v in df_raw.row(i)]

        if len(row) <= weight_idx:
            continue

        weight = parse_weight(row[weight_idx])
        if weight is None or weight <= 0:
            continue

        name = row[name_idx] if len(row) > name_idx else ""
        if not name or name == "null":
            continue

        holdings.append(
            Holding(
                name=name,
                ticker=row[ticker_idx]
                if ticker_idx is not None and len(row) > ticker_idx
                else "",
                sector=row[sector_idx]
                if sector_idx is not None and len(row) > sector_idx
                else "",
                weight_pct=weight,
                location=row[location_idx]
                if location_idx is not None and len(row) > location_idx
                else "",
                source_isin=isin,
            )
        )

    return holdings


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
