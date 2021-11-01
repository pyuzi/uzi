from __future__ import annotations
from logging import getLogger
import typing as t 
from abc import abstractmethod
from djx.common.collections import fallback_default_dict, fallbackdict, frozendict, nonedict, orderedset

from collections.abc import  Callable
from copy import copy


from types import FunctionType, MappingProxyType, MethodType
from typing import (
    ClassVar, Generator, 
)

from djx.common.saferef import SafeRefSet
from djx.common.typing import GenericLike
from djx.common.utils import export, Void
from .inspect import BoundArguments, ordered_id
from . import abc
from .abc import Injectable, Scope, ScopeAlias, T_Injectable, T_Injected, T_Injector, T_Provider, T, T_Scope, T_Resolver

from .resolvers import *




T_ScopeAlias = t.TypeVar('T_ScopeAlias', str, ScopeAlias)

logger = getLogger(__name__)

# _provided = SafeRefSet()

# def is_provided(obj) -> bool:
#     return obj in _provided 
#         # or (isinstance(obj, GenericLike) and obj.__origin__ in _provided)
#     # return saferef(obj) in _provided # or (isinstance(obj, type) and issubclass(obj, abc.Injector))

# is_provided = _provided.__contains__


# @export()
# def alias(abstract: T_Injectable, 
#         alias: abc.Injectable[T], 
#         priority: int = 1, *, 
#         scope: str = 'any', 
#         cache:bool=None, 
#         **opts) -> AliasProvider:
#     """Registers an `AliasProvider`
#     """
#     return provide(abstract, priority=priority, alias=alias, scope=scope, cache=cache, **opts)
        


# @export()
# def injectable(scope: str = None, priority: int = 1, *, cache:bool=None, abstract: T_Injectable = None,**opts):
#     def register(factory):
#         provide(
#             abstract or factory, 
#             priority=priority, 
#             factory=factory, 
#             scope=scope, 
#             cache=cache, 
#             **opts)
#         return factory

#     return register
     



# _kwd_cls_map = dict[str, Callable[..., type[T_Provider]]](
#     factory=lambda: FactoryProvider, 
#     alias=lambda: AliasProvider, 
#     value=lambda: ValueProvider
# )

# # @t.overload
# # def provide(*abstracts: T_Injectable, priority: int = 1, value: T, scope: str = None, with_context:bool=None, **opts): ...
# # @t.overload
# # def provide(*abstracts: T_Injectable, priority: int = 1, alias: abc.Injectable[T], scope: str = None, **opts): 
# # ...
# @t.overload
# def provide(abstract: T_Injectable=..., 
#             *abstracts: T_Injectable, 
#             factory: Callable[..., T]=None,
#             alias: abc.Injectable[T]=None,
#             value: T=None,
#             priority: int = 1, 
#             scope: str = None, 
#             cache: bool = None,
#             **opts): 
#     ...
# @export()
# def provide(abstract: T_Injectable=..., 
#             *abstracts:T_Injectable, 
#             priority: int = 1, 
#             scope: str = None, 
#             cache: bool = None, 
#             **kwds):

#     def register(_abstract):
        
        
#         cls, concrete = next(
#             ((c(), kwds.pop(k)) for k,c in _kwd_cls_map.items() if k in kwds), 
#             (None, None)
#         )

#         if None is cls is concrete:
#             assert callable(_abstract)
#             cls = _kwd_cls_map['factory']
#             concrete = _abstract

#         seen = set()
#         for abstract in (_abstract, *abstracts):
#             if abstract not in seen:
#                 seen.add(abstract)
#                 prov = cls(abstract, concrete, priority, cache=cache, scope=scope, **kwds)
#                 register_provider(prov)

#         return _abstract

#         # return rv[abstracts[0]] if len(abstracts) == 1 else rv.values()

#     if abstract is ...:
#         return register
#     else:
#         return register(abstract)





# @export()
# def register_provider(provider: T_Provider, scope = None) -> T_Provider:
#     abc.Scope.register_provider(provider, scope)
#     return provider




@export()
class Provider(abc.Provider[T_Injected, T_Injectable, T_Resolver]):

    __slots__ = (
        'abstract', 'concrete', 'scope', 'cache', 
        'priority', '__pos', '_resolver', 'options',
        '_parameterized',
    )
    
    abstract: T_Injectable
    _parameterized: dict[tuple,T_Provider]

    __pos: int

    @classmethod
    def create(cls, abstract: T_Injectable, concrete: t.Any = ..., **kwds):
        __base__ = cls
        if cls is Provider:
            if concrete is ...:
                if 'alias' in kwds:
                    cls = AliasProvider
                    concrete = kwds.pop('alias')
                elif 'value' in kwds:
                    cls = ValueProvider
                    concrete = kwds.pop('value')
                elif 'factory' in kwds:
                    cls = FactoryProvider
                    concrete = kwds.pop('factory', abstract)
                else:
                    raise TypeError(f'taka-taka -> {abstract=} -> {concrete=} {kwds=}')
            else:
                cls = FactoryProvider
            
            # debug('__base__'/, __base__, cls, abstract, concrete, kwds)
            return cls(abstract, concrete, **kwds)

        # debug('__self__', __base__, cls, abstract, concrete, kwds)
        return cls(abstract, concrete, **kwds)


    def __init__(self, 
                abstract: T_Injectable,   
                concrete: t.Any, *,
                priority: t.Optional[int]=1,
                scope: str = None, 
                cache: bool=None, 
                **options) -> None:
        self.abstract = abstract
        self.__pos = ordered_id()
        self.scope = scope # or self._default_scope
        self.cache = cache
        self.priority = priority or 0

        self.options = fallbackdict(None, options)
        
        self.set_concrete(concrete)

    @property
    def parameterized(self):
        try:
            return self._parameterized
        except AttributeError:
            if self.can_parameterize():
                self._parameterized = fallback_default_dict(self.as_parameterized)
            else:
                self._parameterized = nonedict()

            return self._parameterized

    def as_parameterized(self, token):
        cp=copy(self)
        cp.abstract=token
        return cp
    
    def set_concrete(self, concrete) -> None:
        self.concrete = concrete
    
    def check(self):
        assert isinstance(self.abstract, Injectable), (
            f'`abstract` must be a `Injectable`. Got: {self.abstract!r}')

    def resolver(self, scope: T_Scope) -> T_Resolver:
        """Get a resolver for the provider based on scope.
        """
        try:
            return self._resolver
        except AttributeError:
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
        # logger.warning(f'{self.__class__.__name__}.')
        return hash(self.abstract)
    
    def __getstate__(self):
        getattr = self.__getattribute__
        return {k: getattr(k) for k in (
                'abstract', 'concrete', 'scope', 'cache', 
                'priority', '__pos', 'options',
            )}
        
    def __setstate__(self, state):
        setattr = self.__setattr__
        cp = {'options'}

        for k,v in state.items():
            if k in cp:
                setattr(k, copy(v))
            else:
                setattr(k, v)
        
                
    def can_parameterize(self):
        return not not getattr(self.abstract, '__parameters__', None)

    def __repr__(self):
        return f'{self.__class__.__name__}({self.abstract}, {self.concrete}, {self.scope})'



@export()
class ValueProvider(Provider):

    __slots__ = ()
    concrete: T

    def make_resolver(self, scope: T_Scope):
        return ValueResolver(self.concrete)





@export()
class AliasProvider(Provider):

    __slots__ = '_params',
    concrete: T

    # def check(self):
        # super().check()
        # assert is_provided(self.concrete), (
        #         f'No provider for aliased `{self.concrete}` in `{self.abstract}`'
        #     )

    @property
    def params(self):
        try:
            return self._params
        except AttributeError:
            args = self.options['args']
            kwds = self.options['kwargs']
            self._params = (args or (), kwds or {}) if args or kwds else None
            return self._params

    def make_resolver(self, scope: T_Scope):
        params = self.params
        if params is None:
            return AliasResolver(self.concrete, cache=self.cache)
        return AliasWithParamsResolver(self.concrete, cache=self.cache, params=params)




@export()
class FactoryProvider(Provider):

    __slots__ = ('_sig', '_params')
    concrete: Callable[..., T]

    @property
    def signature(self):
        try:
            return self._sig
        except AttributeError:
            from .inspect import signature
            self._sig = signature(self.concrete)
            return self._sig

    @property
    def params(self):
        try:
            return self._params
        except AttributeError:
            args = self.options['args'] or ()
            kwds = self.options['kwargs'] or {}
            self._params = self.signature.bind_partial(*args, **kwds) or None
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
        if params is None:
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

    def __new__(cls):
        raise TypeError("Type Depends cannot be instantiated.")

    def __class_getitem__(cls, params: t.Union[T, tuple[T, ...]]) -> t.Annotated[T, 'Dependency']:
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
        _dep_types = (list, dict, Injectable, DependencyAnnotation)
        if any(not isinstance(d, _dep_types) for d in deps):
            raise TypeError("Depends[...] should be used "
                            "with at least one type argument and "
                            "an t.Optional ScopeAlias (Scope['name'])."
                            "and 1 or more Injectables if the type arg "
                            "is not the injectable")
        
        return t.Annotated[tp, DependencyAnnotation(deps, scope=scope)]

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__module__}.Depends")








@export()
@Injectable.register
class DependencyAnnotation(t.Generic[T_Injectable, T_Injected, T_ScopeAlias]):
    """Dependency Object"""
    __slots__ = '_deps', '_scope', '_default', '__weakref__'

    def __new__(cls, deps: T_Injectable, scope: ScopeAlias=..., *, default: t.Union[T_Injected, Callable[..., T_Injected]]=...):
        if isinstance(deps, cls):
            if scope in (..., None, deps.scope) and default in (..., deps.default):
                return deps
            else:
                kwds = dict()
                scope in (..., None) or kwds.update(scope=scope)
                default is ... or kwds.update(default=default)
                return deps.copy(**kwds)
        return super().__new__(cls)

    def __init__(self, deps: T_Injectable, scope: ScopeAlias=..., *, default: t.Union[T_Injected, FunctionType, MethodType]=...):
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
        if isinstance(x, DependencyAnnotation):
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
    

