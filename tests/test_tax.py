# Standard libraries
from datetime import date
from decimal import Decimal

# 3pps
import pytest

# Own modules
from degiro_tools import Sale, build_report_data, calculate_irpf_quota

EXPECTED_BRACKETS_10K = 2
EXPECTED_BRACKETS_60K = 3
EXPECTED_BRACKETS_TOP = 5


@pytest.mark.parametrize("total", [Decimal(0), Decimal("-50"), Decimal("-0.01")])
def test_no_gain_returns_empty_list(total: Decimal) -> None:
    """
    Verify a null or negative gain produces an empty breakdown.
    """

    assert calculate_irpf_quota(total) == []


def test_single_bracket_100_eur() -> None:
    """
    Verify the quota in the first bracket (100 EUR at 19%).
    """

    breakdown = calculate_irpf_quota(Decimal("100"))

    assert len(breakdown) == 1
    bracket = breakdown[0]
    assert bracket.rate == Decimal("0.19")
    assert bracket.base == Decimal("100.00")
    assert bracket.quota == Decimal("19.00")


def test_first_bracket_limit_6000() -> None:
    """
    Verify that exactly 6,000 EUR stays in the first bracket at 19%.
    """

    breakdown = calculate_irpf_quota(Decimal("6000"))
    assert len(breakdown) == 1
    # 6000 * 0.19 = 1140
    assert sum(bracket.quota for bracket in breakdown) == Decimal("1140.00")


def test_two_brackets_10000() -> None:
    """
    Verify that 10,000 EUR is distributed across the first two brackets.
    """

    # 6000 @ 19% = 1140 + 4000 @ 21% = 840 -> 1980
    breakdown = calculate_irpf_quota(Decimal("10000"))

    assert len(breakdown) == EXPECTED_BRACKETS_10K
    assert sum(bracket.quota for bracket in breakdown) == Decimal("1980.00")
    assert breakdown[1].rate == Decimal("0.21")
    assert breakdown[1].base == Decimal("4000.00")


def test_three_brackets_60000() -> None:
    """
    Verify that 60,000 EUR is distributed across the first three
    brackets.
    """

    # 6000@19 + 44000@21 + 10000@23 = 1140 + 9240 + 2300 = 12680
    breakdown = calculate_irpf_quota(Decimal("60000"))

    assert len(breakdown) == EXPECTED_BRACKETS_60K
    assert sum(bracket.quota for bracket in breakdown) == Decimal("12680.00")


@pytest.mark.parametrize(
    ("total", "n_brackets", "expected_quota"),
    [
        # exact boundary bracket 1
        (Decimal("6000"), 1, Decimal("1140.00")),
        # barely crosses to bracket 2 (0.01*0.21 = 0.0021 -> quantize 0.00)
        (Decimal("6000.01"), 2, Decimal("1140.00")),
        # exact boundary bracket 2 (6000@19 + 44000@21 = 1140 + 9240)
        (Decimal("50000"), 2, Decimal("10380.00")),
        # exact boundary bracket 3 (+150000@23 = 34500)
        (Decimal("200000"), 3, Decimal("44880.00")),
        # exact boundary bracket 4 (+100000@27 = 27000)
        (Decimal("300000"), 4, Decimal("71880.00")),
        # barely crosses to bracket 5 (0.01*0.30 = 0.003 -> quantize 0.00)
        (Decimal("300000.01"), 5, Decimal("71880.00")),
    ],
)
def test_irpf_bracket_boundaries(
    total: Decimal, n_brackets: int, expected_quota: Decimal
) -> None:
    """
    Verify bracket count and total quota at each savings-bracket
    boundary.
    """

    breakdown = calculate_irpf_quota(total)

    assert len(breakdown) == n_brackets
    assert sum(bracket.quota for bracket in breakdown) == expected_quota


def test_last_bracket_without_upper() -> None:
    """
    Verify the last active bracket (>300,000) leaves ``upper=None``.
    """

    breakdown = calculate_irpf_quota(Decimal("400000"))

    assert breakdown[-1].upper is None
    assert breakdown[-1].rate == Decimal("0.30")


def test_top_bracket_quota_400000() -> None:
    """
    Verify the full quota when the top 30% bracket is active.
    """

    # 71,880 (first four brackets) + 100,000 @ 30% = 101,880.00.
    breakdown = calculate_irpf_quota(Decimal("400000"))

    assert len(breakdown) == EXPECTED_BRACKETS_TOP
    assert sum(bracket.quota for bracket in breakdown) == Decimal("101880.00")


def test_negative_total_yields_no_quota_or_net_return() -> None:
    """
    Verify a net loss produces no IRPF quota and no net return.
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

    report = build_report_data(
        sales, {}, connectivity_fees=Decimal(0), include_tax=True
    )

    assert report.irpf_quota is None
    assert report.net_return is None
