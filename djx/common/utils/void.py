from __future__ import annotations
import re
from typing import ClassVar


__all__ = [
    'Void',
]


class VoidType(type):

    __type: ClassVar[VoidType] = None

    def __new__(mcls, name, bases, dct):
        if VoidType.__type is None:
            VoidType.__type = super().__new__(mcls, name, bases, dct)
            return VoidType.__type

        raise TypeError(f'{mcls.__name__} already defined')
        
    def __call__(self, *args, **kwds):
        raise TypeError(f'{type(self).__name__} is not callable7')

    def __bool__(self):
        return False

    def __str__(self):
        return self.__name__

    def __repr__(self):
        return f'{self}'

    def __json__(self):
        return None

    def validate(cls, v, **kwargs):
        if v in {Void, None}:
            return Void
        ValueError('must be void')

    def __get_validators__(cls):
        yield cls.validate

    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        field_schema.update(type='null')



Void = VoidType('Void', (), {})