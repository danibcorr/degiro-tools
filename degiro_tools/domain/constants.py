# Standard libraries
from decimal import Decimal
from typing import Final

CENT_QUANTIZE: Decimal = Decimal("0.01")

ISIN_MAPPING: Final[dict[str, str]] = {"IE000I8KRLL9": "SEMI.AS"}

ETF_LIST_NAME: Final[tuple[str, ...]] = (
    "ishares",
    "vanguard",
    "xtrackers",
    "spdr",
    "amundi",
    "lyxor",
    "invesco",
    "hsbc",
    "fidelity",
    "wisdomtree",
    "vaneck",
    "schwab",
    "global x",
    "state street",
    "dimensional",
    "first trust",
    "j.p. morgan",
    "goldman sachs",
    "ubs",
    "franklin templeton",
)
