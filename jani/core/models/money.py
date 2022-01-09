import typing as t
import logging

from djmoney.models import fields as base

from django.db import models
from django.db.models import NOT_PROVIDED, F, Field, Func, Value
from django.db.models.expressions import BaseExpression

from jani.common.money import Money, MoneyAbc, to_money, local_currency

from jani.common.utils import class_property


logger = logging.getLogger(__name__)



DECIMAL_PLACES = 4

MAX_DIGITS = 19


def _get_value(obj, expr):
    """
    Extracts value from object or expression.
    """
    logger.info(f'Patched get_value called')
    if isinstance(expr, F):
        expr = getattr(obj, expr.name)
    else:
        expr = expr.value
    if isinstance(expr, MoneyAbc):
        expr = Money(expr.amount, expr.currency)
    return expr

#Monkey patch base
base.get_value = _get_value


class MoneyFieldProxy(base.MoneyFieldProxy):
    
    def __set__(self, obj, value):  # noqa
        if not(value is None or isinstance(value, BaseException)):
            try:
                v = self._to_money(value)
            except (ValueError, TypeError):
                pass
            else:
                value = v
        
        return super().__set__(obj, value)

    def _money_from_obj(self, obj):
        val = obj.__dict__[self.field.name], obj.__dict__[self.currency_field_name]
        if val[0] is None:
            return None
        return self._to_money(val)

    def _to_money(self, val):
        return to_money(val)




class MoneyField(base.MoneyField):

    _default_currency_ = class_property(lambda cls: local_currency)
    
    _money_descriptor_class_ = MoneyFieldProxy
    _decimal_places_ = DECIMAL_PLACES
    _max_digits_ = MAX_DIGITS

    def __init__(self, *args, 
                max_digits=None, 
                decimal_places=None, 
                default_currency=...,  
                money_descriptor_class=None, 
                **kwds):
        
        kwds['max_digits'] = max_digits or self._max_digits_
        kwds['decimal_places'] = (
            self._decimal_places_ if decimal_places is None else decimal_places
        )
        
        kwds['default_currency'] = (
            self._default_currency_ if default_currency is ... else default_currency
        )
        kwds['money_descriptor_class'] = money_descriptor_class \
            or self._money_descriptor_class_

        super().__init__(*args, **kwds)
    
    def setup_default(self, default, default_currency, nullable):
        if default is None or default is NOT_PROVIDED:
            return default
        else:
            return to_money(default)
    
    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()

        if self.default_currency is self._default_currency_:
            kwargs.pop('default_currency')
            
        return name, path, args, kwargs

