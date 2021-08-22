from abc import ABCMeta
from decimal import Decimal
import re
import typing as t
from collections.abc import Mapping
from moneyed import Money as _Money, Currency, get_currency


from djx.di import di
from djx.common.utils import text, class_property
from djx.common.locale import get_locale_currency
from djx.common.collections import PriorityStack



try:
    from djmoney.money import Money as _Base
except ImportError:
    _Base = _Money



_match_re = re.compile(r'^(?:(-)|\+)?([a-z]{3})?(\d+(?:\.\d+)?)$', re.IGNORECASE)
_sub_re = re.compile(r'[\s,]+')


def to_money(val, *, cls=None) -> 'Money':
    cls = cls or Money
    if isinstance(val, cls):
        return val
    elif isinstance(val, str):
        parts = _match_re.match(_sub_re.sub('', val))
        if parts is not None:
            return cls(f'{parts[1] or ""}{parts[3]}', parts[2])
        return cls(val)
    elif isinstance(val, Mapping):
        return cls(**val)
    elif isinstance(val, (tuple, list)):
        return cls(*val)
    else:
        return cls(val)


class MoneyAbc(metaclass=ABCMeta):

    __slots__ = ()

    amount: Decimal
    currency: Currency



MoneyAbc.register(_Money)



class Money(_Base):

    __currency__: t.ClassVar[Currency] = None
    __currencies__: t.ClassVar[Currency] = None
    __type_stack = PriorityStack()
    
    amount: Decimal
    currency: Currency

    @class_property
    def _default_currency(cls):
        return get_locale_currency()

    def __class_getitem__(cls, params: t.Union[str, Currency, tuple[t.Union[str, Currency]]]) -> type['Money']:
        if isinstance(params, tuple):
            assert len(params) == 1
            params = params[0]
    
        assert cls.__currency__ is None

        __currency__ = get_currency(str(params))

        __name__ = text.uppercamel(f'{__currency__}Money')

        klass = Money.__type_stack.get(__currency__)
        if klass is  None:
            klass = Money.__type_stack.setdefault(
                __currency__, type(__name__, (cls,), dict(
                    __currency__=__currency__, 
                    __module__=cls.__module__
                )
            ))
            print('+++ '*3, __currency__, '-->', __name__, '-->', klass, '+++ '*3)

        return klass

    def __init__(self, amount=0, currency=None):
        if isinstance(amount, MoneyAbc):
            currency = currency or amount.currency
            amount = amount.amount
        elif currency is None:
            currency = self.__currency__ or self._default_currency

        super().__init__(amount, currency)

        if not(self.__currency__ is None or self.currency == self.__currency__):
            raise ValueError(f'invalid currency. expected {self.__currency__}')
    


    def __add__(self, other):
        if other == 0:
            # This allows things like 'sum' to work on list of Money instances,
            # just like list of Decimal.
            return self
        elif not isinstance(other, MoneyAbc):
            return self.__class__(self.amount + other, self.currency)
        # elif self.currency == other.currency:
        #     return self.__class__(self.amount + other.amount, self.currency)
        return super().__add__(other)

        # raise TypeError('Cannot add or subtract two Money ' +
                        # 'instances with different currencies.')
    
    def __sub__(self, other):
        if other == 0:
            # This allows things like 'sum' to work on list of Money instances,
            # just like list of Decimal.
            return self
        elif not isinstance(other, MoneyAbc):
            return self.__class__(self.amount - other, self.currency)
        # elif self.currency == other.currency:
        #     return self.__class__(self.amount + other.amount, self.currency)
        return super().__sub__(other)

    # _______________________________________
    # Override comparison operators
    def __eq__(self, other):
        if not isinstance(other, MoneyAbc):
            return self.amount == other  
        return super().__eq__(other)
        # return self.amount == other.amount and self.currency == other.currency

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

    def __json__(self):
        return dict(amount=self.amount, currency=self.currency.code) 

    @classmethod
    def cast(cls, v):
        return to_money(v, cls=cls)

    @classmethod
    def __get_validators__(cls):
        yield cls.cast

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        field_schema.update(type='string', format=f'numeric', example=f'{cls._default_currency}500.00')



_Money.__json__ = Money.__json__
_Money.__get_validators__ = Money.__get_validators__
_Money.__modify_schema__ = Money.__modify_schema__

