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
from ..calculation.report_data import build_report_data
from ..domain.constants import CENT_QUANTIZE
from ..domain.models import Lot, ReportData, Sale, TaxBracket


def fmt(value: Decimal) -> str:
    """
    Format a Decimal to 2 decimal places without thousands separator.

    Args:
        value: Decimal value to format.

    Returns:
        Formatted string with 2 decimal places.
    """

    return str(value.quantize(CENT_QUANTIZE, rounding=ROUND_HALF_UP))


def gp_text(gain_loss: Decimal, *, bold: bool = True) -> Text:
    """
    Build a colored Rich Text based on the sign of a gain/loss.

    Args:
        gain_loss: Gain or loss amount.
        bold: Whether to use bold styling.

    Returns:
        Rich Text with green (positive) or red (negative) styling.
    """

    color = "green" if gain_loss >= 0 else "red"
    style = f"bold {color}" if bold else color
    return Text(fmt(gain_loss), style=style)


def render_matched_sales(console: Console, sales: list[Sale]) -> None:
    """
    Render the table of FIFO-matched sales.

    Args:
        console: Rich Console instance for output.
        sales: List of matched sales.

    Returns:
        None.
    """

    console.print(Rule("[bold]Ventas casadas (FIFO por ISIN)[/bold]"))
    console.print("[dim]valores en EUR reales del broker[/dim]")

    if not sales:
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

    for sale in sales:
        table.add_row(
            str(sale.date),
            sale.isin,
            sale.product,
            str(sale.quantity),
            fmt(sale.acquisition_cost),
            fmt(sale.transfer_value),
            gp_text(sale.gain_loss),
        )

    console.print(table)


def render_isin_summary(
    console: Console, sales: list[Sale], total_gain_loss: Decimal
) -> None:
    """
    Render the per-ISIN summary and highlighted total gain/loss.

    Args:
        console: Rich Console instance for output.
        sales: List of matched sales.
        total_gain_loss: Total gain or loss across all sales.

    Returns:
        None.
    """

    console.print(Rule("[bold]Resumen por ISIN[/bold]"))

    gain_loss_by_isin: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    for sale in sales:
        gain_loss_by_isin[sale.isin] += sale.gain_loss

    if gain_loss_by_isin:
        table = Table(box=box.ROUNDED, header_style="bold", expand=False)
        table.add_column("ISIN")
        table.add_column("G/P acumulada (EUR)", justify="right")
        for isin, gain_loss in gain_loss_by_isin.items():
            table.add_row(isin, gp_text(gain_loss, bold=False))
        console.print(table)

    if total_gain_loss > 0:
        color = "green"
    elif total_gain_loss < 0:
        color = "red"
    else:
        color = "yellow"

    console.print(
        Panel(
            Text(
                f"{fmt(total_gain_loss)} EUR",
                style=f"bold {color}",
                justify="center",
            ),
            title="[bold]TOTAL GANANCIA/PÉRDIDA PATRIMONIAL[/bold]",
            border_style=color,
            box=box.HEAVY,
        )
    )


def build_brackets_table(irpf_quota: list[TaxBracket], total_quota: Decimal) -> Table:
    """
    Build a Rich table with tax brackets and total tax row.

    Args:
        irpf_quota: List of tax bracket breakdowns.
        total_quota: Total estimated tax amount.

    Returns:
        Rich Table with brackets and total.
    """

    table = Table(box=box.ROUNDED, header_style="bold", expand=False)
    table.add_column("Desde", justify="right")
    table.add_column("Hasta", justify="right")
    table.add_column("Tipo", justify="right")
    table.add_column("Base", justify="right")
    table.add_column("Cuota", justify="right")

    for bracket in irpf_quota:
        table.add_row(
            fmt(bracket.lower),
            fmt(bracket.upper) if bracket.upper is not None else "∞",
            f"{int(bracket.rate * 100)}%",
            fmt(bracket.base),
            fmt(bracket.quota),
        )

    table.add_section()
    table.add_row(
        "",
        "",
        "",
        Text("CUOTA ESTIMADA TOTAL", style="bold"),
        Text(fmt(total_quota), style="bold yellow"),
    )
    return table


def render_irpf_quota(
    console: Console, total_gain_loss: Decimal, irpf_quota: list[TaxBracket] | None
) -> None:
    """
    Render the IRPF tax estimation and net after-tax amount.

    Args:
        console: Rich Console instance for output.
        total_gain_loss: Total gain or loss.
        irpf_quota: Tax bracket breakdown, or None if not applicable.

    Returns:
        None.
    """

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

    if not irpf_quota:
        console.print(
            "[dim]Sin cuota: no hay ganancia neta positiva en el ejercicio.[/dim]"
        )
        return

    total_quota = sum((bracket.quota for bracket in irpf_quota), Decimal(0))
    console.print(build_brackets_table(irpf_quota, total_quota))

    net = (total_gain_loss - total_quota).quantize(
        CENT_QUANTIZE, rounding=ROUND_HALF_UP
    )
    console.print(
        Panel(
            Text(f"{fmt(net)} EUR", style="bold cyan", justify="center"),
            title="[bold]Neto después de impuestos[/bold]",
            border_style="cyan",
            box=box.HEAVY,
        )
    )


def render_connectivity_fees(console: Console, connectivity_fees: Decimal) -> None:
    """
    Render the connectivity fees block not attributed to operations.

    Args:
        console: Rich Console instance for output.
        connectivity_fees: Total connectivity fees in EUR.

    Returns:
        None.
    """

    console.print(Rule("[bold]Gastos de custodia no imputados a operaciones[/bold]"))
    console.print(
        f"[dim]Comisiones de conectividad: {fmt(connectivity_fees)} EUR[/dim]"
    )
    console.print(
        "[dim]No se suman al coste FIFO; declarables por separado según "
        "tu situación fiscal.[/dim]"
    )


def render_net_return(console: Console, net_return: Decimal) -> None:
    """
    Render the final net return panel after taxes and fees.

    Args:
        console: Rich Console instance for output.
        net_return: Net return amount in EUR.

    Returns:
        None.
    """

    if net_return > 0:
        color = "green"
    elif net_return < 0:
        color = "red"
    else:
        color = "yellow"

    console.print(
        Panel(
            Text(
                f"{fmt(net_return)} EUR",
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


def render_pending_lots(console: Console, lots: dict[str, deque[Lot]]) -> None:
    """
    Render the open portfolio (pending lots) grouped by ISIN.

    Args:
        console: Rich Console instance for output.
        lots: Dict mapping ISIN to deque of remaining lots.

    Returns:
        None.
    """

    console.print(Rule("[bold]Cartera abierta (lotes pendientes)[/bold]"))

    items: list[tuple[str, Lot]] = [
        (isin, lot) for isin in sorted(lots) for lot in lots[isin]
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
    for isin, lot in items:
        if prev_isin is not None and isin != prev_isin:
            table.add_section()
        table.add_row(
            str(lot.date),
            isin,
            str(lot.quantity),
            str(lot.unit_cost.quantize(Decimal("0.0001"))),
        )
        prev_isin = isin

    console.print(table)


def render_report_sections(console: Console, data: ReportData) -> None:
    """
    Orchestrate the rendering from precomputed ReportData.

    Args:
        console: Rich Console instance for output.
        data: Precomputed report data with sales, taxes, and lots.

    Returns:
        None.
    """

    console.print(
        Rule(
            "[bold]INFORME FISCAL — GANANCIAS/PÉRDIDAS PATRIMONIALES "
            "(IRPF España)[/bold]"
        )
    )
    render_matched_sales(console, data.sales)
    render_isin_summary(console, data.sales, data.total_gain_loss)

    if data.include_tax:
        render_irpf_quota(console, data.total_gain_loss, data.irpf_quota)

    if data.connectivity_fees > 0:
        render_connectivity_fees(console, data.connectivity_fees)

    if data.net_return is not None:
        render_net_return(console, data.net_return)

    render_pending_lots(console, data.pending_lots)


def print_report(
    sales: list[Sale],
    lots: dict[str, deque[Lot]],
    connectivity_fees: Decimal = Decimal(0),
    include_tax: bool = True,
    console: Console | None = None,
) -> None:
    """
    Print the full report using rich.

    Args:
        sales: Sales matched by FIFO.
        lots: Pending lots per ISIN (open portfolio).
        connectivity_fees: Total connectivity fees for the period.
        include_tax: If ``False`` omit the IRPF estimation block and
            the net return.
        console: Rich console to use. If ``None`` a default one is
            created.
    """

    data = build_report_data(sales, lots, connectivity_fees, include_tax=include_tax)
    render_report_sections(console or Console(), data)
