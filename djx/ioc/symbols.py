import sys
from functools import partial
from abc import ABCMeta, abstractmethod
from types import FunctionType, MethodType
from weakref import WeakMethod, finalize, ref
from typing import (
    Any, Callable, ClassVar, Dict, Generic, Hashable, Literal, NamedTuple, Optional, TYPE_CHECKING, Type, TypeVar, Union, 
)

from flex.datastructures.enum import IntEnum, auto, unique 
from flex.utils.decorators import export

__all__ = [

]


_S = TypeVar('_S', str, FunctionType, Type, Hashable)
        




def identity(obj):

    if isinstance(obj, StaticIndentity):
        return obj
    
    if isinstance(obj, MethodType):
        obj = obj.__func__

    return ReferredIdentity(type(obj), id(obj)) 





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



@export()
class SupportsIndentity(metaclass=ABCMeta):

    __slots__ = ()


SupportsIndentity.register(type)
SupportsIndentity.register(MethodType)
SupportsIndentity.register(FunctionType)



@export()
class StaticIndentity(SupportsIndentity):

    __slots__ = ()

    @abstractmethod
    def __hash__(self):
        return 0


StaticIndentity.register(str)
StaticIndentity.register(bytes)
StaticIndentity.register(int)
StaticIndentity.register(float)
StaticIndentity.register(tuple)
StaticIndentity.register(frozenset)




@export()
@StaticIndentity.register
class symbol(Generic[_S]):
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

    __slots__ = ('_ref', '_ident', '_kind', '_name', '__weakref__')
    

    Kind: ClassVar[type[KindOfSymbol]] = KindOfSymbol

    __instances: ClassVar[Dict['symbol', 'symbol[_S]']] = dict()

    _name: str
    
    _kind: Kind

    _ref: Callable[..., _S]

    _ident: StaticIndentity

    @classmethod
    def __pop(cls, ash, wr = None) -> None:
        return cls.__instances.pop(ash, None)

    def __new__(cls, obj: _S, name = None, /, _kind=None) -> 'symbol[_S]':
        if isinstance(obj, symbol):
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
                rv._ident = ident
                rv._name = name
                if isinstance(obj, StaticIndentity):
                    rv._kind = KindOfSymbol.LITERAL
                else:                
                    if isinstance(obj, type):
                        rv._kind = KindOfSymbol.TYPE
                    elif isinstance(obj, (FunctionType, MethodType)):
                        rv._kind, obj = _real_func_and_kind(obj)
                    else:
                        rv._kind = KindOfSymbol.OBJECT
                    rv._ref = ref(obj, partial(symbol.__pop, ident))

        return rv

    @property
    def __name__(self):
        return self._name\
            or getattr(self(), '__qualname__', None)\
            or str(self._ident) 

    @property
    def kind(self):
        return self._kind

    def __eq__(self, x) -> bool:
        if isinstance(x, StaticIndentity):
            return x == self._ident
        return NotImplemented
    
    def __hash__(self):
        return hash(self._ident)
     
    def __bool__(self):
        return self() is not None
    
    # def __reduce__(self):
    #     return self.__class__, (self(strict=True), self._name, self._kind)

    def __str__(self):
        return f'symbol("{self.__name__}")'

    def __repr__(self):
        return f'symbol({self.__name__!r}, ref={self()!r})'

    def __call__(self, *, strict=False) -> _S:
        rv = self._ident if self._kind is KindOfSymbol.LITERAL else self._ref()
        if rv is None:
            symbol.__pop(self._ident)
            if strict:
                raise RuntimeError(f'Symbol ref is no longer available')
        return rv




class ReferredIdentity(NamedTuple):

    type: type
    id: int
    nspace: Any = symbol

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












