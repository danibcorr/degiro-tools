# 3pps
import pytest

# Own modules
from degiro_tools.providers import yahoo
from degiro_tools.providers.yahoo import get_price_eur, get_usd_eur_rate, is_etf


@pytest.mark.parametrize(
    "product_name",
    [
        "Global X Robotics & Artificial Intelligence UCITS ETF",
        "State Street SPDR S&P 500 UCITS ETF",
        "First Trust NASDAQ-100 Equal Weighted ETF",
        "J.P. Morgan Global Equity Premium Income UCITS ETF",
        "Goldman Sachs Physical Gold ETF",
        "Franklin Templeton FTSE India UCITS ETF",
    ],
)
def test_is_etf_detects_multi_word_brands(product_name: str) -> None:
    """
    Multi-word provider brands are recognized as ETFs.
    """

    assert is_etf(product_name)


@pytest.mark.parametrize(
    "product_name",
    [
        "iShares Core MSCI World UCITS ETF USD (Acc)",
        "VANGUARD FTSE All-World UCITS ETF",
        "Xtrackers MSCI World UCITS ETF 1C",
    ],
)
def test_is_etf_detects_single_word_brands(product_name: str) -> None:
    """
    Single-word provider brands are still recognized as ETFs.
    """

    assert is_etf(product_name)


def test_is_etf_does_not_match_plain_stock() -> None:
    """
    A genuine stock name must not be flagged as an ETF.
    """

    assert not is_etf("INDRA SISTEMAS SA")


class StubTicker:
    """
    Minimal yfinance.Ticker stand-in for deterministic tests.
    """

    def __init__(
        self,
        fast_info: dict[str, object] | None = None,
        info: dict[str, object] | None = None,
        *,
        fast_raises: bool = False,
    ) -> None:
        """
        Store canned payloads and the optional fast_info failure flag.
        """

        self._fast_info = fast_info or {}
        self._info = info or {}
        self._fast_raises = fast_raises

    @property
    def fast_info(self) -> dict[str, object]:
        """
        Return canned fast_info or raise to trigger the fallback.
        """

        if self._fast_raises:
            raise KeyError("fast_info unavailable")

        return self._fast_info

    @property
    def info(self) -> dict[str, object]:
        """
        Return the canned full info payload.
        """

        return self._info


def test_get_usd_eur_rate_returns_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A successful fast_info lookup yields the exchange rate.
    """

    monkeypatch.setattr(
        yahoo.yf, "Ticker", lambda _symbol: StubTicker({"lastPrice": 0.92})
    )

    assert get_usd_eur_rate() == pytest.approx(0.92)


def test_get_usd_eur_rate_returns_none_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A network failure is caught and yields None, not a crash.
    """

    def boom(_symbol: str) -> StubTicker:
        raise ConnectionError("network down")

    monkeypatch.setattr(yahoo.yf, "Ticker", boom)

    assert get_usd_eur_rate() is None


def test_get_price_eur_converts_usd_with_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A USD price is converted to EUR using the supplied rate.
    """

    monkeypatch.setattr(
        yahoo, "get_ticker_from_isin", lambda _isin, logger=None: "AAPL"
    )
    monkeypatch.setattr(
        yahoo.yf,
        "Ticker",
        lambda _symbol: StubTicker({"lastPrice": 100.0, "currency": "USD"}),
    )

    assert get_price_eur("ISIN_USD", 0.9) == pytest.approx(90.0)


def test_get_price_eur_keeps_eur_price_unconverted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A EUR price is returned as-is, even without a conversion rate.
    """

    monkeypatch.setattr(
        yahoo, "get_ticker_from_isin", lambda _isin, logger=None: "ASML.AS"
    )
    monkeypatch.setattr(
        yahoo.yf,
        "Ticker",
        lambda _symbol: StubTicker({"lastPrice": 50.0, "currency": "EUR"}),
    )

    assert get_price_eur("ISIN_EUR", None) == pytest.approx(50.0)


def test_get_price_eur_usd_without_rate_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A USD price with no rate cannot be converted and yields None.
    """

    monkeypatch.setattr(
        yahoo, "get_ticker_from_isin", lambda _isin, logger=None: "AAPL"
    )
    monkeypatch.setattr(
        yahoo.yf,
        "Ticker",
        lambda _symbol: StubTicker({"lastPrice": 100.0, "currency": "USD"}),
    )

    assert get_price_eur("ISIN_USD", None) is None


def test_get_price_eur_returns_none_when_no_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    An unresolved ISIN yields None instead of crashing.
    """

    monkeypatch.setattr(yahoo, "get_ticker_from_isin", lambda _isin, logger=None: None)

    assert get_price_eur("ISIN_UNKNOWN", 0.9) is None


def test_get_price_eur_falls_back_to_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    When fast_info fails, the info payload provides the price.
    """

    monkeypatch.setattr(yahoo, "get_ticker_from_isin", lambda _isin, logger=None: "X")
    monkeypatch.setattr(
        yahoo.yf,
        "Ticker",
        lambda _symbol: StubTicker(
            info={"regularMarketPreviousClose": 10.0, "currency": "EUR"},
            fast_raises=True,
        ),
    )

    assert get_price_eur("ISIN_FALLBACK", None) == pytest.approx(10.0)
