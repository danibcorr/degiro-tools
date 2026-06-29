# Standard libraries
import argparse
import logging
import sys
from pathlib import Path

# 3pps
from rich.console import Console

# Own modules
from . import __version__
from .analysis import (
    compute_geography,
    compute_overlap,
    compute_sectors,
    load_portfolio_holdings,
)
from .calculation import calculate_fifo
from .calculation.portfolio import compute_portfolio_percentage, obtain_yahoo_info
from .parsing import parse_account_xlsx, parse_portfolio_xlsx
from .reporting import print_report
from .reporting.analysis_report import (
    render_geography,
    render_holdings,
    render_overlap,
    render_portfolio,
    render_sectors,
)
from .utils import build_logger


def add_analysis_args(
    parser: argparse.ArgumentParser, include_export: bool = True
) -> None:
    """
    Add shared arguments for analysis subcommands.

    Registers xlsx_path, --config and -v/--verbose flags common to
    holdings, overlap, sectors and geography commands. The --export
    flag is added only when include_export is True; the consolidated
    overview command opts out of it.

    Args:
        parser: The subcommand argument parser to extend.
        include_export: Whether to register the --export CSV flag.

    Returns:
        None.
    """

    parser.add_argument(
        "xlsx_path",
        type=Path,
        help="Path to Portfolio.xlsx exported from Degiro.",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path("holdings.json"),
        help="JSON config mapping ISIN to holdings files (default: holdings.json).",
    )

    if include_export:
        parser.add_argument(
            "--export",
            type=Path,
            default=None,
            help="Export results to CSV at the given path.",
        )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show full traceback on error.",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """
    Build the CLI argument parser with all subcommands.

    Registers tax, portfolio, holdings, overlap, sectors and
    geography subcommands with their respective arguments.

    Returns:
        Configured ArgumentParser instance.
    """

    parser = argparse.ArgumentParser(
        prog="degiro-tools",
        description="Herramientas para extractos Degiro.",
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    sub = parser.add_subparsers(dest="command")

    # --- tax ---
    tax_p = sub.add_parser(
        "tax",
        help="Calcula ganancias/pérdidas patrimoniales IRPF.",
    )
    tax_p.add_argument(
        "account_path",
        type=Path,
        help="Ruta al XLSX de Estado de cuenta (Account.xlsx).",
    )
    tax_p.add_argument(
        "--no-tax",
        action="store_true",
        help="Omite el bloque de estimación IRPF.",
    )
    tax_p.add_argument("-v", "--verbose", action="store_true")

    # --- portfolio ---
    port_p = sub.add_parser(
        "portfolio",
        help="Valoración actual de la cartera desde un XLSX.",
    )
    port_p.add_argument(
        "xlsx_path",
        type=Path,
        help="Ruta al XLSX de Portfolio.",
    )
    port_p.add_argument("-v", "--verbose", action="store_true")

    # --- analysis subcommands ---
    for name, help_text in (
        ("holdings", "Show top holdings across all ETFs."),
        ("overlap", "Show securities present in multiple ETFs."),
        ("sectors", "Show sector allocation."),
        ("geography", "Show geographic allocation."),
    ):
        add_analysis_args(sub.add_parser(name, help=help_text))

    # --- overview (consolidated global view) ---
    add_analysis_args(
        sub.add_parser(
            "overview",
            help="Vista global: valoración + holdings, solapamiento, "
            "sectores y geografía.",
        ),
        include_export=False,
    )

    return parser


def run_tax(args: argparse.Namespace, logger: logging.Logger) -> None:
    """
    Execute the IRPF tax calculation flow.

    Parses the Degiro Account.xlsx, applies FIFO matching and renders
    the fiscal report.

    Args:
        args: Parsed CLI arguments with account_path and no_tax.
        logger: Application logger injected from the entry point.

    Returns:
        None.
    """

    ops, connectivity_fees = parse_account_xlsx(args.account_path, logger=logger)
    sales, lots = calculate_fifo(ops)

    print_report(
        sales,
        lots,
        connectivity_fees,
        include_tax=not args.no_tax,
    )


def run_portfolio(args: argparse.Namespace, logger: logging.Logger) -> None:
    """
    Execute the portfolio valuation flow.

    Reads the Portfolio XLSX, fetches current prices from Yahoo
    Finance, and renders a table with positions and weights.

    Args:
        args: Parsed CLI arguments with xlsx_path.
        logger: Application logger injected from the entry point.

    Returns:
        None.
    """

    df = parse_portfolio_xlsx(args.xlsx_path)
    df_with_info = obtain_yahoo_info(df, logger=logger)
    df_output = compute_portfolio_percentage(df_with_info)

    render_portfolio(df_output)


def run_analysis(
    command: str, args: argparse.Namespace, logger: logging.Logger
) -> None:
    """
    Execute an analysis subcommand.

    Loads portfolio holdings from the files configured in the holdings
    JSON, computes effective weights, then dispatches to the
    appropriate rendering function.

    Args:
        command: Subcommand name (holdings, overlap, sectors, or
            geography).
        args: Parsed CLI arguments with xlsx_path, config, export.
        logger: Application logger injected from the entry point.

    Returns:
        None.
    """

    df = load_portfolio_holdings(args.xlsx_path, args.config, logger=logger)

    if command == "holdings":
        render_holdings(df, export_path=args.export)

    elif command == "overlap":
        render_overlap(compute_overlap(df), export_path=args.export)

    elif command == "sectors":
        render_sectors(compute_sectors(df), export_path=args.export)

    elif command == "geography":
        df_country, df_continent = compute_geography(df)
        render_geography(df_country, df_continent, export_path=args.export)


def run_overview(args: argparse.Namespace, logger: logging.Logger) -> None:
    """
    Execute the consolidated global portfolio view.

    Renders the current valuation (reusing the portfolio flow) and
    then the four holdings analyses (top holdings, ETF overlap, sector
    and geographic allocation). The underlying holdings DataFrame is
    built only once via load_portfolio_holdings to avoid repeating the
    Yahoo Finance network calls across sections. Output is printed to
    stdout only; this command does not support --export.

    Args:
        args: Parsed CLI arguments with xlsx_path and config.
        logger: Application logger injected from the entry point.

    Returns:
        None.
    """

    console = Console()

    console.rule("[bold cyan]Valoración de la cartera[/bold cyan]")
    run_portfolio(args, logger)

    # Single load shared by the four analysis sections below.
    df = load_portfolio_holdings(args.xlsx_path, args.config, logger=logger)

    console.rule("[bold cyan]Principales posiciones reales[/bold cyan]")
    render_holdings(df)

    console.rule("[bold cyan]Solapamiento entre ETFs[/bold cyan]")
    render_overlap(compute_overlap(df))

    console.rule("[bold cyan]Distribución sectorial[/bold cyan]")
    render_sectors(compute_sectors(df))

    console.rule("[bold cyan]Distribución geográfica[/bold cyan]")
    df_country, df_continent = compute_geography(df)
    render_geography(df_country, df_continent)


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry point.

    Parses arguments, dispatches to the appropriate subcommand
    handler, and returns an integer exit code.

    Args:
        argv: Arguments list (optional, for testing). Uses sys.argv
            if None.

    Returns:
        Exit code: 0 success, 1 error, 130 keyboard interrupt.
    """

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    verbose = getattr(args, "verbose", False)
    logger = build_logger(verbose=verbose)

    try:
        if args.command == "tax":
            run_tax(args, logger)
        elif args.command == "portfolio":
            run_portfolio(args, logger)
        elif args.command == "overview":
            run_overview(args, logger)
        else:
            run_analysis(args.command, args, logger)

    except KeyboardInterrupt:
        return 130

    except Exception as exc:
        if verbose:
            raise

        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0
