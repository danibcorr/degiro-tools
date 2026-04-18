# Standard libraries
import argparse
import sys
from pathlib import Path

# Own modules
from . import __version__
from .calculation import calcular_fifo
from .parsing import parse_csv
from .reporting import imprimir_informe


def build_arg_parser() -> argparse.ArgumentParser:
    """
    Construye el ``ArgumentParser`` del CLI con todas las opciones.

    Returns:
        Parser configurado con ``csv_path``, ``--no-tax``, ``--verbose`` y
        ``--version``.
    """

    arg_parser = argparse.ArgumentParser(
        prog="degiro-calc",
        description=(
            "Calcula ganancias/pérdidas patrimoniales IRPF (España) "
            "desde un extracto Degiro."
        ),
    )

    arg_parser.add_argument(
        "csv_path",
        type=Path,
        help="Ruta al CSV exportado desde Degiro (Estado de cuenta).",
    )
    arg_parser.add_argument(
        "--no-tax", action="store_true", help="Omite el bloque de estimación IRPF."
    )
    arg_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Muestra traceback completo en caso de error.",
    )
    arg_parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    return arg_parser


def _run(args: argparse.Namespace) -> None:
    """
    Ejecuta el flujo principal: parseo, FIFO y emisión del informe.

    Args:
        args: Argumentos ya parseados por ``build_arg_parser``.
    """

    ops, comisiones_conectividad = parse_csv(args.csv_path)
    ventas, lotes = calcular_fifo(ops)
    imprimir_informe(
        ventas, lotes, comisiones_conectividad, incluir_tax=not args.no_tax
    )


def main(argv: list[str] | None = None) -> int:
    """
    Punto de entrada del CLI.

    Args:
        argv: Argumentos (opcional, para testing). Si es ``None`` usa ``sys.argv``.

    Returns:
        Código de salida: 0 éxito, 1 error, 130 interrupción por teclado.
    """

    args = build_arg_parser().parse_args(argv)

    try:
        _run(args)

    except KeyboardInterrupt:
        return 130

    except Exception as exc:
        if args.verbose:
            raise

        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0
