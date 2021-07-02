import logging
import typing as t 
from django.db import models 


from djx.common.utils import export
from djx.common.phone import PhoneNumber, PhoneFormat, PhoneStr, parse_phone, to_phone
from djx.common.locale import locale, Locale




@export()
class PhoneNumberField(models.CharField):

    description = "A phone number"
    default_phone_cls = PhoneNumber
    default_phone_format = PhoneFormat.PLAIN

    def __init__(self, *args, 
            phone_format: PhoneFormat = None, 
            region: str=..., 
            locale: Locale = None, 
            max_length=64, 
            phone_class=None, 
            **kwargs):
        super().__init__(*args, max_length=max_length, **kwargs)
        self._region = region
        self.locale = locale 
        self.phone_class = phone_class or self.default_phone_cls 
        self.phone_format = PhoneFormat(phone_format or self.default_phone_format)

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
        if self.phone_format != self.default_phone_format:
            kwargs['phone_format'] = self.phone_format
        if self.phone_class is not self.default_phone_cls:
            kwargs['phone_class'] = self.phone_class

        return name, path, args, kwargs

    def to_python(self, value, *, strict=False):
        return value and to_phone(value, region=self.region,  _phone_class=self.phone_class)
        # if value is None:
        #     return value
        # elif isinstance(value, PhoneNumber):
        #     if not strict or value.__class__ is self.phone_class:
        #         return value
        #     return self.phone_class(value)
        # elif isinstance(value, PhoneStr):
        #     return self.to_python(value.phone) if strict else value.phone
        # else:
        #     return value and parse_phone(value, self.region, phone_class=self.phone_class)

    def from_db_value(self, value, expression, connection, context=None):
        return value and parse_phone(value, None, check_region=False, phone_class=self.phone_class)

    def get_prep_value(self, value: PhoneNumber):
        value = self.to_python(value)
        return value if not value else value.to(self.phone_format) # if value.ispossible() else value 


