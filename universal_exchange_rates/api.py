"""A simple yet powerful exchange rate API client.

This module exposes a :class:`ExchangeRateAPI` class that makes it easy to
retrieve foreign exchange rates and convert between currencies without
requiring an API key.  Under the hood it uses the free, open‑source
currency data published by the `fawazahmed0/exchange‑api` project.  That
project publishes daily snapshots of exchange rates for more than 200
currencies (including major fiat currencies, cryptocurrencies and a few
precious metals) and makes them available via a CDN.  A summary of the
service is reproduced below:

* The data is **free**, **daily updated** and **has no rate limits**【957031637096005†L11-L16】.
* Rates are available for a specific **date** (in ``YYYY‑MM‑DD`` format) or
  for the special ``latest`` date which always resolves to the most recent
  snapshot【957031637096005†L24-L27】.
* A base currency can be chosen simply by requesting
  ``/currencies/{base}.json``【957031637096005†L45-L56】.
* A comprehensive list of available currency codes can be obtained from
  ``/currencies.json``【957031637096005†L34-L40】.

The :class:`ExchangeRateAPI` class wraps these endpoints and adds
conveniences such as:

* Retrieving the latest rates or historical rates for a given date.
* Selecting a subset of target currencies or returning all available rates.
* Fetching a series of rates across a date range.
* Converting an amount from one currency to another using the retrieved
  rates.
* Automatic failover between the jsDelivr CDN and a Cloudflare fallback,
  as recommended by the upstream project【957031637096005†L62-L70】.

The class is designed to be robust and easy to use.  It does not depend
on any external API keys, but it does rely on an internet connection to
fetch the JSON files.  Internally it caches responses to minimise
duplicate downloads during the lifetime of the object.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import requests


class ExchangeRateAPIError(Exception):
    """Custom exception raised by :class:`ExchangeRateAPI` on errors."""


class ExchangeRateAPI:
    """Client for retrieving foreign exchange rates from an open source API.

    Parameters
    ----------
    base_currency : str, optional
        The three‑letter ISO 4217 code of the currency to use as the base
        for all conversions.  Defaults to ``"USD"``.
    api_version : str, optional
        The API version string.  At time of writing the upstream service
        exposes only a single version (``"v1"``), but this parameter is
        provided for forward compatibility.  Defaults to ``"v1"``.
    timeout : float or tuple, optional
        Timeout (in seconds) passed directly to :func:`requests.get` when
        fetching data.  You may supply a single float or a ``(connect,
        read)`` tuple.  Defaults to ``5`` seconds.

    Notes
    -----
    The underlying data is cached in memory for the lifetime of the
    instance.  If you wish to force a refresh of the latest data you can
    create a new instance or call :meth:`clear_cache`.
    """

    # Base URLs for the upstream service.  The first entry is the primary
    # jsDelivr CDN; the second entry is the Cloudflare fallback.  The
    # ``{date}`` placeholder will be replaced with a date string such as
    # ``latest`` or ``2024-03-06`` during runtime.
    _BASE_URLS: Sequence[str] = (
        "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/{version}/{endpoint}",
        "https://{date}.currency-api.pages.dev/{version}/{endpoint}",
    )

    def __init__(
        self,
        base_currency: str = "USD",
        api_version: str = "v1",
        timeout: Union[float, Tuple[float, float]] = 5,
    ) -> None:
        self.base_currency = base_currency.lower()
        self.api_version = api_version
        self.timeout = timeout
        # Internal cache mapping (date, base) -> rates dict
        self._cache: Dict[Tuple[str, str], Dict[str, float]] = {}

    # ------------------------------------------------------------------
    # High level public methods
    # ------------------------------------------------------------------
    def get_rates(
        self,
        *,
        base: Optional[str] = None,
        date: Optional[str] = None,
        symbols: Optional[Iterable[str]] = None,
    ) -> Dict[str, float]:
        """Retrieve exchange rates for a given base currency and date.

        Parameters
        ----------
        base : str, optional
            The ISO 4217 code of the currency to use as the base.  If
            omitted, the instance's default `base_currency` is used.
        date : str, optional
            The date for which to retrieve rates.  Must be ``"latest"``
            or in ``YYYY‑MM‑DD`` format.  If omitted, ``"latest"`` is used.
        symbols : iterable of str, optional
            An iterable of target currency codes.  If provided the returned
            dictionary will include only these currencies (case‑insensitive).
            If omitted or empty all available rates are returned.

        Returns
        -------
        dict
            A mapping from target currency code (lowercase) to the
            number of units of the **target** currency obtainable from
            one unit of the base currency.  For example ``{"eur": 0.92}``
            means that one US dollar buys 0.92 euros.  The reciprocal of
            this value (1/0.92 ≈ 1.09) gives the number of base currency
            units required to buy one unit of the target.

        Raises
        ------
        ExchangeRateAPIError
            If the base currency is invalid, the date is malformed or the
            upstream API cannot be reached.
        """
        # Normalise input
        base_code = (base or self.base_currency).lower()
        date_str = date or "latest"
        if symbols is not None:
            # Convert to lower case for case‑insensitive lookup
            wanted = {c.lower() for c in symbols}
        else:
            wanted = None

        # Fetch rates from cache or upstream
        rates = self._get_rates_for(date_str, base_code)

        if wanted:
            missing = wanted - rates.keys()
            if missing:
                raise ExchangeRateAPIError(
                    f"Unknown currency code(s) for base {base_code}: {', '.join(sorted(missing))}"
                )
            return {k: rates[k] for k in wanted}
        else:
            return dict(rates)  # return a copy to prevent accidental mutation

    def convert(
        self,
        amount: Union[int, float],
        to_currency: str,
        *,
        from_currency: Optional[str] = None,
        date: Optional[str] = None,
    ) -> float:
        """Convert an amount from one currency to another.

        Parameters
        ----------
        amount : float
            The numeric amount in the source currency.
        to_currency : str
            The ISO 4217 code of the currency to convert to.
        from_currency : str, optional
            The ISO 4217 code of the currency you are converting from.  If
            omitted the instance's default `base_currency` is used.
        date : str, optional
            The date for which to apply the conversion.  Must be ``"latest"``
            or ``YYYY‑MM‑DD``.  If omitted ``"latest"`` is used.

        Returns
        -------
        float
            The converted amount in the target currency.

        Raises
        ------
        ExchangeRateAPIError
            If either currency code is invalid or the date is malformed.
        """
        if not isinstance(amount, (int, float)):
            raise TypeError("amount must be a numeric type")

        # Normalise codes
        from_code = (from_currency or self.base_currency).lower()
        to_code = to_currency.lower()
        date_str = date or "latest"

        # Retrieve rates for both currencies relative to a common base.  We
        # choose USD as the internal base for cross conversions because the
        # underlying data includes every supported currency in each JSON
        # snapshot, so it doesn't matter which base we use here.  Using a
        # consistent base avoids having to fetch two separate snapshots.
        common_base = "usd"
        rates = self._get_rates_for(date_str, common_base)

        # Ensure both currencies exist in the snapshot
        if from_code not in rates:
            raise ExchangeRateAPIError(f"Unknown from_currency code: {from_code}")
        if to_code not in rates:
            raise ExchangeRateAPIError(f"Unknown to_currency code: {to_code}")

        # Compute conversion: amount_in_common_base = amount / rate[from]
        # and then amount_in_target = amount_in_common_base * rate[to].
        # Note: rates are defined as: base -> target, i.e. how many units of
        # base buy one target.  Therefore to convert from 'from_currency' to
        # the common base we divide by its rate and then multiply by the
        # target's rate.
        rate_from = rates[from_code]
        rate_to = rates[to_code]
        amount_in_common_base = amount / rate_from
        converted = amount_in_common_base * rate_to
        return converted

    def get_historical_rates(
        self,
        start_date: Union[str, _dt.date],
        end_date: Union[str, _dt.date],
        *,
        base: Optional[str] = None,
        symbols: Optional[Iterable[str]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Retrieve rates over a range of dates.

        This method iterates from ``start_date`` to ``end_date`` inclusive and
        collects the exchange rates for each day.  Dates on which data is
        unavailable will raise an :class:`ExchangeRateAPIError`.  Use this
        method to build time series for analysis or to compute rolling
        statistics.

        Parameters
        ----------
        start_date : str or datetime.date
            The start of the date range (inclusive).  If a string it must be
            in ``YYYY‑MM‑DD`` format.
        end_date : str or datetime.date
            The end of the date range (inclusive).  If a string it must be in
            ``YYYY‑MM‑DD`` format.
        base : str, optional
            The base currency to use.  Defaults to the instance's base.
        symbols : iterable of str, optional
            A set of target currencies to include.  If omitted all available
            currencies are returned for each date.

        Returns
        -------
        dict
            A mapping from date string to a dictionary of rates as returned by
            :meth:`get_rates`.
        """
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        if start > end:
            raise ValueError("start_date must be on or before end_date")

        result: Dict[str, Dict[str, float]] = {}
        current = start
        while current <= end:
            date_str = current.isoformat()
            result[date_str] = self.get_rates(base=base, date=date_str, symbols=symbols)
            current += _dt.timedelta(days=1)
        return result

    def available_currencies(self, *, date: Optional[str] = None) -> List[str]:
        """Return a sorted list of all available currency codes.

        Parameters
        ----------
        date : str, optional
            The date for which to list available currencies.  If omitted
            ``"latest"`` is used.  Note that the set of currencies may
            change over time as new currencies or tokens are added.

        Returns
        -------
        list of str
            Sorted list of currency codes in lowercase.
        """
        date_str = date or "latest"
        # Arbitrarily choose USD base to get the list of keys.  Any base
        # currency would suffice because each snapshot includes every currency.
        rates = self._get_rates_for(date_str, "usd")
        return sorted(rates.keys())

    def clear_cache(self) -> None:
        """Clear the in‑memory cache of previously fetched rates."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Internal helper methods
    # ------------------------------------------------------------------
    def _parse_date(self, value: Union[str, _dt.date]) -> _dt.date:
        if isinstance(value, _dt.date):
            return value
        try:
            return _dt.datetime.strptime(value, "%Y-%m-%d").date()
        except Exception as exc:
            raise ValueError(f"Invalid date format '{value}'. Expected YYYY‑MM‑DD.") from exc

    def _get_rates_for(self, date: str, base: str) -> Dict[str, float]:
        """Retrieve (and cache) the rates for a specific date and base.

        Parameters
        ----------
        date : str
            ``"latest"`` or a date in ``YYYY‑MM‑DD`` format.
        base : str
            ISO 4217 code of the base currency in lower case.

        Returns
        -------
        dict
            A mapping of target currency codes to rates.

        Raises
        ------
        ExchangeRateAPIError
            If the upstream service cannot be reached or returns an error.
        """
        cache_key = (date, base)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Build endpoint path: currencies/{base}.json
        endpoint = f"currencies/{base}.json"
        # Try each base URL until one succeeds
        last_error: Optional[Exception] = None
        for base_url_template in self._BASE_URLS:
            url = base_url_template.format(date=date, version=self.api_version, endpoint=endpoint)
            try:
                response = requests.get(url, timeout=self.timeout)
            except Exception as exc:
                last_error = exc
                continue
            if response.status_code == 200:
                try:
                    payload = response.json()
                except json.JSONDecodeError as exc:
                    last_error = exc
                    continue
                # The JSON has the form {"date": "2025-08-05", "usd": {...}}
                # Extract the dictionary containing the rates.  The base
                # currency key is the only top level key besides 'date'.
                if base not in payload:
                    last_error = ExchangeRateAPIError(
                        f"Unexpected response structure from {url}: missing base currency '{base}'"
                    )
                    continue
                rates: Dict[str, float] = payload[base]
                # Normalise keys to lower case
                normalized = {k.lower(): float(v) for k, v in rates.items()}
                self._cache[cache_key] = normalized
                return normalized
            else:
                last_error = ExchangeRateAPIError(
                    f"HTTP {response.status_code} while fetching {url}: {response.text[:200]}"
                )
                # do not break; try fallback
        # If we get here, all attempts failed
        raise ExchangeRateAPIError(
            f"Failed to fetch rates for {base} on {date}: {last_error}"
        )
