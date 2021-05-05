from __future__ import annotations
from collections import defaultdict
import datetime
import operator as op

from abc import ABCMeta, abstractmethod
from decimal import Decimal

from types import MethodType
import typing as t
from weakref import WeakValueDictionary, finalize, ref as weakref, WeakMethod, ReferenceType as WeakReferenceType

from . import export

_T = t.TypeVar('_T')

__all__ = [
    'ref',
]



@export()
def safe_ref(obj: _T, callback=None, /, *, coerce: bool=True, strict=False, checkstatic:bool=True) -> ReferenceType[_T]:
    if isinstance(obj, ReferenceType):
        return obj
    elif checkstatic and isinstance(obj, StrongReferent):
        return strong_ref(obj, callback)
    elif isinstance(obj, MethodType):
        return WeakMethod(obj, callback)

    try:
        return weakref(obj, callback)
    except TypeError as e:

        print(f'WEAKREF FAILED:--', e)

        if strict is True: 
            raise
        elif coerce:
            return strong_ref(obj, callback)
        else:
            return obj
        

ref = safe_ref





class StrongReferent(t.Generic[_T], metaclass=ABCMeta):
    
    __slots__ = ()


StrongReferent.register(str)
StrongReferent.register(int)
StrongReferent.register(float)
StrongReferent.register(list)
StrongReferent.register(tuple)
StrongReferent.register(dict)
StrongReferent.register(set)
StrongReferent.register(frozenset)
StrongReferent.register(Decimal)
StrongReferent.register(datetime.date)
StrongReferent.register(datetime.datetime)
StrongReferent.register(datetime.time)
StrongReferent.register(datetime.timedelta)
StrongReferent.register(datetime.timezone)





class ReferenceType(t.Generic[_T], metaclass=ABCMeta):
    __slots__ = ()
    
    @abstractmethod
    def __hash__(self) -> int:
        ...
    
    @abstractmethod
    def __eq__(self, o) -> bool:
        ...

    @abstractmethod
    def __call__(self):
        ...


ReferenceType.register(WeakReferenceType)





@ReferenceType.register
class strong_ref:
    
    __slots__ = '__value', '__hash', '__callback__', '__weakref__'

    __value: _T
    __hash: int
    __callback__: t.Callable[..., t.Any]

    __refs: t.ClassVar[WeakValueDictionary[int, strong_ref]] = WeakValueDictionary()

    def __new__(cls, val, callback=None, /) -> ReferenceType[_T]: 
        if val.__class__ is cls:
            if callback is val.__callback__ or callback is None:
                return val
            val = val()
        elif isinstance(val, ReferenceType):
            raise TypeError(f'ReferenceType: {val.__class__} cannot be referenced')
        elif callback is not None:
            ref = super().__new__(cls)
            finalize(ref, callback, weakref(ref))
            return ref

        refs = strong_ref.__refs
        ref = refs.get((idv := id(val)))

        if ref is not None:
            if ref() is val:
                return ref
            del refs[idv]

        return refs.setdefault(idv, super().__new__(cls))
        
    def __init__(self, val, callback=None, /): 
        self.__value = val
        self.__callback__ = callback
    
    def __hash__(self) -> int:
        if not hasattr(self, '__hash'):
            self.__hash = hash((strong_ref, hash(self.__value)))
        return self.__hash
    
    def __eq__(self, o) -> bool:
        if isinstance(o, ReferenceType):
            return o() == self.__value
        return NotImplemented

    def __call__(self):
        return self.__value



