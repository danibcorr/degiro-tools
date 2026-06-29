# Standard libraries
from unittest.mock import MagicMock

# 3pps
import pytest

# Own modules
from degiro_tools import cli
from degiro_tools.cli import build_arg_parser, main


def test_overview_parser_omits_export() -> None:
    """
    The overview subcommand shares the analysis args but not
    --export, which it explicitly does not support.
    """

    parser = build_arg_parser()
    args = parser.parse_args(["overview", "Portfolio.xlsx"])

    assert args.command == "overview"
    assert args.xlsx_path.name == "Portfolio.xlsx"
    assert not hasattr(args, "export")

    with pytest.raises(SystemExit):
        parser.parse_args(["overview", "Portfolio.xlsx", "--export", "out.csv"])


def test_overview_loads_holdings_once_and_renders_all_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    ``overview`` runs the valuation flow once, loads the holdings
    DataFrame exactly once, and renders all four analysis sections
    from that single frame (no repeated network loads).
    """

    sentinel_df = object()

    run_portfolio = MagicMock()
    load_holdings = MagicMock(return_value=sentinel_df)
    compute_overlap = MagicMock(return_value="overlap_df")
    compute_sectors = MagicMock(return_value="sectors_df")
    compute_geography = MagicMock(return_value=("country_df", "continent_df"))
    render_portfolio = MagicMock()
    render_holdings = MagicMock()
    render_overlap = MagicMock()
    render_sectors = MagicMock()
    render_geography = MagicMock()

    monkeypatch.setattr(cli, "run_portfolio", run_portfolio)
    monkeypatch.setattr(cli, "load_portfolio_holdings", load_holdings)
    monkeypatch.setattr(cli, "compute_overlap", compute_overlap)
    monkeypatch.setattr(cli, "compute_sectors", compute_sectors)
    monkeypatch.setattr(cli, "compute_geography", compute_geography)
    monkeypatch.setattr(cli, "render_portfolio", render_portfolio)
    monkeypatch.setattr(cli, "render_holdings", render_holdings)
    monkeypatch.setattr(cli, "render_overlap", render_overlap)
    monkeypatch.setattr(cli, "render_sectors", render_sectors)
    monkeypatch.setattr(cli, "render_geography", render_geography)

    exit_code = main(["overview", "Portfolio.xlsx"])

    assert exit_code == 0

    # Valuation section reuses the portfolio flow exactly once.
    run_portfolio.assert_called_once()

    # The holdings frame is built only once and shared by all sections.
    load_holdings.assert_called_once()

    # Every analysis section renders from the single shared frame.
    render_holdings.assert_called_once_with(sentinel_df)
    compute_overlap.assert_called_once_with(sentinel_df)
    render_overlap.assert_called_once_with("overlap_df")
    compute_sectors.assert_called_once_with(sentinel_df)
    render_sectors.assert_called_once_with("sectors_df")
    compute_geography.assert_called_once_with(sentinel_df)
    render_geography.assert_called_once_with("country_df", "continent_df")
