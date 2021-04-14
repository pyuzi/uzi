
from collections.abc import Sequence

from djx.ioc.interfaces import InjectorProto
from weakref import WeakSet

from types import FunctionType, MethodType
from typing import Any, Callable, ClassVar, Generic, Optional, Type, TypeVar, Union, overload


from flex.utils.decorators import export


from .exc import ProviderNotFoundError
from .symbols import KindOfSymbol, symbol, SupportsIndentity
from .inspect import _empty

__all__ = [

]


ProvidedType = TypeVar('ProvidedType')

FuncProviderType = TypeVar("FuncProviderType", bound=Callable[..., Any])

InjectableType = Union[symbol, Type, FunctionType, MethodType]


_I = TypeVar('_I', bound=InjectableType)
_T = TypeVar('_T')





__provided = WeakSet()

def is_provided(obj) -> bool:
    return isinstance(obj, SupportsIndentity) and symbol(obj) in __provided




@export()
class Provider(Generic[_I, _T]):

    __slots__ = ('abstract', 'contexts', 'is_cached', 'concrete', 'priority', 'options',)

    abstract: symbol[_I]

    contexts: Optional[Sequence[str]]
    priority: int
    concrete: Any
    is_cached: bool
    options: dict

    def __init__(self, abstract: _I, concrete: Any, priority: Optional[int]=1, contexts: Optional[Sequence[str]]=None, **options) -> None:
        self.abstract = symbol(abstract)
        self.contexts = list(contexts or ())
        self.is_cached = bool(self.contexts)
        self.priority = priority or 0
        self.options = options
        self.set_concrete(concrete)
        __provided.add(self.abstract)

    def set_concrete(self, concrete) -> None:
        self.concrete = concrete
    
    def provide(self, inj: InjectorProto, *args, **kwds) -> _T:
        raise NotImplementedError(f'{self.__class__.__name__}.resolve()')

    def get_cached(self, inj) -> Optional[_T]:

        return _empty
    
    def set_cached(self, inj, val: _T) -> _T:
        return val
    
    def __ge__(self, x) -> bool:
        if isinstance(x, Provider):
            return self.priority >= x.priority
        return NotImplemented

    def __gt__(self, x) -> bool:
        if isinstance(x, Provider):
            return self.priority > x.priority
        return NotImplemented

    def __le__(self, x) -> bool:
        if isinstance(x, Provider):
            return self.priority <= x.priority
        return NotImplemented

    def __lt__(self, x) -> bool:
        if isinstance(x, Provider):
            return self.priority < x.priority
        return NotImplemented

    def __eq__(self, x) -> bool:
        return x == self.abstract

    def __hash__(self, x) -> bool:
        return hash(self.abstract)





@export()
class ValueProvider(Provider):

    __slots__ = ()
    concrete: _T

    def provide(self, inj: InjectorProto, *args, **kwds) -> _T:
        return self.concrete



@export()
class AliasProvider(Provider):

    __slots__ = ()
    concrete: symbol[_T]

    def set_concrete(self, concrete) -> None:
        self.concrete = symbol(concrete)
    
    def provide(self, inj: InjectorProto, *args, **kwds) -> _T:
        return inj[self.concrete]




@export()
class FactoryProvider(Provider):

    __slots__ = ('_sig')
    concrete: symbol[Callable[..., _T]]

    @property
    def factory(self):
        return self.concrete()

    @property
    def signature(self):
        if rv := getattr(self, '_sig', None):
            return rv
        
        from .inspect import signature

        self._sig = signature(self.factory)
        return self._sig

    def set_concrete(self, concrete) -> None:
        concrete = symbol(concrete)
        if not callable(concrete()):
            raise ValueError(
                f'Invalid concrete in {self.__class__.__name__}. '
                f'Expected Callable but got {type(concrete())}.'
            )
        
        self.concrete = concrete
    
    def get_params(self, inj: InjectorProto, *args, __self__=None, **kwds) -> None:
        if __self__ is not None:
            return self.signature.bind_partial(__self__, *args, **kwds)
        return self.signature.bind_partial(*args, **kwds)

    def provide(self, inj: InjectorProto, *args, **kwds):
        rv = self.get_cached(inj)
        if rv is _empty:
            params = self.get_params(inj, *args, **kwds)
            params.apply_dependencies(inj)
            rv = self.set_cached(self.factory(*params.args, **params.kwargs))
        return rv



@export()
class TypeProvider(FactoryProvider):
    __slots__ = ()

    concrete: symbol[type[_T]]



@export()
class MethodProvider(FactoryProvider):
    __slots__ = ()



@export()
class FunctionProvider(FactoryProvider):
    __slots__ = ()




_P = TypeVar('_P', bound=Provider)


# _P = Provider[_I, _T]

class Container(dict[symbol[_I], list[_P]]):
    
    __slots__= ()

    _alias_provider_cls: ClassVar[type[AliasProvider]] = AliasProvider
    _value_provider_cls: ClassVar[type[_P]] = ValueProvider
    

    _factory_provider_cls: ClassVar[type[_P]] = FactoryProvider

    _type_provider_cls: ClassVar[type[_P]] = TypeProvider
    _func_provider_cls: ClassVar[type[_P]] = FunctionProvider
    _method_provider_cls: ClassVar[type[_P]] = MethodProvider

    def get(self, k: _I, *, default: Optional[_P]=None, recursive: bool=True) -> _P:
        try:
            rv = self[symbol(k)][-1]
        except KeyError:
            return default
        else:
            if recursive and isinstance(rv, AliasProvider):
                return self.get(rv.concrete, default=default)
            return rv

    def alias(self, 
            abstract: _I, 
            concrete: _I, 
            priority: int = 1, 
            contexts: Optional[Sequence[str]] = None, 
            **opts) -> AliasProvider:
        return self.push(self.make_alias(abstract, concrete, priority, contexts, **opts))
            
    def factory(self, 
            abstract: _I, 
            concrete: Callable[..., _T], 
            priority: int = 1, 
            contexts: Optional[Sequence[str]] = None, 
            **opts) -> _P:
        
        sa = symbol(abstract)
        sc = symbol(concrete)

        if sa() is not sc():
            self.setdefault(self.make_factory(sc, sc, priority, contexts, **opts))
            return self.alias(sa, sc, priority, contexts, **opts)

        return self.push(self.make_factory(abstract, concrete, priority, contexts, **opts))
    
    bind = factory

    def value(self, 
            abstract: _I, 
            concrete: Callable[..., _T], 
            priority: int = 1, 
            contexts: Optional[Sequence[str]] = None, 
            **opts) -> _P:
        return self.push(self.make_value(abstract, concrete, priority, contexts, **opts))
   
    def make_alias(self, 
            abstract: _I, 
            concrete: _I, 
            priority: int = 1, 
            contexts: Optional[Sequence[str]] = None, 
            **options) -> AliasProvider:
        cls = self._alias_provider_cls
        return cls(abstract, concrete, priority, contexts, **options)
            
    def make_factory(self, 
            abstract: _I, 
            concrete: Callable[..., _T], 
            priority: int = 1, 
            contexts: Optional[Sequence[str]] = None, 
            **options) -> _P:

        cls = {
            KindOfSymbol.TYPE: self._type_provider_cls,
            KindOfSymbol.FUNCTION: self._method_provider_cls,
            KindOfSymbol.METHOD: self._method_provider_cls,
        }.get(symbol(concrete).kind, self._factory_provider_cls)

        return cls(abstract, concrete, priority, contexts, **options)
                   
    def make_value(self, 
            abstract: _I, 
            concrete: Callable[..., _T], 
            priority: int = 1, 
            contexts: Optional[Sequence[str]] = None, 
            **options) -> _P:
        cls = self._value_provider_cls
        return cls(abstract, concrete, priority, contexts, **options)
            
    def push(self, provider: _P):
        stack = super().setdefault(provider.abstract, [])
        stack.append(provider)
        stack.sort()
        return provider

    @overload
    def pop(self, provider: _P, default=...):...
    @overload
    def pop(self, key: symbol[_I], default=...):...
    def pop(self, k, default=...):
        provider = None
        if isinstance(k, Provider): 
            provider = k
            k = k.abstract
            
        try:
            if provider is None:
                return super().pop(k)
            else:
                self[k].remove(provider)
        except KeyError:
            if default is ...:
                raise
            return default
        else:
            return provider

    def setdefault(self, provider, val: _P = ...) -> _P:
        if isinstance(val, Provider):
            provider = val

        stack = super().setdefault(provider.abstract, [])
        stack or stack.append(provider)
        return stack[-1]




