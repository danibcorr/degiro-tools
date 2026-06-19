# Standard libraries
import re
from typing import Final

# 3pps
import polars as pl

CORP_SUFFIXES: Final[re.Pattern[str]] = re.compile(
    r"\b(INC|CORP|LTD|PLC|SA|AG|NV|SE|CO|GROUP|HOLDINGS|CLASS\s+[A-Z])\b"
)


def normalize_name(name: str) -> str:
    """
    Normalize a company name for deduplication across data sources.

    Uppercases and strips common corporate suffixes (INC, CORP, LTD,
    PLC, etc.) to allow matching the same company across different
    ETFs that may use slightly different naming.

    Args:
        name: Raw company name from holdings data.

    Returns:
        Cleaned uppercase name with suffixes removed.
    """

    cleaned = CORP_SUFFIXES.sub("", name.upper().strip())
    return " ".join(cleaned.split())


def compute_overlap(df: pl.DataFrame) -> pl.DataFrame:
    """
    Identify securities held through multiple ETFs.

    Groups holdings by normalized company name and returns only those
    appearing in 2+ distinct source funds, sorted by total effective
    portfolio exposure descending.

    Args:
        df: Holdings DataFrame with columns name, source_isin,
            effective_pct.

    Returns:
        DataFrame with columns: name, etf_count, effective_pct.
    """

    return (
        df.with_columns(
            pl.col("name")
            .map_elements(normalize_name, return_dtype=pl.Utf8)
            .alias("normalized_name")
        )
        .group_by("normalized_name")
        .agg(
            pl.col("name").first().alias("name"),
            pl.col("source_isin").n_unique().alias("etf_count"),
            pl.col("effective_pct").sum().alias("effective_pct"),
        )
        .filter(pl.col("etf_count") > 1)
        .sort("effective_pct", descending=True)
        .drop("normalized_name")
    )
