# 3pps
import polars as pl

# Own modules
from degiro_tools.analysis.sectors import compute_sectors
from degiro_tools.domain.constants import SECTOR_MAP

CANONICAL_IT: str = "Information Technology"


def test_sector_map_normalizes_aliases_to_canonical_it() -> None:
    """
    SECTOR_MAP unifies Technology aliases to the GICS canonical.

    Both the Vanguard/Morningstar ``Technology`` alias and the
    Spanish iShares ``Tecnología de la Información`` value must
    normalize to ``Information Technology`` so that providers share a
    single sector taxonomy.
    """

    assert SECTOR_MAP["Technology"] == CANONICAL_IT
    assert SECTOR_MAP["Tecnología de la Información"] == CANONICAL_IT


def test_compute_sectors_merges_mixed_provider_it_buckets() -> None:
    """
    compute_sectors merges normalized IT holdings into one row.

    Synthesizes mixed-provider holdings whose raw sector labels are
    normalized via SECTOR_MAP, then verifies a single aggregated
    Information Technology row with no residual ``Technology`` bucket.
    """

    raw_sectors = [
        "Technology",
        "Tecnología de la Información",
        "Information Technology",
    ]
    df = pl.DataFrame(
        {
            "sector": [SECTOR_MAP.get(s, s) for s in raw_sectors],
            "effective_pct": [1.0, 2.0, 3.0],
        }
    )

    result = compute_sectors(df)
    sectors = result["sector"].to_list()

    assert sectors == [CANONICAL_IT]
    assert "Technology" not in sectors
    assert result.filter(pl.col("sector") == CANONICAL_IT)["effective_pct"][0] == 6.0
