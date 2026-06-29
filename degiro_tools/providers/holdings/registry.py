# Standard libraries
import json
import logging
from pathlib import Path
from typing import Final

# Own modules
from ...domain.holdings import Holding, normalize_holding
from .base import HoldingsParser
from .ishares import ISharesParser
from .vanguard import VanguardParser
from .xtrackers import XtrackersParser

_FALLBACK_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


def build_parsers(
    logger: logging.Logger | None = None,
) -> tuple[HoldingsParser, ...]:
    """
    Build the ordered tuple of provider parsers.

    Each parser receives the injected logger so its diagnostics are
    traceable through the same logging chain as the rest of the run.

    Args:
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        Tuple of parser instances evaluated in detection order.
    """

    return (
        ISharesParser(logger=logger),
        VanguardParser(logger=logger),
        XtrackersParser(logger=logger),
    )


# Registered parsers, evaluated in order for content-based dispatch.
PARSERS: Final[tuple[HoldingsParser, ...]] = build_parsers()


def parse_holdings_file(
    path: Path, isin: str, logger: logging.Logger | None = None
) -> list[Holding]:
    """
    Parse a holdings file using the first matching provider parser.

    Selects the parser via content-based detection (header
    signatures and file markers) rather than file extension alone,
    then delegates parsing to it.

    Args:
        path: Path to the holdings file (.xls or .xlsx).
        isin: Source ETF ISIN for attribution.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        List of Holding objects. Empty list if no parser recognizes
        the file.
    """

    log = logger if logger is not None else _FALLBACK_LOGGER

    for parser in build_parsers(logger):
        if parser.can_parse(path):
            log.debug("Using %s parser for %s.", parser.name, path)
            return parser.parse(path, isin)

    log.warning("No holdings parser matched %s.", path)
    return []


def load_holdings_config(config_path: Path) -> dict[str, Path]:
    """
    Load the ISIN-to-file-path mapping from a JSON config.

    The JSON must be a flat object mapping ISIN strings to file
    paths pointing to holdings files (.xls or .xlsx).
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


def fetch_holdings(
    isin: str, file_path: Path, logger: logging.Logger | None = None
) -> list[Holding]:
    """
    Load holdings for an ETF from its local file.

    Parses the file via the matching provider parser and applies the
    single normalization step at this providers boundary, so every
    consumer receives already-canonical holdings (sector and location
    mapped to the project vocabulary).

    Args:
        isin: ISIN of the ETF.
        file_path: Path to the holdings file.
        logger: Optional logger for diagnostics; falls back to a
            module-level logger when omitted.

    Returns:
        List of canonicalized Holding objects. Empty list if the file
        is missing or unparseable.
    """

    log = logger if logger is not None else _FALLBACK_LOGGER

    if not file_path.exists():
        log.warning("Holdings file not found: %s.", file_path)
        return []

    holdings = parse_holdings_file(file_path, isin, logger=logger)

    return [normalize_holding(holding) for holding in holdings]
