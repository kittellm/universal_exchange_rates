"""Basic tests for the ExchangeRateAPI client.

These tests exercise the public API and ensure that the client can
retrieve data from the upstream service.  They are deliberately light
weight so they do not exhaust the underlying service.  To run the tests
simply execute:

    pytest tests/test_api.py

Note that the tests require an internet connection.  They will be
skipped automatically if network access is unavailable.
"""

import pytest

from universal_exchange_rates import ExchangeRateAPI


def has_network() -> bool:
    try:
        import socket
        socket.create_connection(("cdn.jsdelivr.net", 443), timeout=2)
        return True
    except OSError:
        return False


network_available = pytest.mark.skipif(
    not has_network(), reason="Network is required for live API tests"
)


@network_available
def test_get_latest_rates_subset():
    api = ExchangeRateAPI(base_currency="usd")
    rates = api.get_rates(symbols=["eur", "cad"])
    assert set(rates.keys()) == {"eur", "cad"}
    assert all(isinstance(v, float) for v in rates.values())


@network_available
def test_convert_between_currencies():
    api = ExchangeRateAPI()
    amount_cad = 100
    # Convert to EUR and back to CAD; due to daily rounding and mid‑market rates
    # the roundtrip may not return exactly the original amount but should be
    # reasonably close.
    eur = api.convert(amount_cad, to_currency="eur", from_currency="cad")
    cad = api.convert(eur, to_currency="cad", from_currency="eur")
    assert isinstance(eur, float) and isinstance(cad, float)
    # Roundtrip should preserve value within 5% due to market spreads
    assert abs(cad - amount_cad) / amount_cad < 0.05


@network_available
def test_historical_range():
    api = ExchangeRateAPI(base_currency="usd")
    # Use a date range for which snapshots are known to exist in the upstream dataset.
    start, end = "2024-03-06", "2024-03-07"
    series = api.get_historical_rates(start, end, symbols=["eur"])
    # Expect two entries (inclusive range)
    assert len(series) == 2
    for date_str, daily in series.items():
        assert "eur" in daily
        assert isinstance(daily["eur"], float)