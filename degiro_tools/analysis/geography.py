# 3pps
import polars as pl

# Own modules
from ..domain.constants import CONTINENT_MAP


def compute_geography(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Aggregate effective portfolio weight by country and continent.

    Filters out holdings without location data, groups by country,
    then maps countries to continents via CONTINENT_MAP (unmapped
    countries fall under "Other").

    Args:
        df: Holdings DataFrame with columns location, effective_pct.

    Returns:
        Tuple of (by_country, by_continent) DataFrames. Each has
        columns location/continent and effective_pct, sorted by
        weight descending.
    """

    df_geo = df.filter(pl.col("location") != "")

    df_country = (
        df_geo.group_by("location")
        .agg(pl.col("effective_pct").sum())
        .sort("effective_pct", descending=True)
    )

    df_continent = (
        df_geo.with_columns(
            pl.col("location")
            .replace_strict(CONTINENT_MAP, default="Other")
            .alias("continent")
        )
        .group_by("continent")
        .agg(pl.col("effective_pct").sum())
        .sort("effective_pct", descending=True)
    )

    return df_country, df_continent
