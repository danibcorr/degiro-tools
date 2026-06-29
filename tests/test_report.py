# Standard libraries
import io
from collections import defaultdict, deque
from datetime import date
from decimal import Decimal

# 3pps
import pytest
from rich.console import Console

# Own modules
from degiro_tools import Lot, Sale, print_report


@pytest.fixture
def simple_sales() -> list[Sale]:
    """
    Return a synthetic sale with a positive gain/loss of 50 EUR.
    """

    return [
        Sale(
            date=date(2026, 3, 1),
            isin="IE0000000099",
            product="TEST",
            quantity=10,
            acquisition_cost=Decimal("100.00"),
            transfer_value=Decimal("150.00"),
            gain_loss=Decimal("50.00"),
        )
    ]


@pytest.fixture
def one_pending_lot() -> dict[str, deque[Lot]]:
    """
    Portfolio with a single pending lot.
    """

    lots: dict[str, deque[Lot]] = defaultdict(deque)
    lots["IE0000000099"].append(
        Lot(quantity=5, unit_cost=Decimal("10.00"), date=date(2026, 1, 15))
    )
    return lots


def make_console() -> tuple[Console, io.StringIO]:
    """
    Create a colorless rich console captured in a StringIO.
    """

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, no_color=True, width=200)
    return console, buf


def test_print_report_includes_sections_with_tax(
    simple_sales: list[Sale],
    one_pending_lot: dict[str, deque[Lot]],
) -> None:
    """
    Verify that with tax all the key sections are printed.
    """

    console, buf = make_console()
    print_report(
        simple_sales,
        one_pending_lot,
        connectivity_fees=Decimal("5.00"),
        include_tax=True,
        console=console,
    )
    out = buf.getvalue()

    assert "Ventas casadas" in out
    assert "TOTAL GANANCIA/PÉRDIDA PATRIMONIAL" in out
    assert "50.00" in out
    assert "Estimación cuota IRPF" in out
    assert "CUOTA ESTIMADA TOTAL" in out
    assert "9.50" in out
    assert "RENTABILIDAD NETA REAL" in out
    assert "Cartera abierta" in out
    assert "IE0000000099" in out


def test_print_report_no_tax_omits_fiscal_blocks(
    simple_sales: list[Sale],
    one_pending_lot: dict[str, deque[Lot]],
) -> None:
    """
    Verify that ``--no-tax`` omits the IRPF quota and net return.
    """

    console, buf = make_console()
    print_report(
        simple_sales,
        one_pending_lot,
        connectivity_fees=Decimal(0),
        include_tax=False,
        console=console,
    )
    out = buf.getvalue()

    assert "Estimación cuota IRPF" not in out
    assert "RENTABILIDAD NETA" not in out
    assert "TOTAL GANANCIA/PÉRDIDA PATRIMONIAL" in out


def test_print_report_without_sales() -> None:
    """
    Verify that without sales it prints total 0 and no net return.
    """

    console, buf = make_console()
    print_report([], defaultdict(deque), include_tax=True, console=console)
    out = buf.getvalue()

    assert "TOTAL GANANCIA/PÉRDIDA PATRIMONIAL" in out
    assert "0.00" in out
    assert "Sin ventas en el ejercicio." in out
    assert "RENTABILIDAD NETA" not in out
    assert "Sin cuota" in out


def test_print_report_empty_portfolio(
    simple_sales: list[Sale],
) -> None:
    """
    Verify the message when no pending lots remain.
    """

    console, buf = make_console()
    print_report(simple_sales, defaultdict(deque), include_tax=True, console=console)
    out = buf.getvalue()

    assert "Sin cartera abierta." in out


def test_print_report_connectivity_fees_hidden_when_zero(
    simple_sales: list[Sale],
) -> None:
    """
    Verify the connectivity block is omitted when there are no fees.
    """

    console, buf = make_console()
    print_report(
        simple_sales,
        defaultdict(deque),
        connectivity_fees=Decimal(0),
        include_tax=True,
        console=console,
    )
    out = buf.getvalue()

    assert "Comisiones de conectividad" not in out


def test_print_report_loss_hides_net_return(
    one_pending_lot: dict[str, deque[Lot]],
) -> None:
    """
    Verify that a loss does not produce a net return computation.
    """

    sales = [
        Sale(
            date=date(2026, 3, 1),
            isin="IE0000000099",
            product="TEST",
            quantity=10,
            acquisition_cost=Decimal("200.00"),
            transfer_value=Decimal("150.00"),
            gain_loss=Decimal("-50.00"),
        )
    ]

    console, buf = make_console()
    print_report(sales, one_pending_lot, include_tax=True, console=console)
    out = buf.getvalue()

    assert "RENTABILIDAD NETA" not in out
    assert "Sin cuota" in out
