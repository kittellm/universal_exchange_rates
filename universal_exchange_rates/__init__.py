"""Top level package for the universal exchange rates client.

Importing from this module will expose the :class:`ExchangeRateAPI` class
directly for convenience:

>>> from universal_exchange_rates import ExchangeRateAPI
>>> api = ExchangeRateAPI(base_currency="cad")
>>> rates = api.get_rates(symbols=["usd", "eur"])

The module is implemented in :mod:`.api`.
"""

from .api import ExchangeRateAPI, ExchangeRateAPIError  # noqa: F401

__all__ = ["ExchangeRateAPI", "ExchangeRateAPIError"]