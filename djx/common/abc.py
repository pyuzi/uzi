import typing as t 
from abc import ABCMeta, abstractmethod

from collections.abc import (
    Collection, Mapping, MutableMapping, Set, MutableSet, Sequence, MutableSequence
)

from .utils import export



@export()
class Fluent(ABCMeta):
    """
    """
    __slots__ = ()

    def __getattr__(self, key):
        return None 



@export()
class FluentMapping(Mapping):
    __slots__ = ()

    @abstractmethod
    def __missing__(self, key):
        return None 


    


def _check_methods(C, *methods):
    mro = C.__mro__
    for method in methods:
        for B in mro:
            if method in B.__dict__:
                if B.__dict__[method] is None:
                    return NotImplemented
                break
        else:
            return NotImplemented
    return True



@export()
class Orderable(metaclass=ABCMeta):
    """SupportsOrdering Object"""
    __slots__ = ()
    
    def __order__(self):
        return self

    def __eq__(self, it, orderby=None) -> bool:
        if isinstance(it, Orderable):
            return it == (orderby or self.__class__.__order__)(self)
        return NotImplemented

    def __ne__(self, it, orderby=None) -> bool:
        return not self.__eq__(it, orderby)

    def __gt__(self, it, orderby=None) -> bool:
        if isinstance(it, Orderable):
            return (orderby or self.__class__.__order__)(self) > it
        return NotImplemented

    def __ge__(self, it, orderby=None) -> bool:
        return it is self or self.__gt__(it, orderby) or self.__eq__(it, orderby)

    def __lt__(self, it, orderby=None) -> bool:
        if isinstance(it, Orderable):
            return (orderby or self.__class__.__order__)(self) < it
        return NotImplemented

    def __le__(self, it, orderby=None) -> bool:
        return it is self or self.__lt__(it, orderby) or self.__eq__(it, orderby)

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        if cls is Orderable:
            return _check_methods(subclass, '__eq__', '__ge__', '__gt__', '__le__', '__lt__')
        return NotImplemented



Orderable.register(str)
Orderable.register(int)
Orderable.register(float)
Orderable.register(bytes)
Orderable.register(tuple)
Orderable.register(Set)
Orderable.register(frozenset)
Orderable.register(set)



@export()
class Immutable(metaclass=ABCMeta):
    """SupportsOrdering Object"""
    __slots__ = ()

    __mutable__: t.ClassVar[t.Union[type[t.Any], tuple[type[t.Any]]]] = ...
    __immutable__: t.ClassVar[t.Union[type[t.Any], tuple[type[t.Any]]]] = ...
    
    def __init_subclass__(cls, *, mutable=..., immutable=...) -> None:
        if mutable is not ...:
            cls.__mutable__ = mutable
        if immutable is not ...:
            cls.__immutable__ = immutable
        

    @classmethod
    def __subclasshook__(cls, sub: type) -> bool:
        if Immutable in cls.__bases__ and cls.__mutable__ and cls.__immutable__:
            return issubclass(sub, cls.__immutable__) and not issubclass(sub, cls.__mutable__)
        return NotImplemented


@export()
class ImmutableSequence(Immutable, immutable=Sequence, mutable=MutableSequence):

    __slots__ = ()


@export()
class ImmutableSet(Immutable, immutable=Set, mutable=MutableSet):

    __slots__ = ()


@export()
class ImmutableMapping(Immutable, immutable=Mapping, mutable=MutableMapping):

    __slots__ = ()

