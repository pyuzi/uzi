from abc import ABCMeta
from decimal import Decimal
import re
import typing as t
from moneyed import Money as _Money, Currency

from . import settings


try:
    from djmoney.money import Money as _Base
except ImportError:
    _Base = _Money


_match_re = re.compile(r'^(?:(-)|\+)?([a-z]{3})?(\d+(?:\.\d+)?)$', re.IGNORECASE)
_sub_re = re.compile(r'[\s,]+')

class MoneyAbc(metaclass=ABCMeta):

    __slots__ = ()

    amount: Decimal
    currency: Currency

    @classmethod
    def cast(cls, v):
        if isinstance(v, cls):
            return v
        elif isinstance(v, str):
            parts = _match_re.match(_sub_re.sub('', v))
            if parts is not None:
                return cls(f'{parts[1] or ""}{parts[3]}', parts[2])
        elif isinstance(v, dict):
            return cls(**v)
        
        return cls(v)

    # def __json__(self):
    #     return f'{self.currency.code}{self.amount}'

    def __json__(self):
        # return f'{self.currency.code}{self.amount}'
        return dict(amount=self.amount, currency=self.currency.code) 

    @classmethod
    def __get_validators__(cls):
        yield cls.cast

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        field_schema.update(type='string', format=f'numeric', example=f'{cls._default_currency}500.00')



MoneyAbc.register(_Money)


class Money(_Base, MoneyAbc):

    _default_currency: t.ClassVar[str] = settings.DEFAULT_CURRENCY

    def __init__(self, amount=0, currency=None):
        if isinstance(amount, MoneyAbc):
            currency = currency or amount.currency
            amount = amount.amount
        elif currency is None:
            currency = self._default_currency
        super().__init__(amount, currency)
        
        
    def __add__(self, other):
        if other == 0:
            # This allows things like 'sum' to work on list of Money instances,
            # just like list of Decimal.
            return self
        elif not isinstance(other, MoneyAbc):
            return self.__class__(self.amount + other, self.currency)
        elif self.currency == other.currency:
            return self.__class__(self.amount + other.amount, self.currency)

        raise TypeError('Cannot add or subtract two Money ' +
                        'instances with different currencies.')

    # _______________________________________
    # Override comparison operators
    def __eq__(self, other):
        if not isinstance(other, MoneyAbc):
            return self.amount == other  
        
        return self.amount == other.amount and self.currency == other.currency

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if not isinstance(other, MoneyAbc):
            return self.amount < other  
        if (self.currency == other.currency):
            return (self.amount < other.amount)
        else:
            raise TypeError('Cannot compare Money with different currencies.')

    def __gt__(self, other):
        if not isinstance(other, MoneyAbc):
            return self.amount > other  
        if (self.currency == other.currency):
            return (self.amount > other.amount)
        else:
            raise TypeError('Cannot compare Money with different currencies.')


_Money.__json__ = Money.__json__
_Money.__get_validators__ = Money.__get_validators__
_Money.__modify_schema__ = Money.__modify_schema__

