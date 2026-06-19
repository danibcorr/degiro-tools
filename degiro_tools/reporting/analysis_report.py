# Standard libraries
from pathlib import Path

# 3pps
import polars as pl
from rich import box
from rich.console import Console
from rich.table import Table


def weight_color(value: float) -> str:
    """
    Select a Rich color tag based on a weight percentage magnitude.

    Used to visually distinguish high-impact holdings (green) from
    medium (yellow) and low (white) in terminal output.

    Args:
        value: Weight percentage value.

    Returns:
        Rich color name string.
    """

    if value >= 5.0:
        return "green"

    if value >= 1.0:
        return "yellow"

    return "white"


def render_holdings(df: pl.DataFrame, export_path: Path | None = None) -> None:
    """
    Show the top portfolio holdings aggregated by company name.

    Groups all underlying holdings by name and sums their effective
    portfolio weight. Displays the top 50 by weight.

    Args:
        df: Holdings DataFrame with columns name, sector, location,
            effective_pct.
        export_path: Optional CSV export path.

    Returns:
        None.
    """

    df_agg = (
        df.group_by("name")
        .agg(
            pl.col("sector").first(),
            pl.col("location").first(),
            pl.col("effective_pct").sum(),
        )
        .sort("effective_pct", descending=True)
    )

    if export_path:
        df_agg.write_csv(export_path)
        Console().print(f"[green]Exported to {export_path}[/green]")
        return

    console = Console()

    table = Table(
        title="Portfolio Holdings (Top 50)",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", max_width=35, no_wrap=True)
    table.add_column("Sector", max_width=22)
    table.add_column("Country", max_width=16)
    table.add_column("Weight %", justify="right")

    for i, row in enumerate(df_agg.head(50).iter_rows(named=True), 1):
        w = row["effective_pct"]
        c = weight_color(w)

        table.add_row(
            str(i),
            row["name"],
            row["sector"],
            row["location"],
            f"[{c}]{w:.2f}%[/{c}]",
        )

    console.print(table)


def render_overlap(df_overlap: pl.DataFrame, export_path: Path | None = None) -> None:
    """
    Show securities that appear in multiple ETFs.

    Displays the overlap table sorted by effective portfolio weight,
    including the number of ETFs each security appears in.

    Args:
        df_overlap: DataFrame with columns name, etf_count,
            effective_pct.
        export_path: Optional CSV export path.

    Returns:
        None.
    """

    if export_path:
        df_overlap.write_csv(export_path)
        Console().print(f"[green]Exported to {export_path}[/green]")
        return

    console = Console()

    table = Table(
        title="Portfolio Overlap (Securities in 2+ ETFs)",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", max_width=35, no_wrap=True)
    table.add_column("# ETFs", justify="right")
    table.add_column("Effective %", justify="right")

    for i, row in enumerate(df_overlap.head(50).iter_rows(named=True), 1):
        w = row["effective_pct"]
        c = weight_color(w)

        table.add_row(
            str(i),
            row["name"],
            str(row["etf_count"]),
            f"[{c}]{w:.3f}%[/{c}]",
        )

    console.print(table)

    console.print(f"[dim]Total overlapping securities: {len(df_overlap)}[/dim]")


def render_sectors(df_sectors: pl.DataFrame, export_path: Path | None = None) -> None:
    """
    Show sector allocation across the portfolio.

    Displays each sector with its aggregated effective portfolio
    weight percentage.

    Args:
        df_sectors: DataFrame with columns sector, effective_pct.
        export_path: Optional CSV export path.

    Returns:
        None.
    """

    if export_path:
        df_sectors.write_csv(export_path)
        Console().print(f"[green]Exported to {export_path}[/green]")
        return

    console = Console()

    table = Table(
        title="Sector Allocation",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Sector", min_width=25)
    table.add_column("Weight %", justify="right")

    for i, row in enumerate(df_sectors.iter_rows(named=True), 1):
        w = row["effective_pct"]
        c = weight_color(w)

        table.add_row(str(i), row["sector"], f"[{c}]{w:.2f}%[/{c}]")

    console.print(table)


def render_geography(
    df_country: pl.DataFrame,
    df_continent: pl.DataFrame,
    export_path: Path | None = None,
) -> None:
    """
    Show geographic allocation by continent and top countries.

    Renders two tables: first by continent, then top 20 countries.
    With --export, only the country breakdown is saved to CSV.

    Args:
        df_country: DataFrame with columns location, effective_pct.
        df_continent: DataFrame with columns continent, effective_pct.
        export_path: Optional CSV export path.

    Returns:
        None.
    """

    if export_path:
        df_country.write_csv(export_path)
        Console().print(f"[green]Exported to {export_path}[/green]")
        return

    console = Console()

    # Continent table
    t_cont = Table(
        title="Allocation by Continent",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    t_cont.add_column("Continent", min_width=15)
    t_cont.add_column("Weight %", justify="right")

    for row in df_continent.iter_rows(named=True):
        w = row["effective_pct"]
        c = weight_color(w)

        t_cont.add_row(row["continent"], f"[{c}]{w:.2f}%[/{c}]")

    console.print(t_cont)
    console.print()

    # Country table (top 20)
    t_cty = Table(
        title="Allocation by Country (Top 20)",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    t_cty.add_column("#", justify="right", style="dim")
    t_cty.add_column("Country", min_width=18)
    t_cty.add_column("Weight %", justify="right")

    for i, row in enumerate(df_country.head(20).iter_rows(named=True), 1):
        w = row["effective_pct"]
        c = weight_color(w)

        t_cty.add_row(str(i), row["location"], f"[{c}]{w:.2f}%[/{c}]")

    console.print(t_cty)


def render_portfolio(df: pl.DataFrame, export_path: Path | None = None) -> None:
    """
    Show the portfolio valuation as a Rich table.

    Displays each position with type, quantity, current price,
    amount invested, and portfolio weight percentage.

    Args:
        df: DataFrame with columns Producto, Symbol/ISIN, Tipo,
            Cantidad, Precio €, Invertido €, Porcentaje Cartera.
        export_path: Optional CSV export path.

    Returns:
        None.
    """

    if export_path:
        df.write_csv(export_path)
        Console().print(f"[green]Exported to {export_path}[/green]")
        return

    console = Console()

    table = Table(
        title="Portfolio Valuation",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("Product", max_width=40, no_wrap=True)
    table.add_column("Type", justify="center")
    table.add_column("Qty", justify="right")
    table.add_column("Price €", justify="right")
    table.add_column("Invested €", justify="right")
    table.add_column("Weight %", justify="right")

    df_sorted = df.sort("Porcentaje Cartera", descending=True)
    total = df["Total €"].item(0) if df.height > 0 else 0.0

    for row in df_sorted.iter_rows(named=True):
        w = row["Porcentaje Cartera"]
        c = weight_color(w)

        table.add_row(
            row["Producto"],
            row["Tipo"],
            str(row["Cantidad"]),
            f"{row['Precio €']:.2f}",
            f"{row['Invertido €']:.2f}",
            f"[{c}]{w:.2f}%[/{c}]",
        )

    console.print(table)
    console.print(f"[bold]Total: [cyan]{total:.2f}[/cyan] €[/bold]")
