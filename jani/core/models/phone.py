import logging
import typing as t 
from django.db import models 


from jani.common.functools import export
from jani.common.phone import PhoneNumber, PhoneFormat, PhoneStr, parse_phone, to_phone
from jani.common.locale import locale, Locale




@export()
class PhoneNumberField(models.CharField):

    description = "A phone number"
    default_phone_cls = None
    default_format = PhoneFormat.default

    def __init__(self, *args, 
            format: PhoneFormat = None, 
            region: str=..., 
            locale: Locale = None, 
            max_length=64, 
            phone_class=None, 
            **kwargs):
        super().__init__(*args, max_length=max_length, **kwargs)
        self._region = region
        self.locale = locale 
        self.phone_class = phone_class or self.default_phone_cls 
        self.format = PhoneFormat(format or self.default_format)

    @property
    def region(self):
        if self._region is ... and self.locale:
            return self.local.territory
        return self._region

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()

        if kwargs.get('max_length') == 64:
            del kwargs['max_length']
        if self._region is not ...:
            kwargs['region'] = self._region
        if self.locale is not None:
            kwargs['locale'] = self.locale
        if self.format != self.default_format:
            kwargs['format'] = self.format
        if self.phone_class is not self.default_phone_cls:
            kwargs['phone_class'] = self.phone_class

        return name, path, args, kwargs

    def to_python(self, value, *, strict=False):
        if value is None:
            return value
        return to_phone(value, region=self.region, _phone_class=self.phone_class)

    def from_db_value(self, value: str, expression, connection, context=None):
        if not value:
            return value

        if self.format is PhoneFormat.MSISDN:
            value = f'+{value}'

        return parse_phone(value, None, check_region=False, phone_class=self.phone_class)

    def get_prep_value(self, value: PhoneNumber):
        value = self.to_python(value)
        return value if not value else value.to(self.format) # if value.ispossible() else value 

