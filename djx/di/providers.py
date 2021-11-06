from __future__ import annotations
from enum import auto
from logging import getLogger
import typing as t 
from abc import abstractmethod
from weakref import finalize
from djx.common.collections import AttributeMapping, fallback_default_dict, fallbackdict, frozendict, nonedict, orderedset

from collections.abc import  Callable, Hashable, Sequence
from copy import copy


from types import FunctionType, MappingProxyType, MethodType
from djx.common.enum import IntEnum, auto
from djx.common.proxy import unproxy

from djx.common.saferef import ReferenceType, saferef, SafeRefSet
from djx.common.typing import GenericLike
from djx.common.utils import export, Void, cached_property, Missing, noop
from .inspect import BoundArguments, ordered_id
from . import abc
from .abc import (
    Injectable, ScopeAlias, T_Injectable, T_Injected, T_Injector, T_Provider, T, T_Scope, T_Resolver,
    T_UsingAny, Scope
)

from .resolvers import *
from .resolvers import Resolver as DependencyRef
from .container import IocContainer
from .common import KindOfProvider


if t.TYPE_CHECKING:
    from . import Scope, InjectableSignature


logger = getLogger(__name__)


T_ScopeAlias = t.TypeVar('T_ScopeAlias', str, ScopeAlias)






@export()
class Provider(abc.Provider[T_Injected, T_Injectable, T_Resolver]):

    concrete: T_UsingAny[T_Injected]
    kind: t.Final[t.Union[KindOfProvider, None]] = None

    __hidden_attrs__: t.Final[orderedset[str]] = ...

    # _using_kwarg_: t.ClassVar = 'concrete'
    _sig: 'InjectableSignature'

    _resolvers: fallback_default_dict[str, SafeRefSet]

    __pos: int

    def __init_subclass__(cls, hidden_attrs=(), **kwds) -> None:
        super().__init_subclass__(**kwds)

        flip = set(a for a in hidden_attrs if a[0] == '~')
        cls.__hidden_attrs__ = hidden_attrs = orderedset(hidden_attrs) ^ flip
        
        for attr in dir(cls):
            if isinstance(getattr(cls, attr, None), cached_property):
                cls.__hidden_attrs__.add(attr)
        
        if flip:
            cls.__hidden_attrs__ -= (a[1:] for a in flip)

    def __init__(self, concrete: t.Any, /, **kwds) -> None:

        self.concrete = concrete

        kwds = dict(self._defaults_() or (), **kwds)
        kwds['priority'] = kwds.get('priority', 1) or 0
        
        self._assing(**kwds)
        self._boot_()
        self.__statekeys__
        
    def _defaults_(self) -> dict:
        return

    def _boot_(self):
        self.__pos = ordered_id()

    @property
    def resolvers(self):
        try:
            return self._resolvers
        except AttributeError:
            self._resolvers = fallback_default_dict(SafeRefSet)
            return self._resolvers

    @property
    def signature(self):
        try:
            return self._sig
        except AttributeError:
            from .inspect import signature
            if callable(self.concrete):
                self._sig = signature(self.concrete, evaltypes=True)
            else:
                self._sig = None
            return self._sig

    @cached_property[orderedset[str]]
    def __statekeys__(self):
        return orderedset(self._iter_statekeys())

    def _assing(self, **kwds):
        setattr = self.__setattr__
        for k,v in kwds.items():
            if k[0] == '_' or k[-1] == '_':
                raise AttributeError(f'invalid attribute {k!r}')
            setattr(k, v)

        return self

    def get(self, key, default=None):
        return getattr(self, key, default)

    def clone(self):
        return copy(self)
        
    def replace(self, **kwds):
        return self.clone()._assing(**kwds)

    @t.overload
    def flush(self, scope: str, /) -> Sequence[T_Injectable]:
        ...
    @t.overload
    def flush(self, scopes: Sequence[str]=..., /, all: bool=False) -> dict[str, Sequence[T_Injectable]]:
        ...

    def flush(self, scopes: t.Union[Sequence[str], str]=..., *, all: bool=False):
        if isinstance(scopes, str):
            return tuple(self.resolvers.pop(scopes, ()))
        elif all:
            scopes = tuple(self.resolvers.keys())
        elif scopes is ...:
            raise ValueError(f'provide a scopes or set all=True')
        
        return { s: self.flush(s) for s in scopes}

    def __getstate__(self):
        dct = self.__dict__
        return { k: dct[k] for k in self.__statekeys__ if k in dct }

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._boot_()
        del self.__statekeys__
        self.__statekeys__

    def _iter_statekeys(self):
        excludes = self.__hidden_attrs__
        for k in self.__dict__.keys():
            if not(k in excludes or k[:1] == '_' or k[-1] == '_'):
                yield k

    def implicit_tag(self):
        if isinstance(self.concrete, Hashable):
            return self.concrete
        return NotImplemented

    def _cleanup_resolve_(self, scope: str, key: ReferenceType):
        return self.resolvers.get(scope, nonedict()).pop(key, None) is not None

    @abstractmethod
    def make_resolver(self, token: T_Injectable, scope: T_Scope) -> Resolver[T_Injected]:
        ...
    
    def __call__(self, token: T_Injectable, scope: T_Scope) -> Resolver[T_Injected]:
        self.resolvers[scope.name].add(token)
        return self.make_resolver(token, scope)

    def __order__(self):
        return (self.priority, self.__pos)
  
    def __eq__(self, x) -> bool:
        return self.__class__ is x.__class__ \
            and self.__getstate__() == x.__getstate__()

    def __repr__(self):
        return f'{self.__class__.__name__}({self.concrete!r})'



@export()
@KindOfProvider.factory._set_default_impl
class FactoryProvider(Provider):

    # _using_kwarg_: t.ClassVar = 'provider'

    def make_resolver(self, token: T_Injectable, scope: T_Scope) -> Resolver[T_Injected]:
        return self.concrete(self, token, scope)        



@export()
@KindOfProvider.resolver._set_default_impl
class ResolverProvider(Provider):

    # _using_kwarg_: t.ClassVar = 'resolver'

    def make_resolver(self, token: T_Injectable, scope: T_Scope) -> Resolver[T_Injected]:
        return self.concrete 



@export()
@KindOfProvider.value._set_default_impl
class ValueProvider(Provider):

    # _using_kwarg_: t.ClassVar = 'value'

    def make_resolver(self, token: T_Injectable, scope: T_Scope) -> Resolver[T_Injected]:
        return ValueResolver(self.concrete)






@export()
@KindOfProvider.alias._set_default_impl
class AliasProvider(Provider):

    __slots__ = '_params',

    def _defaults_(self) -> dict:
        return dict(cache=None)
        
    @property
    def params(self):
        try:
            return self._params
        except AttributeError:
            args = self.get('args')
            kwds = self.get('kwargs')
            self._params = (args or (), kwds or {}) if args or kwds else None
            return self._params

    def implicit_tag(self):
        return NotImplemented

    def make_resolver(self, token: T_Injectable, scope: T_Scope) -> Resolver[T_Injected]:
        params = self.params
        if params is None:
            return AliasResolver(self.concrete, cache=self.cache)
        return AliasWithParamsResolver(self.concrete, cache=self.cache, params=params)



@export()
class CallableProvider(Provider):

    __slots__ = ('_sig', '_params')
    concrete: Callable[..., T]

    def _defaults_(self) -> dict:
        return dict(cache=None)
        
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
            args = self.get('args') or ()
            kwds = self.get('kwargs') or {}
            self._params = self.signature.bind_partial(*args, **kwds) or None
            return self._params

    def check(self):
        super().check()
        assert callable(self.concrete), (
                f'`concrete` must be a valid Callable. Got: {type(self.concrete)}'
            )

    def make_resolver(self, token: T_Injectable, scope: T_Scope) -> Resolver[T_Injected]:
        params = self.params
        if params is None:
            return FuncResolver(self.concrete, cache=self.cache)
        return FuncParamsResolver(self.concrete, cache=self.cache, params=params)





@KindOfProvider.func._set_default_impl
class FunctionProvider(CallableProvider):
    __slots__ = ()

    _using_kwarg_: t.ClassVar = 'func'





@KindOfProvider.type._set_default_impl
class TypeProvider(CallableProvider):
    __slots__ = ()

    _using_kwarg_: t.ClassVar = 'type'
    
    

@KindOfProvider.meta._set_default_impl
class MetaProvider(CallableProvider):
    __slots__ = ()

    _using_kwarg_: t.ClassVar = 'meta'
    
    


# class InjectorProvider(ValueProvider):
#     __slots__ = ()

#     def make_resolver(self, token: T_Injectable, scope: T_Scope) -> Resolver[T_Injected]:
#         return InjectorResolver()


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

    def make_resolver(self, inj) -> T_Injectable:
        # return inj[self._scope][self._deps]
        inj = inj[self._scope]
        return next((inj[d] for d in self._deps), self._default)

    def copy(self, **kwds) -> T_Injectable:
        kwds['scope'] = kwds.get('scope') or self._scope
        kwds['deafult'] = kwds.setdefault('deafult', self._default)
        return self.__class__(self._deps, **kwds)
    __copy__ = copy
    

