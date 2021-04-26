from __future__ import annotations

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


from flex.utils.decorators import export

from djx.common.utils import Void

from .symbols import symbol, _ordered_id, identity
from . import abc
from .abc import Injectable, Injector, Scope, ScopeAlias, Resolver, T_Injectable, T_Injected, T_Injector, T_Provider, T

__all__ = [

]

T_ScopeAlias = TypeVar('T_ScopeAlias', str, ScopeAlias)
T_Resolver = TypeVar('T_Resolver', bound='Resolver')



_provided = set()

def is_provided(obj) -> bool:
    return identity(obj) in _provided or (isinstance(obj, type) and issubclass(obj, abc.Injector))



@export()
def alias(abstract: T_Injectable, 
        alias: abc.Injectable[T], 
        priority: int = 1, *, 
        scope: str = None, 
        **opts) -> AliasProvider:
    """Registers an `AliasProvider`
    """
    return provide(abstract, priority=priority, alias=alias, scope=scope, **opts)
        


@export()
def injectable(priority: int = 1, scope: str = None, *, cache:bool=None, abstract: T_Injectable = None, **opts):
    def register(factory: Callable[..., T]):
        provide(abstract or factory, priority=priority, factory=factory, scope=scope, cache=cache, **opts)
        return factory

    return register
     



_kwd_cls_map = dict[str, Callable[..., type[T_Provider]]](
    factory=lambda: FactoryProvider, 
    alias=lambda: AliasProvider, 
    value=lambda: ValueProvider
)

@overload
def provide(*abstracts: T_Injectable, priority: int = 1, value: T, scope: str = None, **opts) -> 'ValueProvider': ...
@overload
def provide(*abstracts: T_Injectable, priority: int = 1, alias: abc.Injectable[T], scope: str = None, **opts) -> 'AliasProvider': ...
@overload
def provide(*abstracts: T_Injectable, priority: int = 1, factory: Callable[..., T],
            scope: str = None, cache: bool = None, **opts) -> 'FactoryProvider': ...
@export()
def provide(*abstracts: T_Injectable, priority: int = 1, 
            scope: str = None, cache: bool = None, **kwds) -> T_Provider:
    cls, concrete = next((c(), kwds.pop(k)) for k,c in _kwd_cls_map.items() if k in kwds)

    rv = {}
    for abstract in abstracts:
        if abstract in rv:
            continue

        rv[abstract] = register_provider(
            cls(abstract, concrete, priority, cache=cache, scope=scope, **kwds)
        )

    return rv[abstracts[0]] if len(abstracts) == 1 else rv.values()





@export()
def register_provider(provider: T_Provider, scope = None) -> T_Provider:
    abc.Scope.register_provider(provider, scope)
    return provider






T_R = TypeVar('T_R')


@export()
@abc.Resolver.register
class Resolver(Generic[T, T_R, T_Injectable, T_Injector]):

    __slots__ = ('abstract', 'bound', 'concrete', 'value')

    abstract: T_Injectable
    concrete: T_R
    value: T
    bound: T_Injector

    def __init__(self, abstract: T_Injectable, concrete: T_R=None, *, bound: T_Injector=None, value: T=Void) -> None:
        self.abstract = abstract
        self.concrete = concrete
        self.bound = bound
        self.value = value

    def bind(self: T_Resolver, inj: T_Injector) -> T_Resolver:
        if inj is not self.bound:
            return self.clone(bound=inj)
        return self
    
    def clone(self, abstract=..., bound=...):
        rv = self.__class__(
                self.abstract if abstract is ... else abstract, 
                self.concrete,
                bound=self.bound if bound is ... else bound, 
            )
        # rv.value = self.value
        return rv


@export()
class ValueResolver(Resolver[T, T, T_Injectable, T_Injector]):

    __slots__ = ()

    def __init__(self, abstract, value=None, *, bound=None):
        super().__init__(abstract, bound=bound, value=value)
      
    def __call__(self, inj: T_Injector=...) -> T:
        return self.value

    def clone(self, abstract=..., bound=...):
        return self.__class__(
                self.abstract if abstract is ... else abstract, 
                self.value,
                bound=self.bound if bound is ... else bound, 
            )


    # @classmethod
    # def none(cls, abstract: T_Injectable, *, bound: T_Injector=None): #-> ValueResolver[Literal[None], T_Injectable, T_Injector]:
    #     return cls(abstract, None, bound=bound)



                                                                                                                                                                 
@export()
class AliasResolver(Resolver[T, T_Injectable, T_Injectable, T_Injector]):
    """BoundProvider Object"""

    __slots__ = ()

    def __call__(self, inj: Injector=...) -> T:
        return self.bound[self.concrete]





@export()
class FuncResolver(Resolver[T, Callable, T_Injectable, T_Injector]):
    """BoundProvider Object"""

    __slots__ = 'cache', '__call__'

    def __init__(self, abstract, concrete, *, bound=None, cache=False, **kwds):
        super().__init__(abstract, concrete, bound=bound, **kwds)
        self.cache = cache
        if cache:
            def __call__() -> T:
                self.value = concrete()
                return self.value
            self.__call__ = __call__
        else:
            self.__call__ = concrete
    
    def __calls__(self) -> T:
        inj = self.bound
        if p := self.params:
            rv = self.concrete(*p.inject_args(inj), **p.inject_kwargs(inj))
        else:
            rv = self.concrete()
        
        if self.cache:
            self.value = rv
        
        return rv

    def clone(self, abstract=..., bound=...):
        return self.__class__(
                self.abstract if abstract is ... else abstract, 
                self.concrete,
                bound=self.bound if bound is ... else bound, 
                cache=self.cache,
            )


@export()
class FuncParamsResolver(FuncResolver):
    """FuncParamsResolver Object"""

    __slots__ = 'params',

    def __init__(self, abstract, concrete, *, bound=None, cache=False, params=None, **kwds):
        Resolver.__init__(self, abstract, concrete, bound=bound, **kwds)
        self.cache = cache
        self.params = params

        if cache:
            def __call__() -> T:
                self.value = concrete(*params.inject_args(bound), **params.inject_kwargs(bound))
                return self.value
        else:
            def __call__() -> T:
                return concrete(*params.inject_args(bound), **params.inject_kwargs(bound))
                
        self.__call__ = __call__
    
    def __calls__(self) -> T:
        inj = self.bound
        if p := self.params:
            rv = self.concrete(*p.inject_args(inj), **p.inject_kwargs(inj))
        else:
            rv = self.concrete()
        
        if self.cache:
            self.value = rv
        
        return rv

    def clone(self, abstract=..., bound=...):
        return self.__class__(
                self.abstract if abstract is ... else abstract, 
                self.concrete,
                bound=self.bound if bound is ... else bound, 
                cache=self.cache,
                params=self.params
            )



@export()
class Provider(abc.Provider[T, T_Injectable]):

    __slots__ = (
        'abstract', 'concrete', 'scope', 'cache', 
        'priority', 'options', '__pos',
    )
    
    abstract: symbol[T_Injectable]

    # scope: str
    # priority: int
    # concrete: Any
    # cache: bool
    # options: dict
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
        _provided.add(identity(self.abstract))

    def set_concrete(self, concrete) -> None:
        self.concrete = concrete
    
    def check(self):
        assert isinstance(self.abstract, Injectable), (
            f'`abstract` must be a `Injectable`. Got: {self.abstract!r}')

    def bind(self, inj: T_Injector):
        """Bind provider to given injector.
        """
        return self

    def __call__(self, inj: abc.Injector) -> T:
        return self.concrete

    def __order__(self):
        return (self.priority, self.abstract, self.__pos)
  
    def __eq__(self, x) -> bool:
        if isinstance(x, abc.Provider):
            return x.abstract == self.abstract
        
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.abstract)
    

@export()
class ValueProvider(Provider):

    __slots__ = ()
    concrete: T

    def set_concrete(self, concrete) -> None:
        self.concrete = concrete
        if self.cache is None:
            self.cache = True 
    
    def bind(self, inj: T_Injector):
        """Bind provider to given injector.
        """
        return ValueResolver(self.abstract, self.concrete, bound=inj)


    # def setup(self, scope: abc.Scope) -> Generator[tuple[T_Injectable, Resolver[T, T_Injectable]]]:
    #     # res: 
    #     yield self.abstract, ValueResolver(self.abstract, self.concrete)



@export()
class AliasProvider(Provider):

    __slots__ = ()
    concrete: symbol[T]

    def check(self):
        super().check()
        assert is_provided(self.concrete), (
                f'No provider for aliased `{self.concrete}` in `{self.abstract}`'
            )
        # assert not self.cache, f'AliasProvider cannot be cached'

    def __call__(self, inj: abc.Injector) -> T:
        return inj[self.concrete]

    def bind(self, inj: T_Injector):
        """Bind provider to given injector.
        """
        return AliasResolver(self.abstract, self.concrete, bound=inj)

    # def setup(self, scope: abc.Scope) -> Generator[tuple[T_Injectable, Resolver[T, T_Injectable]]]:
    #     yield self.abstract, AliasResolver(self.concrete)






@export()
class FactoryProvider(Provider):

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

    def bind(self, inj: T_Injector) -> Generator[tuple[T_Injectable, Resolver[T, T_Injectable]]]:
        params = self.params
        if not params:
            return FuncResolver(self.abstract, self.concrete, bound=inj, cache=self.cache)
        return FuncParamsResolver(self.abstract, self.concrete, bound=inj, cache=self.cache, params=self.params)
        res: FactoryResolver
        if params is None:
            if self.cache:
                def factory(inj: Injector=None):
                    res.value = self.concrete()
                    return res.value

                    # inj[self.abstract] = ValueResolver(self.abstract, self.concrete())
                    # return inj[self.abstract]
            else:
                def factory(inj: Injector):
                    return self.concrete()
        else:
            if self.cache:
                def factory(inj: Injector):
                    res.value = self.concrete(*params.inject_args(inj), **params.inject_kwargs(inj))
                    return inj[self.abstract]
            else:
                def factory(inj: Injector):
                    return self.concrete(*params.inject_args(inj), **params.inject_kwargs(inj))

        res = FactoryResolver(self.abstract, factory, bound=inj, cache=self.cache, params=params)
        return res










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

    def __class_getitem__(cls, params):
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
    




@export()
class Inject(Dependency[T_Injectable, T_Injected, T_ScopeAlias]):
    
    __slots__ = ()
    
    def __get__(self, typ, obj=None) -> T_Injected:
        from .di import final
        return self(final())
