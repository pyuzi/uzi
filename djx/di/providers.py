from __future__ import annotations
from abc import abstractmethod

from functools import cache, wraps
from collections import defaultdict
from collections.abc import Sequence, Mapping, Iterable, ItemsView, Callable
from re import S

from weakref import WeakSet

from types import FunctionType, MethodType
from typing import (
    Annotated, Any, ClassVar, Generator, 
    Generic, Literal, NamedTuple, Optional, Protocol, Type, TypeVar, Union, overload
)


from djx.common.utils import export

from djx.common.utils import Void, saferef
from djx.di.inspect import BoundArguments

from .symbols import symbol, _ordered_id, identity
from . import abc
from .abc import Injectable, Scope, ScopeAlias, T_Injectable, T_Injected, T_Injector, T_Provider, T, T_Scope, T_Resolver



T_ScopeAlias = TypeVar('T_ScopeAlias', str, ScopeAlias)



_provided = set()

def is_provided(obj) -> bool:
    return saferef(obj) in _provided # or (isinstance(obj, type) and issubclass(obj, abc.Injector))



@export()
def alias(abstract: T_Injectable, 
        alias: abc.Injectable[T], 
        priority: int = 1, *, 
        scope: str = None, 
        cache:bool=None, 
        **opts) -> AliasProvider:
    """Registers an `AliasProvider`
    """
    return provide(abstract, priority=priority, alias=alias, scope=scope, cache=cache, **opts)
        


@export()
def injectable(scope: str = None, priority: int = 1, *, cache:bool=None, abstract: T_Injectable = None,**opts):
    def register(factory):
        provide(
            abstract or factory, 
            priority=priority, 
            factory=factory, 
            scope=scope, 
            cache=cache, 
            **opts)
        return factory

    return register
     



_kwd_cls_map = dict[str, Callable[..., type[T_Provider]]](
    factory=lambda: FactoryProvider, 
    alias=lambda: AliasProvider, 
    value=lambda: ValueProvider
)

# @overload
# def provide(*abstracts: T_Injectable, priority: int = 1, value: T, scope: str = None, with_context:bool=None, **opts): ...
# @overload
# def provide(*abstracts: T_Injectable, priority: int = 1, alias: abc.Injectable[T], scope: str = None, **opts): 
# ...
@overload
def provide(abstract: T_Injectable=..., 
            *abstracts: T_Injectable, 
            factory: Callable[..., T]=None,
            alias: abc.Injectable[T]=None,
            value: T=None,
            priority: int = 1, 
            scope: str = None, 
            cache: bool = None,
            **opts): 
    ...
@export()
def provide(abstract: T_Injectable=..., 
            *abstracts:T_Injectable, 
            priority: int = 1, 
            scope: str = None, 
            cache: bool = None, 
            **kwds):

    def register(_abstract):
        
        cls, concrete = next((c(), kwds.pop(k)) for k,c in _kwd_cls_map.items() if k in kwds)

        seen = set()
        for abstract in (_abstract, *abstracts):
            if abstract not in seen:
                seen.add(abstract)
                prov = cls(abstract, concrete, priority, cache=cache, scope=scope, **kwds)
                register_provider(prov)

        return _abstract

        # return rv[abstracts[0]] if len(abstracts) == 1 else rv.values()

    if abstract is ...:
        return register
    else:
        return register(abstract)





@export()
def register_provider(provider: T_Provider, scope = None) -> T_Provider:
    abc.Scope.register_provider(provider, scope)
    return provider








@export()
class ConcreteResolver(abc.Resolver[T], Generic[T, T_Injectable]):

    __slots__ = 'concrete',

    concrete: T_Injectable

    def __init__(self, concrete: T_Injectable=None, value: T=Void, *, bound: T_Injector=None) -> None:
        super().__init__(value, bound=bound)
        self.concrete = concrete

    def clone(self, *args, **kwds):
        return super().clone(self.concrete, *args, **kwds)




@export()
class ValueResolver(abc.Resolver[T]):

    __slots__ = ()




@export()
class InjectorResolver(abc.Resolver[T_Injector]):

    __slots__ = ()

    def __init__(self, value=Void, bound=None):
        self.value = self.bound = bound





                                                                                                                                                                 
@export()
class AliasResolver(ConcreteResolver[T, T_Injectable]):
    """Resolver Object"""

    __slots__ = 'cache', '__call__',

    def __init__(self, concrete, *, cache=False, **kwds):
        super().__init__(concrete, **kwds)
        self.cache = cache
        if cache:
            def __call__() -> T:
                self.value = self.bound[concrete]
                return self.value
        else:
            def __call__() -> T:
                return self.bound[concrete]
        self.__call__ = __call__

    def clone(self, *args, **kwds):
        kwds.setdefault('cache', self.cache)
        return super().clone(*args, **kwds)


@export()
class FuncResolver(ConcreteResolver[T, Callable[..., T]]):
    """Resolver Object"""

    __slots__ = 'cache', '__call__'

    def __init__(self, concrete, *, cache=False, **kwds):
        super().__init__(concrete, **kwds)
        self.cache = cache
        if cache:
            def __call__(*args, **kwds) -> T:
                self.value = concrete(*args, **kwds)
                return self.value
            self.__call__ = __call__
        else:
            self.__call__ = concrete

    def clone(self, *args, **kwds):
        kwds.setdefault('cache', self.cache)
        return super().clone(*args, **kwds)





@export()
class FuncParamsResolver(FuncResolver):
    """FuncParamsResolver Object"""

    __slots__ = 'params',

    params: BoundArguments

    def __init__(self, concrete, *, params=None, **kwds):
        super().__init__(concrete, **kwds)

        self.params = params
        if self.cache:
            def __call__(*args, **kwds) -> T:
                bound = self.bound
                self.value = concrete(*params.inject_args(bound, kwds), *args, **params.inject_kwargs(bound, kwds))
                return self.value
        else:
            def __call__(*args, **kwds) -> T:
                bound = self.bound
                return concrete(*params.inject_args(bound, kwds), *args, **params.inject_kwargs(bound, kwds))
                
        self.__call__ = __call__
    
    def clone(self, *args, **kwds):
        kwds.setdefault('params', self.params)
        return super().clone(*args, **kwds)




@export()
class Provider(abc.Provider[T, T_Injectable, T_Resolver, T_Scope]):

    __slots__ = (
        'abstract', 'concrete', 'scope', 'cache', 
        'priority', 'options', '__pos', '_resolver',
    )
    
    abstract: symbol[T_Injectable]
    __pos: int

    def __init__(self, 
                abstract: T_Injectable,   
                concrete: Any, 
                priority: Optional[int]=1, *,
                scope: str = None, 
                cache: bool=None, 
                **options) -> None:
        global _provided

        self.abstract = abstract
        self.__pos = _ordered_id()
        self.scope = scope or self._default_scope
        self.cache = cache
        self.priority = priority or 0
        self.options = options
        self.set_concrete(concrete)
        _provided.add(saferef(self.abstract))

    def set_concrete(self, concrete) -> None:
        self.concrete = concrete
    
    def check(self):
        assert isinstance(self.abstract, Injectable), (
            f'`abstract` must be a `Injectable`. Got: {self.abstract!r}')

    def resolver(self, scope: T_Scope) -> T_Resolver:
        """Get a resolver for the provider based on scope.
        """
        if not hasattr(self, '_resolver'):
            self._resolver = self.make_resolver(scope)
        return self._resolver

    @abstractmethod
    def make_resolver(self, scope: T_Scope):
        ...

    def __order__(self):
        return (self.priority, self.abstract, self.__pos)
  
    def __eq__(self, x) -> bool:
        if isinstance(x, abc.Provider):
            return x.abstract == self.abstract
        
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.abstract)
    


@export()
class ValueProvider(Provider[T, T_Injectable, ValueResolver[T], T_Scope]):

    __slots__ = ()
    concrete: T

    def make_resolver(self, scope: T_Scope):
        return ValueResolver(self.concrete)





@export()
class AliasProvider(Provider[T, T_Injectable, AliasResolver[T, T_Injectable], T_Scope]):

    __slots__ = ()
    concrete: symbol[T]

    def check(self):
        super().check()
        assert is_provided(self.concrete), (
                f'No provider for aliased `{self.concrete}` in `{self.abstract}`'
            )

    def make_resolver(self, scope: T_Scope):
        return AliasResolver(self.concrete, cache=self.cache)




@export()
class FactoryProvider(Provider[T, T_Injectable, FuncResolver[T], T_Scope]):

    __slots__ = ('_sig', '_params')
    concrete: symbol[Callable[..., T]]

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

    def __call__(self, inj: abc.Injector):
        if None is (params := self.params):
            return self.concrete()
        else:
            return self.concrete(*params.inject_args(inj), **params.inject_kwargs(inj))

    def make_resolver(self, scope: T_Scope):
        params = self.params
        if not params:
            return FuncResolver(self.concrete, cache=self.cache)
        return FuncParamsResolver(self.concrete, cache=self.cache, params=params)





class InjectorProvider(ValueProvider):
    __slots__ = ()

    def make_resolver(self, scope: T_Scope):
        return InjectorResolver()





@export()
class Depends:
    """Annotates type as a `Dependency` that can be resolved by the di.
    
    Example: 
        Depends[t] # type(injector[t]) == t 
        
        Depends[InjectableType]
        Depends[typ, Injectable] # type(injector[Injectable]) = typ

        Depends[type, Scope['scope'], injectable] # type(injector[Scope('scope')][injectable]) == typ
        Depends[typ, Scope['scope']] ==  Depends[typ, typ, 'scope']  # type(injector[Scope('scope')][typ]) == typ 
    """

    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise TypeError("Type Depends cannot be instantiated.")

    def __class_getitem__(cls, params: Union[T, tuple[T, ...]]) -> Annotated[T, Dependency]:
        scope = None
        if not isinstance(params, tuple):
            deps = ((tp := params),)
        elif(lp := len(params)) == 1:
            tp = (deps := params)[0]
        elif lp > 1:
            if isinstance(params[1], ScopeAlias):
                tp, scope, *deps = params
            else:
                tp, *deps = params
        

        deps or (deps := (tp,))
        isinstance(deps, list) and (deps := tuple(deps))
        _dep_types = (list, dict, Injectable, Dependency)
        if any(not isinstance(d, _dep_types) for d in deps):
            raise TypeError("Depends[...] should be used "
                            "with at least one type argument and "
                            "an optional ScopeAlias (Scope['name'])."
                            "and 1 or more Injectables if the type arg "
                            "is not the injectable")
        
        return Annotated[tp, Dependency(deps, scope=scope)]

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__module__}.Depends")








@export()
@Injectable.register
class Dependency(Generic[T_Injectable, T_Injected, T_ScopeAlias]):
    """Dependency Object"""
    __slots__ = '_deps', '_scope', '_default', '__weakref__'

    def __new__(cls, deps: T_Injectable, scope: ScopeAlias=..., *, default: Union[T_Injected, Callable[..., T_Injected]]=...):
        if isinstance(deps, cls):
            if scope in (..., None, deps.scope) and default in (..., deps.default):
                return deps
            else:
                kwds = dict()
                scope in (..., None) or kwds.update(scope=scope)
                default is ... or kwds.update(default=default)
                return deps.copy(**kwds)
        return super().__new__(cls)

    def __init__(self, deps: T_Injectable, scope: ScopeAlias=..., *, default: Union[T_Injected, FunctionType, MethodType]=...):
        self._deps = tuple(deps) if isinstance(deps, list) \
            else deps if isinstance(deps, tuple) else (deps,)
        self._scope = Scope[(None if scope is ... else scope) or Scope.ANY]
        self._default = default
    
    @property
    def deps(self) -> T_Injectable:
        return self._deps

    @property
    def scope(self) -> Scope[T_ScopeAlias]:
        return self._scope

    def __eq__(self, x) -> bool:
        if isinstance(x, Dependency):
            return self._scope == x._scope and self._deps == x._deps
        return NotImplemented

    def __hash__(self) -> bool:
        return hash((self.scope, self.deps))

    def __call__(self, inj) -> T_Injectable:
        # return inj[self._scope][self._deps]
        inj = inj[self._scope]
        return next((inj[d] for d in self._deps), self._default)

    def copy(self, **kwds) -> T_Injectable:
        kwds['scope'] = kwds.get('scope') or self._scope
        kwds['deafult'] = kwds.setdefault('deafult', self._default)
        return self.__class__(self._deps, **kwds)
    __copy__ = copy
    

