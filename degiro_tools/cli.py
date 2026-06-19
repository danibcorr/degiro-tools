# Standard libraries
import argparse
import sys
from pathlib import Path

# Own modules
from . import __version__
from .analysis import (
    compute_geography,
    compute_overlap,
    compute_sectors,
    load_portfolio_holdings,
)
from .calculation import calcular_fifo
from .calculation.portfolio import compute_portfolio_percentage, obtain_yahoo_info
from .parsing import parse_csv
from .parsing.xlsx_parser import parse_portfolio_xlsx
from .reporting import imprimir_informe
from .reporting.analysis_report import (
    render_geography,
    render_holdings,
    render_overlap,
    render_portfolio,
    render_sectors,
)


def add_analysis_args(parser: argparse.ArgumentParser) -> None:
    """
    Add shared arguments for analysis subcommands.

    Registers xlsx_path, --config, --export and -v/--verbose flags
    common to holdings, overlap, sectors and geography commands.

    Args:
        parser: The subcommand argument parser to extend.

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
        help="JSON config mapping ISIN to holdings CSV paths (default: holdings.json).",
    )

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
        "csv_path",
        type=Path,
        help="Ruta al CSV de Estado de cuenta.",
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

    return parser


def run_tax(args: argparse.Namespace) -> None:
    """
    Execute the IRPF tax calculation flow.

    Parses the Degiro CSV, applies FIFO matching and renders the
    fiscal report.

    Args:
        args: Parsed CLI arguments with csv_path and no_tax.

    Returns:
        None.
    """

    ops, comisiones_conectividad = parse_csv(args.csv_path)
    ventas, lotes = calcular_fifo(ops)

    imprimir_informe(
        ventas,
        lotes,
        comisiones_conectividad,
        incluir_tax=not args.no_tax,
    )


def run_portfolio(args: argparse.Namespace) -> None:
    """
    Execute the portfolio valuation flow.

    Reads the Portfolio XLSX, fetches current prices from Yahoo
    Finance, and renders a table with positions and weights.

    Args:
        args: Parsed CLI arguments with xlsx_path.

    Returns:
        None.
    """

    df = parse_portfolio_xlsx(args.xlsx_path)
    df_with_info = obtain_yahoo_info(df)
    df_output = compute_portfolio_percentage(df_with_info)

    render_portfolio(df_output)


def run_analysis(command: str, args: argparse.Namespace) -> None:
    """
    Execute an analysis subcommand.

    Loads portfolio holdings from CSVs configured in the holdings
    JSON, computes effective weights, then dispatches to the
    appropriate rendering function.

    Args:
        command: Subcommand name (holdings, overlap, sectors, or
            geography).
        args: Parsed CLI arguments with xlsx_path, config, export.

    Returns:
        None.
    """

    df = load_portfolio_holdings(args.xlsx_path, args.config)

    if command == "holdings":
        render_holdings(df, export_path=args.export)

    elif command == "overlap":
        render_overlap(compute_overlap(df), export_path=args.export)

    elif command == "sectors":
        render_sectors(compute_sectors(df), export_path=args.export)

    elif command == "geography":
        df_country, df_continent = compute_geography(df)
        render_geography(df_country, df_continent, export_path=args.export)


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

    try:
        if args.command == "tax":
            run_tax(args)
        elif args.command == "portfolio":
            run_portfolio(args)
        else:
            run_analysis(args.command, args)

    except KeyboardInterrupt:
        return 130

    except Exception as exc:
        if verbose:
            raise

        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0
