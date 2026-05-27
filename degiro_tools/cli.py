# Standard libraries
import argparse
import sys
from pathlib import Path

# Own modules
from . import __version__
from .calculation import calcular_fifo
from .calculation.portfolio import compute_portfolio_percentage, obtain_yahoo_info
from .parsing import parse_csv
from .parsing.xlsx_parser import parse_portfolio_xlsx
from .reporting import imprimir_informe


def _build_arg_parser() -> argparse.ArgumentParser:
    """Construye el ``ArgumentParser`` con subcomandos ``tax`` y ``portfolio``."""

    parser = argparse.ArgumentParser(
        prog="degiro-tools",
        description="Herramientas para extractos Degiro.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command")

    # --- tax subcommand ---
    tax_parser = subparsers.add_parser(
        "tax",
        help="Calcula ganancias/pérdidas patrimoniales IRPF desde un CSV Degiro.",
    )
    tax_parser.add_argument(
        "csv_path",
        type=Path,
        help="Ruta al CSV exportado desde Degiro (Estado de cuenta).",
    )
    tax_parser.add_argument(
        "--no-tax", action="store_true", help="Omite el bloque de estimación IRPF."
    )
    tax_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Muestra traceback completo en caso de error.",
    )

    # --- portfolio subcommand ---
    portfolio_parser = subparsers.add_parser(
        "portfolio",
        help="Valoración actual de la cartera desde un XLSX de Portfolio Degiro.",
    )
    portfolio_parser.add_argument(
        "xlsx_path",
        type=Path,
        help="Ruta al XLSX exportado desde Degiro (Portfolio).",
    )
    portfolio_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Muestra traceback completo en caso de error.",
    )

    return parser


def _run_tax(args: argparse.Namespace) -> None:
    """Ejecuta el flujo de cálculo fiscal: parseo, FIFO e informe."""

    ops, comisiones_conectividad = parse_csv(args.csv_path)
    ventas, lotes = calcular_fifo(ops)
    imprimir_informe(
        ventas, lotes, comisiones_conectividad, incluir_tax=not args.no_tax
    )


def _run_portfolio(args: argparse.Namespace) -> None:
    """Ejecuta el flujo de valoración de cartera."""

    df = parse_portfolio_xlsx(args.xlsx_path)
    df_with_info = obtain_yahoo_info(df)
    df_output = compute_portfolio_percentage(df_with_info)
    print(df_output)


def main(argv: list[str] | None = None) -> int:
    """
    Punto de entrada del CLI.

    Args:
        argv: Argumentos (opcional, para testing). Si es ``None`` usa ``sys.argv``.

    Returns:
        Código de salida: 0 éxito, 1 error, 130 interrupción por teclado.
    """

    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    verbose = getattr(args, "verbose", False)

    try:
        if args.command == "tax":
            _run_tax(args)
        elif args.command == "portfolio":
            _run_portfolio(args)

    except KeyboardInterrupt:
        return 130

    except Exception as exc:
        if verbose:
            raise

        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0
