
from collections import defaultdict
from collections.abc import Sequence, Mapping, Iterable, ItemsView
from re import S

from weakref import WeakSet

from types import FunctionType, MethodType
from typing import Any, Callable, ClassVar, Generic, Optional, Type, TypeVar, Union, overload


from flex.utils.decorators import export


from .symbols import symbol, _ordered_id
from .reg import registry
from . import abc

__all__ = [

]


_T = TypeVar('_T')
_I = TypeVar('_I', bound=abc.Injectable)
_P = TypeVar('_P', bound='Provider')
_T_Collect = TypeVar('_T_Collect', bound=Mapping[symbol, 'Provider'])



_provided = WeakSet()

def is_provided(obj) -> bool:
    return isinstance(obj, abc.SupportsIndentity) and symbol(obj) in _provided



@export()
def alias(abstract: _I, 
        alias: abc.Injectable[_T], 
        priority: int = 1, *, 
        scope: str = None, 
        **opts) -> 'AliasProvider':
    """Registers an `AliasProvider`
    """
    return provide(abstract, priority=priority, alias=alias, scope=scope, **opts)
        


@export()
def injectable(priority: int = 1, scope: str = None, *, cache:bool=None, abstract: _I = None, **opts):
    def register(factory: Callable[..., _T]):
        provide(abstract or factory, priority=priority, factory=factory, scope=scope, cache=cache, **opts)
        return factory

    return register
     



_kwd_cls_map = dict[str, Callable[..., type[_P]]](
    factory=lambda: FactoryProvider, 
    alias=lambda: AliasProvider, 
    value=lambda: ValueProvider
)

@overload
def provide(*abstracts: _I, priority: int = 1, value: _T, scope: str = None, **opts) -> 'ValueProvider': ...
@overload
def provide(*abstracts: _I, priority: int = 1, alias: abc.Injectable[_T], scope: str = None, **opts) -> 'AliasProvider': ...
@overload
def provide(*abstracts: _I, priority: int = 1, factory: Callable[..., _T],
            scope: str = None, cache: bool = None, **opts) -> 'FactoryProvider': ...
@export()
def provide(*abstracts: _I, priority: int = 1, 
            scope: str = None, cache: bool = None, **kwds) -> _P:
    cls, concrete = next((c(), kwds.pop(k)) for k,c in _kwd_cls_map.items() if k in kwds)

    rv = {}
    for abstract in abstracts:
        if abstract in rv:
            continue

        rv[abstract] = add_provider(
            cls(abstract, concrete, priority, cache=cache, scope=scope, **kwds)
        )

    return rv[abstracts[0]] if len(abstracts) == 1 else rv.values()





@export()
def add_provider(provider: _P, scope: str = None) -> _P:
    registry.add_provider(provider, scope)
    return provider






@export()
class Provider(abc.Provider[_T, _I]):

    __slots__ = ('__pos',)

    
    abstract: symbol[_I]

    # scope: str
    # priority: int
    # concrete: Any
    # cache: bool
    # options: dict
    __pos: int

    def __init__(self, 
                abstract: _I,   
                concrete: Any, 
                priority: Optional[int]=1, *,
                scope: str = None, 
                cache: bool=None, 
                **options) -> None:
        global _provided

        self.abstract = symbol(abstract)
        self.__pos = _ordered_id()
        self.scope = scope or self._default_scope
        self.cache = cache
        self.priority = priority or 0
        self.options = options
        self.set_concrete(concrete)
        symbol(self.scope) 
        _provided.add(self.abstract)

    def set_concrete(self, concrete) -> None:
        self.concrete = concrete
    
    def check(self):
        assert isinstance(self.abstract, symbol), '`abstract` must be a `symbpl`'

    def setup(self, scope: abc.Scope) -> None:
        pass

    def provide(self, inj: abc.Injector) -> _T:
        return self.concrete
#
    def __order__(self):
        return (self.priority, self.abstract, symbol(self.scope), self.__pos)
        
    def __ge__(self, x) -> bool:
        return self.__order__() >= x

    def __gt__(self, x) -> bool:
        return self.__order__() > x

    def __le__(self, x) -> bool:
        return self.__order__() <= x

    def __lt__(self, x) -> bool:
        return self.__order__() < x

    def __eq__(self, x) -> bool:
        return self.__order__() == x

    def __hash__(self) -> int:
        return hash(self.__order__())
    

@export()
class ValueProvider(Provider):

    __slots__ = ()
    concrete: _T

    def set_concrete(self, concrete) -> None:
        self.concrete = concrete
        if self.cache is None:
            self.cache = True 
    

@export()
class AliasProvider(Provider):

    __slots__ = ()
    concrete: symbol[_T]

    def check(self):
        super().check()
        assert is_provided(self.concrete), (
                f'No provider for aliased `{self.concrete}` in `{self.abstract}`'
            )
        assert not self.cache, f'AliasProvider cannot be cached'

    # def set_concrete(self, concrete) -> None:
    #     self.concrete = symbol(concrete)
    
    def provide(self, inj: abc.Injector) -> _T:
        return inj[self.concrete]




@export()
class FactoryProvider(Provider):

    __slots__ = ('_sig', '_params')
    concrete: symbol[Callable[..., _T]]

    @property
    def signature(self):
        if rv := getattr(self, '_sig', None):
            return rv
        
        from .inspect import signature
        self._sig = signature(self.concrete)
        return self._sig

    @property
    def params(self):
        try:
            return self._params
        except AttributeError:
            self._params = self.signature.bind_partial() or None
            return self._params

    def check(self):
        super().check()
        assert callable(self.concrete), (
                f'`concrete` must be a valid Callable. Got: {type(self.concrete)}'
            )

    def provide(self, inj: abc.Injector):
        if None is (params := self.params):
            return self.concrete()
        else:
            return self.concrete(*params.inject_args(inj), **params.inject_kwargs(inj))



class ProviderStack(dict[symbol[_I], list[_P]]):
    
    __slots__= ()

    def push(self, provider: _P) -> _P:
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

    @overload
    def __getitem__(self, k: slice) -> list[_P]: ...
    @overload
    def __getitem__(self, k: Any) -> _P: ...
    def __getitem__(self, k) -> _P:
        if isinstance(k, slice):
            return self[k.start]
        else:
            return self[k][-1]

    def heads(self):
        for k in self:
            yield k, self[k]
    
