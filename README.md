# Universal Exchange Rates

`universal_exchange_rates` is a lightweight Python library that makes it
simple to fetch foreign exchange rates and convert between currencies
without needing an API key.  It wraps the free and open‐source
exchange rate data published by the
[fawazahmed0/exchange‑api](https://github.com/fawazahmed0/exchange-api)
project, which provides **daily updates**, **no rate limits** and
supports over **200 currencies**【957031637096005†L11-L16】.

The motivation for this library is to offer a more intuitive interface
than existing tools.  For example, the European Central Bank API
requires specifying a start and end date even when you only care about
the latest values.  Similarly, popular libraries such as
`forex-python` rely on remote services that are frequently unstable.
`universal_exchange_rates` aims to be robust by default: it lets you
ask for the latest rates with a single call, optionally specify
historical dates or ranges, select specific target currencies, and
performs automatic failover between multiple data mirrors【957031637096005†L62-L70】.

## Installation

The package is self‑contained and has no external dependencies beyond
the standard library and `requests`.  You can install it directly
from a git checkout:

```bash
pip install path/to/universal_exchange_rates
```

Alternatively, copy the `universal_exchange_rates` directory into your
project.

## Quick Start

```python
from universal_exchange_rates import ExchangeRateAPI

# Create an API client (defaults to USD base currency)
api = ExchangeRateAPI()

# Get the latest rates for a few target currencies
latest = api.get_rates(symbols=["eur", "cad"])
print(latest)  # e.g. {'eur': 0.8651, 'cad': 1.3780}

# Convert 100 Canadian dollars to Euros using the latest rates
eur_amount = api.convert(100, to_currency="eur", from_currency="cad")
print(f"100 CAD = {eur_amount:.2f} EUR")

# Fetch historical rates for a date range
series = api.get_historical_rates("2024-06-01", "2024-06-07", symbols=["eur", "gbp"])
for date, rates in series.items():
    print(date, rates)

# List all available currencies
codes = api.available_currencies()
print(f"Supported currencies: {codes[:10]} ...")
```

## API Reference

### `ExchangeRateAPI(base_currency='USD', api_version='v1', timeout=5)`

Construct a new client.  The `base_currency` sets the default source
currency; it can be overridden per call.

### `get_rates(base=None, date=None, symbols=None) -> dict`

Return a mapping of currency codes to rates for the specified base
currency and date.  You can supply a subset of `symbols` to filter the
result.  Omitting `date` uses the most recent snapshot.

### `convert(amount, to_currency, *, from_currency=None, date=None) -> float`

Convert an `amount` from one currency to another.  If
`from_currency` is omitted the instance’s `base_currency` is used.
An optional `date` lets you perform historical conversions.

### `get_historical_rates(start_date, end_date, *, base=None, symbols=None) -> dict`

Return a dictionary keyed by ISO date strings where each value is
itself a dictionary of rates.  Useful for building time series.

### `available_currencies(date=None) -> list`

Return a sorted list of supported currency codes.  Omitting `date`
uses the latest snapshot.

## Notes on Data Source

The underlying data is provided by the `fawazahmed0/exchange‑api`
project.  It publishes daily snapshots of exchange rates via a CDN.
Snapshots are addressed by date; the special `latest` alias resolves to
the most recent snapshot.  JSON files live at URLs of the form:

```
https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/{version}/currencies/{base}.json
```

where `date` is `latest` or `YYYY‑MM‑DD`, and `version` is currently
`v1`【957031637096005†L19-L27】.  See the upstream project’s README for
more examples and details【957031637096005†L45-L60】.  In case the
jsDelivr CDN is unavailable the library automatically falls back to
the Cloudflare mirror【957031637096005†L62-L70】.

## License

This project is licensed under the MIT License.  See the
`LICENSE` file for details.