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
from djx.common.typing import GenericLike, get_all_type_hints, get_origin
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
    
    

