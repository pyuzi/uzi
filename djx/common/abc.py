
from abc import ABCMeta, abstractmethod

from collections.abc import Set, Mapping

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

