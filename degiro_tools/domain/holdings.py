# Standard libraries
from dataclasses import dataclass, replace

# Own modules
from .constants import COUNTRY_MAP, SECTOR_MAP


@dataclass(frozen=True)
class Holding:
    """
    Single equity holding within an ETF or standalone stock position.

    Attributes:
        name: Company or instrument name.
        ticker: Ticker symbol of the holding.
        sector: Sector classification (e.g. "Information Technology").
        weight_pct: Weight within the parent fund as percentage (0-100).
        location: Country where the company is domiciled.
        source_isin: ISIN of the parent ETF (or self for stocks).
    """

    name: str
    ticker: str
    sector: str
    weight_pct: float
    location: str
    source_isin: str


def normalize_holding(holding: Holding) -> Holding:
    """
    Canonicalize a holding's sector and location labels.

    Maps raw provider sector and country values to the project's
    canonical vocabulary via SECTOR_MAP and COUNTRY_MAP. Values that
    are already canonical (or absent from the maps) are returned
    unchanged. This is the single normalization step applied at the
    providers boundary so that every consumer receives canonical
    holdings, regardless of the originating provider.

    Args:
        holding: Holding carrying raw provider sector and location
            values.

    Returns:
        New Holding with normalized sector and location fields; all
        other fields are preserved.
    """

    return replace(
        holding,
        sector=SECTOR_MAP.get(holding.sector, holding.sector),
        location=COUNTRY_MAP.get(holding.location, holding.location),
    )
