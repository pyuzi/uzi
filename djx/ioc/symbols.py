
from functools import partialmethod
from types import FunctionType, MethodType
from weakref import finalize, ref
from typing import (
    Any, Callable, ClassVar, Dict, Generic, Hashable, Optional, TYPE_CHECKING, Type, TypeVar, Union, 
)
from attr import s

from flex.utils.decorators import export

__all__ = [
    'symbol'
]


_S = TypeVar('_S', str, FunctionType, Type, Hashable)


# class SymbolRef(ref, Generic[_S]):

    # __slots__ = () # 'ash',

    # def __init__(self, o: _S, callback: Optional[Callable[['SymbolRef[_S]'], Any]]=None, /, ash: tuple = None) -> None:
    #     super().__init__(o, callback)
    #     self.ash = ash

    # if TYPE_CHECKING:
    #     def __call__(self) -> _S: ...

        



class _HashTuple(tuple):
    """A tuple that ensures that hash() will be called no more than once
    per element, since cache decorators will hash the key multiple
    times on a cache miss.  See also _HashedSeq in the standard
    library functools implementation.

    """
    __ash: int = None

    def __hash__(self, hash=tuple.__hash__):
        if self.__ash is None:
            self.__ash = hash(self)
        return self.__ash

    def __add__(self, other, add=tuple.__add__):
        return self.__class__(add(self, other))

    def __radd__(self, other, add=tuple.__add__):
        return self.__class__(add(other, self))



@export()
class Symbol(Generic[_S]):
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
    __slots__ = ('_ref', '_ash', '_name', '__weakref__')

    __instances: ClassVar[Dict['Symbol', 'Symbol[_S]']] = dict()

    _name: str

    _ref: Callable[..., _S]

    _ash: Union[_HashTuple, str]

    @classmethod
    def __pop(cls, wr: ref) -> None:
        return cls.__instances.pop(wr(), None)

    def __new__(cls, obj: _S, name = None, /) -> 'Symbol[_S]':

        ash = obj if isinstance(obj, (Symbol, str)) else _HashTuple((Symbol, type(obj), hash(obj)))

        try:
            rv = Symbol.__instances[ash]
        except KeyError as e:
            if isinstance(obj, MethodType):
                return Symbol(obj.__func__, name)
            elif isinstance(obj, (ref, Symbol)):
                return Symbol(obj(), name)
            elif obj is None:
                raise ValueError(f'NoneTypes cannot have a Symbol') from e

            if isinstance(obj, str):
                rv = Symbol.__instances.setdefault(ash, (s := object.__new__(_StrSymbol)))
                if rv is s:
                    rv._ash = ash
                    rv._name = name or obj
            else:
                rv = Symbol.__instances.setdefault(ash, (s := object.__new__(Symbol)))
                if rv is s:
                    rv._ref = ref(obj, partialmethod(Symbol.__pop, ash))
                    rv._ash = ash
                    rv._name = name or getattr(obj, '__name__', str(obj))
                
        return rv

    @property
    def __name__(self):
        return self._name

    def __eq__(self, x) -> bool:
        if isinstance(x, Symbol):
            return self._ash == x._ash
        elif isinstance(x, type(self._ash)):
            return x == self._ash

        return NotImplemented
    
    def __hash__(self):
        return hash(self._ash)
     
    def __bool__(self):
        return self() is not None
    
    def __reduce__(self):
        if self._name:
            return type(self), (self(strict=True), self._name)
        else:
            return type(self), (self(strict=True),)

    def __str__(self):
        return f'Symbol("{self._name}")'

    def __repr__(self):
        return f'<{self}, {self()!r}>'

    def __call__(self, *, strict=False) -> _S:
        if (rv := self._ref()) is None:
            Symbol.__pop(self._ash)
            if strict:
                raise RuntimeError(f'Symbol ref is no longer available')
        return rv




class _StrSymbol(Symbol[str]):

    __slots__ = ()
    
    def __call__(self, *, strict=False) -> str:
        return self._ash



symbol = Symbol