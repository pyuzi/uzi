
from collections import defaultdict
from collections.abc import Sequence, Mapping, Iterable, ItemsView, Callable
from re import S

from weakref import WeakSet

from types import FunctionType, MethodType
from typing import (
    Annotated, Any, ClassVar, 
    Generic, NamedTuple, Optional, Type, TypeVar, Union, overload
)


from flex.utils.decorators import export

from djx.common.utils import Void

from .symbols import symbol, _ordered_id
from .reg import registry
from . import abc
from .abc import Injectable, Resolver, Scope, ScopeAlias, T_Injectable, T_Injected, T_Injector, T_Provider, T

__all__ = [

]




_provided = WeakSet()

def is_provided(obj) -> bool:
    return isinstance(obj, abc.SupportsIndentity) and symbol(obj) in _provided \
        or (isinstance(obj, type) and issubclass(obj, abc.Injector))



@export()
def alias(abstract: T_Injectable, 
        alias: abc.Injectable[T], 
        priority: int = 1, *, 
        scope: str = None, 
        **opts) -> 'AliasProvider':
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

        rv[abstract] = add_provider(
            cls(abstract, concrete, priority, cache=cache, scope=scope, **kwds)
        )

    return rv[abstracts[0]] if len(abstracts) == 1 else rv.values()





@export()
def add_provider(provider: T_Provider, scope = None) -> T_Provider:
    registry.add_provider(provider, scope)
    return provider




@export()
class Provider(abc.Provider[T, T_Injectable]):

    __slots__ = ('__pos',)

    
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

        self.abstract = symbol(abstract)
        self.__pos = _ordered_id()
        # self.scope = scope or self._default_scope
        self.scope = (None if scope is ... else scope) or Scope.ANY
        self.cache = cache
        self.priority = priority or 0
        self.options = options
        self.set_concrete(concrete)
        _provided.add(self.abstract)

    def set_concrete(self, concrete) -> None:
        self.concrete = concrete
    
    def check(self):
        assert isinstance(self.abstract, symbol), '`abstract` must be a `symbpl`'

    def setup(self, scope: abc.Scope) -> None:
        pass

    def __call__(self, inj: abc.Injector) -> T:
        return self.concrete

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
    concrete: T

    def set_concrete(self, concrete) -> None:
        self.concrete = concrete
        if self.cache is None:
            self.cache = True 
    

@export()
class AliasProvider(Provider):

    __slots__ = ()
    concrete: symbol[T]

    def check(self):
        super().check()
        assert is_provided(self.concrete), (
                f'No provider for aliased `{self.concrete}` in `{self.abstract}`'
            )
        assert not self.cache, f'AliasProvider cannot be cached'

    # def set_concrete(self, concrete) -> None:
    #     self.concrete = symbol(concrete)
    
    def __call__(self, inj: abc.Injector) -> T:
        return inj[self.concrete]




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


_ANY_SCOPE = Scope[Scope.ANY]
T_ScopeName = TypeVar('T_ScopeName', bound=str)


@export()
@Injectable.register
class Dependency(Resolver[T_Injectable, T_Injected], Generic[T_Injectable, T_Injected, T_ScopeName]):
    """DependencyResolver Object"""
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
    def scope(self) -> Scope[T_ScopeName]:
        return self._scope

    def __eq__(self, x) -> bool:
        if isinstance(x, Dependency):
            return self._scope == x._scope and self._deps == x._deps
        return NotImplemented

    def __hash__(self) -> bool:
        return hash(self.scope, self.deps)

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
class Inject(Dependency[T_Injectable], Generic[T_Injectable, T_Injected]):
    
    __slots__ = ()
    
    def __get__(self, typ, obj=None) -> T_Injected:
        from .di import final
        return self(final())
