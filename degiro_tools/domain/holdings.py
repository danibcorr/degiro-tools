# Standard libraries
from dataclasses import dataclass


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
