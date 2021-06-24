from decimal import Decimal
import typing as t





from moneyed import Currency, CURRENCIES, CURRENCIES_BY_ISO, get_currency

from .money import Money, MoneyAbc
from .monies import Monies
from .settings import DEFAULT_CURRENCY, ALLOWED_CURRENCIES

__all__ = [
    'Money',
    'Monies',
    'MoneyLike',
    'Currency',
    'get_currency',
]


MoneyLike = t.Union[MoneyAbc, Decimal, int, float]


if t.TYPE_CHECKING:
    money = None
    monies = None


def __patch_currency():

    def __json__(self: Currency):
        return self.code

    def __get_validators__(cls):
        def _validate_currency(v):
            if isinstance(v, Currency):
                return v
            
            v = str(v)
            try:
                return CURRENCIES[v]
            except KeyError:
                if v in CURRENCIES_BY_ISO:
                    return CURRENCIES_BY_ISO[v]
                raise ValueError(f'must be a valid currency with code.')

        yield _validate_currency


    Currency.__json__ = __json__
    Currency.__get_validators__ = classmethod(__get_validators__)

__patch_currency()
del __patch_currency

