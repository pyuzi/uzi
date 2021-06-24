import sys
from functools import partial
from abc import ABCMeta, abstractmethod
from types import FunctionType, MethodType
from weakref import WeakMethod, finalize, ref
from typing import (
    Any, Callable, ClassVar, Dict, Generic, Hashable, Literal, NamedTuple, Optional, TYPE_CHECKING, Type, TypeVar, Union, 
)
from enum import IntEnum, auto, unique 


from djx.common.utils import export

from djx.common.abc import Orderable

from .abc import StaticIndentity, Injectable, SupportsIndentity


__all__ = [

]


_S = TypeVar('_S', bound=StaticIndentity)
        




def identity(obj):

    if isinstance(obj, StaticIndentity):
        return obj
    
    if isinstance(obj, MethodType):
        obj = obj.__func__

    return HashIdentity(id(obj), type(obj)) 





@unique
class KindOfSymbol(IntEnum):
    TYPE = 1
    OBJECT = auto()
    LITERAL = auto()
    METHOD = auto()
    FUNCTION = auto()



@export()
class UnsupportedTypeError(TypeError):
    pass





__last_id: int = 0
def _ordered_id():
    global __last_id
    __last_id += 1
    return __last_id


@export()
@Injectable.register
@StaticIndentity.register
class symbol(Orderable, Generic[_S]):
    """A constant symbol representing given object. 
        
    They are singletons. So, repeated calls of symbol(object) will all
    return the same instance.

    Example:

        # str symbols
        assert symbol('foo') is symbol('foo')

        # class symbols
        class Foo: 
            ...
        assert symbol(Foo) is symbol(Foo)

        # function symbols
        def foo(): 
            ...
        assert symbol(foo) is symbol(foo)
    """

    __slots__ = ('__ref', '__ident', '__kind', '_name', '__pos', '__weakref__')
    

    Kinds: ClassVar[type[KindOfSymbol]] = KindOfSymbol

    __instances: ClassVar[Dict['symbol', 'symbol[_S]']] = dict()

    _name: str
    __pos: int
    __kind: Kinds
    __ref: Callable[..., _S]
    __ident: StaticIndentity

    @classmethod
    def __pop(cls, ash, wr = None) -> None:
        return cls.__instances.pop(ash, None)

    def __new__(cls, obj: _S, name = None):
        if type(obj) is symbol:
            return obj
       
        ident = identity(obj) 

        try:
            rv = symbol.__instances[ident]
        except KeyError:
            
            if isinstance(obj, ref):
                return symbol(obj(), name)
            elif not isinstance(obj, SupportsIndentity):
                raise UnsupportedTypeError(f'Cannot create Symbol for: {type(obj)}')

            rv = symbol.__instances.setdefault(ident, (s := object.__new__(cls)))
            if rv is s:
                rv.__ident = ident
                
                rv.__pos = _ordered_id()

                rv._name = name
                if isinstance(obj, StaticIndentity):
                    rv.__kind = KindOfSymbol.LITERAL
                else:                
                    if isinstance(obj, type):
                        rv.__kind = KindOfSymbol.TYPE
                    elif isinstance(obj, (FunctionType, MethodType)):
                        rv.__kind, obj = _real_func_and_kind(obj)
                    else:
                        rv.__kind = KindOfSymbol.OBJECT
                    rv.__ref = ref(obj, partial(symbol.__pop, ident))
                
        return rv

    @property
    def __name__(self):
        return self._name\
            or getattr(self(), '__qualname__', None)\
            or str(self.__ident) 

    @property
    def ident(self):
        return self.__ident

    @property
    def ref(self):
        return self.__ref

    @property
    def kind(self):
        return self.__kind

    def __eq__(self, x) -> bool:
        if x is self:
            return True
        elif isinstance(x, symbol):
            return self() == x()
        elif isinstance(x, SupportsIndentity):
            return self() == x
        
        return NotImplemented
    
    def __hash__(self):
        return hash(self.__ident)
     
    def __bool__(self):
        return self() is not None
    
    def __reduce__(self):
        return type(self), (self(strict=True), self._name)

    def __str__(self):
        return f'symbol("{self.__name__}")'

    def __repr__(self):
        return f'symbol({self.__name__!r}, ref={self()!r})'

    def __call__(self, *, strict=False) -> _S:
        rv = self.__ident if self.__kind is KindOfSymbol.LITERAL else self.__ref()
        if rv is None:
            symbol.__pop(self.__ident)
            if strict:
                raise RuntimeError(f'Symbol ref is no longer available')
        return rv
        
    def __order__(self):
        return self.__pos, self()
   


class HashIdentity(NamedTuple):

    hash: int
    type: type
    hmark: Any = symbol

    def __reduce__(self):
        raise ValueError(f'ReferredIdentity cannot be pickled.')





def _isunboundmethod(obj: FunctionType) -> bool:
    from .inspect import signature
    if next(iter(signature(obj).parameters), None) == 'self':
        _mod = sys.modules[obj.__module__]
        p, _, n = obj.__qualname__.rpartition('.')
        if p and isinstance(t := getattr(_mod, p), type):
            return getattr(t, obj.__name__) is obj
    return False



def _real_func_and_kind(obj: Union[MethodType, FunctionType]):
    if isinstance(obj, MethodType):
        return KindOfSymbol.METHOD, obj.__func__
    elif _isunboundmethod(obj):
        return KindOfSymbol.METHOD, obj
    else:
        return KindOfSymbol.FUNCTION, obj












