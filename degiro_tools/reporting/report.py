# Standard libraries
from collections import defaultdict, deque
from decimal import ROUND_HALF_UP, Decimal

# 3pps
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Own modules
from ..calculation.informe import build_informe_data
from ..domain.constants import CENT_QUANTIZE
from ..domain.models import InformeData, Lote, TramoCuota, Venta


def _fmt(value: Decimal) -> str:
    """Formatea un Decimal a 2 decimales sin separador de miles."""

    return str(value.quantize(CENT_QUANTIZE, rounding=ROUND_HALF_UP))


def _gp_text(gp: Decimal, *, bold: bool = True) -> Text:
    """Construye un Text coloreado según el signo de la G/P."""

    color = "green" if gp >= 0 else "red"
    style = f"bold {color}" if bold else color
    return Text(_fmt(gp), style=style)


def render_ventas_casadas(console: Console, ventas: list[Venta]) -> None:
    """Renderiza la tabla de ventas casadas por FIFO."""

    console.print(Rule("[bold]Ventas casadas (FIFO por ISIN)[/bold]"))
    console.print("[dim]valores en EUR reales del broker[/dim]")

    if not ventas:
        console.print("[dim]Sin ventas en el ejercicio.[/dim]")
        return

    table = Table(box=box.ROUNDED, header_style="bold", expand=False)
    table.add_column("Fecha")
    table.add_column("ISIN")
    table.add_column("Producto", max_width=28, no_wrap=True, overflow="ellipsis")
    table.add_column("Cant.", justify="right")
    table.add_column("Coste adq.", justify="right")
    table.add_column("Valor trans.", justify="right")
    table.add_column("G/P", justify="right")

    for v in ventas:
        table.add_row(
            str(v.fecha),
            v.isin,
            v.producto,
            str(v.cantidad),
            _fmt(v.coste_adq),
            _fmt(v.valor_trans),
            _gp_text(v.gp),
        )

    console.print(table)


def render_resumen_isin(
    console: Console, ventas: list[Venta], total_gp: Decimal
) -> None:
    """Renderiza el resumen por ISIN y el total destacado."""

    console.print(Rule("[bold]Resumen por ISIN[/bold]"))

    ventas_por_isin: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    for v in ventas:
        ventas_por_isin[v.isin] += v.gp

    if ventas_por_isin:
        table = Table(box=box.ROUNDED, header_style="bold", expand=False)
        table.add_column("ISIN")
        table.add_column("G/P acumulada (EUR)", justify="right")
        for isin, gp in ventas_por_isin.items():
            table.add_row(isin, _gp_text(gp, bold=False))
        console.print(table)

    if total_gp > 0:
        color = "green"
    elif total_gp < 0:
        color = "red"
    else:
        color = "yellow"

    console.print(
        Panel(
            Text(f"{_fmt(total_gp)} EUR", style=f"bold {color}", justify="center"),
            title="[bold]TOTAL GANANCIA/PÉRDIDA PATRIMONIAL[/bold]",
            border_style=color,
            box=box.HEAVY,
        )
    )


def _tramos_table(cuota_irpf: list[TramoCuota], cuota_total: Decimal) -> Table:
    """Construye la tabla con los tramos y la fila de cuota total."""

    table = Table(box=box.ROUNDED, header_style="bold", expand=False)
    table.add_column("Desde", justify="right")
    table.add_column("Hasta", justify="right")
    table.add_column("Tipo", justify="right")
    table.add_column("Base", justify="right")
    table.add_column("Cuota", justify="right")

    for t in cuota_irpf:
        table.add_row(
            _fmt(t.desde),
            _fmt(t.hasta) if t.hasta is not None else "∞",
            f"{int(t.tipo * 100)}%",
            _fmt(t.base),
            _fmt(t.cuota),
        )

    table.add_section()
    table.add_row(
        "",
        "",
        "",
        Text("CUOTA ESTIMADA TOTAL", style="bold"),
        Text(_fmt(cuota_total), style="bold yellow"),
    )
    return table


def render_cuota_irpf(
    console: Console, total_gp: Decimal, cuota_irpf: list[TramoCuota] | None
) -> None:
    """Renderiza la estimación de cuota IRPF y el neto tras impuestos."""

    console.print(Rule("[bold]Estimación cuota IRPF[/bold]"))
    console.print("[dim]base imponible del ahorro, tramos art. 66 LIRPF[/dim]")
    console.print(
        Panel(
            "Estimación aislada. La cuota real depende del total de tu base del "
            "ahorro (dividendos, intereses, otras ganancias/pérdidas, "
            "compensaciones de años anteriores).",
            title="[bold]ADVERTENCIA[/bold]",
            border_style="yellow",
            box=box.ROUNDED,
        )
    )

    if not cuota_irpf:
        console.print(
            "[dim]Sin cuota: no hay ganancia neta positiva en el ejercicio.[/dim]"
        )
        return

    cuota_total = sum((t.cuota for t in cuota_irpf), Decimal(0))
    console.print(_tramos_table(cuota_irpf, cuota_total))

    neto = (total_gp - cuota_total).quantize(CENT_QUANTIZE, rounding=ROUND_HALF_UP)
    console.print(
        Panel(
            Text(f"{_fmt(neto)} EUR", style="bold cyan", justify="center"),
            title="[bold]Neto después de impuestos[/bold]",
            border_style="cyan",
            box=box.HEAVY,
        )
    )


def render_comisiones_conectividad(
    console: Console, comisiones_conectividad: Decimal
) -> None:
    """Renderiza el bloque de comisiones de conectividad no imputadas."""

    console.print(Rule("[bold]Gastos de custodia no imputados a operaciones[/bold]"))
    console.print(
        f"[dim]Comisiones de conectividad: {_fmt(comisiones_conectividad)} EUR[/dim]"
    )
    console.print(
        "[dim]No se suman al coste FIFO; declarables por separado según "
        "tu situación fiscal.[/dim]"
    )


def render_rentabilidad_neta(console: Console, rentabilidad_neta: Decimal) -> None:
    """Renderiza el panel final de rentabilidad neta real."""

    if rentabilidad_neta > 0:
        color = "green"
    elif rentabilidad_neta < 0:
        color = "red"
    else:
        color = "yellow"

    console.print(
        Panel(
            Text(
                f"{_fmt(rentabilidad_neta)} EUR",
                style=f"bold {color}",
                justify="center",
            ),
            title=(
                "[bold]RENTABILIDAD NETA REAL "
                "(tras impuestos y gastos de custodia)[/bold]"
            ),
            border_style=color,
            box=box.HEAVY,
        )
    )


def render_lotes_pendientes(console: Console, lotes: dict[str, deque[Lote]]) -> None:
    """Renderiza la cartera abierta (lotes pendientes) por ISIN."""

    console.print(Rule("[bold]Cartera abierta (lotes pendientes)[/bold]"))

    items: list[tuple[str, Lote]] = [
        (isin, lote) for isin in sorted(lotes) for lote in lotes[isin]
    ]

    if not items:
        console.print("[dim]Sin cartera abierta.[/dim]")
        return

    table = Table(box=box.ROUNDED, header_style="bold", expand=False)
    table.add_column("Fecha")
    table.add_column("ISIN")
    table.add_column("Cantidad", justify="right")
    table.add_column("Coste medio (EUR/ud)", justify="right")

    prev_isin: str | None = None
    for isin, lote in items:
        if prev_isin is not None and isin != prev_isin:
            table.add_section()
        table.add_row(
            str(lote.fecha),
            isin,
            str(lote.cantidad),
            str(lote.coste_unit.quantize(Decimal("0.0001"))),
        )
        prev_isin = isin

    console.print(table)


def _render_informe(console: Console, data: InformeData) -> None:
    """Orquesta el renderizado a partir de ``InformeData`` precomputado."""

    console.print(
        Rule(
            "[bold]INFORME FISCAL — GANANCIAS/PÉRDIDAS PATRIMONIALES "
            "(IRPF España)[/bold]"
        )
    )
    render_ventas_casadas(console, data.ventas)
    render_resumen_isin(console, data.ventas, data.total_gp)

    if data.incluir_tax:
        render_cuota_irpf(console, data.total_gp, data.cuota_irpf)

    if data.comisiones_conectividad > 0:
        render_comisiones_conectividad(console, data.comisiones_conectividad)

    if data.rentabilidad_neta is not None:
        render_rentabilidad_neta(console, data.rentabilidad_neta)

    render_lotes_pendientes(console, data.lotes_pendientes)


def imprimir_informe(
    ventas: list[Venta],
    lotes: dict[str, deque[Lote]],
    comisiones_conectividad: Decimal = Decimal(0),
    incluir_tax: bool = True,
    console: Console | None = None,
) -> None:
    """
    Imprime el informe completo usando rich.

    Args:
        ventas: Ventas casadas por FIFO.
        lotes: Lotes pendientes por ISIN (cartera abierta).
        comisiones_conectividad: Total de comisiones de conectividad del ejercicio.
        incluir_tax: Si ``False`` omite el bloque de estimación IRPF y la
            rentabilidad neta.
        console: Consola rich a utilizar. Si es ``None`` se crea una por defecto.
    """

    data = build_informe_data(
        ventas, lotes, comisiones_conectividad, incluir_tax=incluir_tax
    )
    _render_informe(console or Console(), data)
