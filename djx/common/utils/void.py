from __future__ import annotations
import re
from typing import ClassVar


__all__ = [
    'Void',
]


class VoidType:

    __slots__ = '__name__',

    __value__: ClassVar[VoidType] = None

    @classmethod
    def __init_subclass__(cls) -> None:
        cls.__value__ = None

    # def __new__(mcls, name, bases, dct):
    #     if mcls.__value__ is None:
    #         mcls.__value__ = super().__new__(mcls, name, bases, dct)
    #         return mcls.__value__

    #     raise TypeError(f'{mcls.__name__} already defined {mcls.__value__}')
        
    def __new__(cls):
        # if cls.__value__ is None:
            # cls.__value__ = super().__new__(cls)
            # cls.__value__.__name__ = name
        return cls.__value__

    # def __call__(self, *args, **kwds):
    #     raise TypeError(f'{type(self).__name__} is not callable7')
    
    @classmethod
    def _makenew__(cls, name):
        if cls.__value__ is None:
            cls.__value__ = object.__new__(cls)
            cls.__value__.__name__ = name

        return cls.__value__

    def __bool__(self):
        return False

    def __str__(self):
        return ''

    def __repr__(self):
        return f'{self.__name__}'

    def __json__(self):
        return None
    
    def __reduce__(self):
        return self.__class__, ()
    
    def __eq__(self, x):
        return x is self

    def __hash__(self):
        return hash((self.__class__, id(self)))

    def validate(cls, v, **kwargs):
        val = cls.__value__
        if v is val or v is None:
            return val

        ValueError(f'must be {val!r}')


    def __get_validators__(cls):
        yield cls.validate

    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        field_schema.update(type='null')





class MissingType(VoidType):
    ...



Void = VoidType._makenew__('Void')
Missing = MissingType._makenew__('Missing')


