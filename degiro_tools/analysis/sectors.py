# 3pps
import polars as pl


def compute_sectors(df: pl.DataFrame) -> pl.DataFrame:
    """
    Aggregate effective portfolio weight by sector.

    Filters out holdings without sector data, then groups by sector
    and sums the pre-computed effective_pct column.

    Args:
        df: Holdings DataFrame with columns sector, effective_pct.

    Returns:
        DataFrame with columns: sector, effective_pct. Sorted by
        weight descending.
    """

    return (
        df.filter(pl.col("sector") != "")
        .group_by("sector")
        .agg(pl.col("effective_pct").sum())
        .sort("effective_pct", descending=True)
    )
