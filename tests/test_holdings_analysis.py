# Standard libraries
import logging

# 3pps
import polars as pl
import pytest

# Own modules
import degiro_tools.analysis.holdings as analysis_holdings
from degiro_tools.analysis.holdings import (
    build_holdings_dataframe,
    compute_portfolio_weights,
)
from degiro_tools.domain.holdings import Holding

EXPECTED_TOTAL_PCT = 100.0


def holding(source_isin: str, name: str = "ACME") -> Holding:
    """
    Build a canonical single-holding ETF stand-in for tests.
    """

    return Holding(
        name=name,
        ticker="",
        sector="Information Technology",
        weight_pct=100.0,
        location="United States",
        source_isin=source_isin,
    )


def test_build_holdings_dataframe_raises_on_empty() -> None:
    """
    No loadable holdings raises a clear ValueError, not a cryptic
    ColumnNotFoundError downstream.
    """

    with pytest.raises(ValueError, match="No holdings could be loaded"):
        build_holdings_dataframe([], {})


def test_build_holdings_dataframe_excludes_unpriced_positions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Unpriced source positions are dropped and reported, and the
    effective weights of the priced holdings still sum to ~100%.
    """

    holdings = [holding("ISIN_PRICED", "Priced"), holding("ISIN_MISSING", "Missing")]
    weights = {"ISIN_PRICED": 1.0}

    with caplog.at_level(logging.WARNING):
        df = build_holdings_dataframe(holdings, weights)

    assert df["source_isin"].to_list() == ["ISIN_PRICED"]
    assert df["effective_pct"].sum() == pytest.approx(EXPECTED_TOTAL_PCT)
    assert "ISIN_MISSING" in caplog.text
    assert "relative to priced holdings" in caplog.text


def test_build_holdings_dataframe_weights_relative_to_priced_base() -> None:
    """
    With two priced ETFs, each effective weight reflects its share of
    the priced portfolio value.
    """

    holdings = [holding("ISIN_A", "A"), holding("ISIN_B", "B")]
    weights = {"ISIN_A": 0.3, "ISIN_B": 0.7}

    df = build_holdings_dataframe(holdings, weights)

    by_isin = dict(
        zip(
            df["source_isin"].to_list(),
            df["effective_pct"].to_list(),
            strict=True,
        )
    )

    assert by_isin["ISIN_A"] == pytest.approx(30.0)
    assert by_isin["ISIN_B"] == pytest.approx(70.0)


def test_compute_portfolio_weights_normalizes_over_priced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Weights are fractions of the summed priced market values.
    """

    monkeypatch.setattr(
        analysis_holdings,
        "get_position_values",
        lambda _df, logger=None: {"ISIN_A": 30.0, "ISIN_B": 70.0},
    )

    weights = compute_portfolio_weights(pl.DataFrame({"x": [1]}))

    assert weights["ISIN_A"] == pytest.approx(0.3)
    assert weights["ISIN_B"] == pytest.approx(0.7)


def test_compute_portfolio_weights_empty_when_nothing_priced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    No priced positions yields an empty weight mapping.
    """

    monkeypatch.setattr(
        analysis_holdings, "get_position_values", lambda _df, logger=None: {}
    )

    assert compute_portfolio_weights(pl.DataFrame({"x": [1]})) == {}
