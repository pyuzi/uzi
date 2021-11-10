# from __future__ import annotations
from logging import getLogger
import typing as t 
from abc import abstractmethod
from djx.common.abc import Orderable
from djx.common.collections import Arguments, nonedict

from collections.abc import  Callable, Hashable, Sequence
from copy import copy



from djx.common.saferef import SafeReferenceType, saferef, SafeRefSet
from djx.common.utils import export, Void, cached_property, Missing, noop
from .inspect import BoundArguments, ordered_id
from . import abc
from .abc import (
    ScopeAlias, ResolverFunc, T_Injectable, T, T_UsingAlias,
    Scope, T_UsingFactory, T_UsingResolver, T_UsingValue, T_UsingVariant
)

from .common import KindOfProvider, ResolverInfo, InjectorVar


if t.TYPE_CHECKING:
    from . import Scope, InjectableSignature, Injector


logger = getLogger(__name__)







@export()
@abc.Provider.register
class Provider(Orderable, t.Generic[T]):

    # __slots__ = ()

    concrete: T
    arguments: Arguments


    kind: t.Final[KindOfProvider] = None

    # __hidden_attrs__: t.Final[orderedset[str]] = ...

    # _using_kwarg_: t.ClassVar = 'concrete'
    _sig: 'InjectableSignature'

    # _resolvers: fallback_default_dict[str, SafeRefSet]

    __pos: int

    # def __init_subclass__(cls, hidden_attrs=(), **kwds) -> None:
    #     super().__init_subclass__(**kwds)

    #     flip = set(a for a in hidden_attrs if a[0] == '~')
    #     cls.__hidden_attrs__ = hidden_attrs = orderedset(hidden_attrs) ^ flip
        
    #     for attr in dir(cls):
    #         if isinstance(getattr(cls, attr, None), cached_property):
    #             cls.__hidden_attrs__.add(attr)
        
    #     if flip:
    #         cls.__hidden_attrs__ -= (a[1:] for a in flip)

    def __init__(self, concrete: t.Any, /, **kwds) -> None:

        self.concrete = concrete

        self.arguments = Arguments.coerce(kwds.pop('arguments', None))\
            .extend(kwds.pop('args', None) or (), kwds.pop('kwargs', None) or ())

        kwds = dict(self._defaults_() or (), **kwds)
        kwds['priority'] = kwds.get('priority', 1) or 0
        
        self._assing(**kwds)
        self._boot_()
        
    def _defaults_(self) -> dict:
        return

    def _boot_(self):
        self.__pos = ordered_id()

    # @property
    # def resolvers(self):
    #     try:
    #         return self._resolvers
    #     except AttributeError:
    #         self._resolvers = fallback_default_dict(SafeRefSet)
    #         return self._resolvers

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

    def implicit_tag(self):
        if isinstance(self.concrete, Hashable):
            return self.concrete
        return NotImplemented

    def _cleanup_resolve_(self, scope: str, key: SafeReferenceType):
        return self.resolvers.get(scope, nonedict()).pop(key, None) is not None

    @abstractmethod
    def provide(self, scope: 'Scope', token: T_Injectable,  *args, **kwds) -> ResolverInfo:
        ...
    
    def __call__(self, scope: 'Scope', token: T_Injectable,  *args, **kwds) -> ResolverFunc:
        func, deps = ResolverInfo.coerce(self.provide(scope, token, *args, **kwds))
        if func is not None and deps:
            scope.register_dependency(token, *deps)
        return func

    def __order__(self):
        return (self.priority, self.__pos)

    def __repr__(self):
        return f'{self.__class__.__name__}({self.concrete!r})'



@export()
@KindOfProvider.factory._set_default_impl
class FactoryProvider(Provider[T_UsingFactory]):

    __slots__ = ()

    def provide(self, scope: 'Scope', dep: T_Injectable,  *args, **kwds) -> ResolverInfo:
        return ResolverInfo.coerce(self.concrete(self, scope, dep, *args, **kwds))



@export()
@KindOfProvider.resolver._set_default_impl
class ResolverProvider(Provider[T_UsingResolver]):
    __slots__ = ()

    def provide(self, scope: 'Scope', dep: T_Injectable,  *args, **kwds) -> ResolverInfo:
        return ResolverInfo.coerce(self.concrete)



@export()
@KindOfProvider.value._set_default_impl
class ValueProvider(Provider[T_UsingValue]):

    __slots__ = ()

    def provide(self, scope: 'Scope', dep: T_Injectable,  *args, **kwds) -> ResolverInfo:
        value = self.concrete
        return ResolverInfo(lambda at: InjectorVar(at, value))






@export()
@KindOfProvider.alias._set_default_impl
class AliasProvider(Provider[T_UsingAlias]):

    __slots__ = '_params',

    def implicit_tag(self):
        return NotImplemented

    def _defaults_(self) -> dict:
        return dict(cache=None)

    def provide(self, scope: 'Scope', dep: T_Injectable,  *_args, **_kwds) -> ResolverInfo:
        
        arguments = self.arguments or None
        real = self.concrete
        cache = self.cache

        if not (arguments or cache):
            def resolve(at: 'Injector'):
                nonlocal real
                return at.content[real]
        elif arguments:
            args, kwargs = arguments.args, arguments.kwargs
            def resolve(at: 'Injector'):
                if inner := at.content[real]:
                    def make(*a, **kw):
                        nonlocal inner, args, kwargs
                        return inner.make(*args, *a, **dict(kwargs, **kw))

                    return InjectorVar(at, make=make, cache=cache)

        else:
            def resolve(at: 'Injector'):
                nonlocal real, cache
                if inner := at.content[real]:
                    return InjectorVar(at, make=lambda *a, **kw: inner.make(*a, **kw), cache=cache)

        return ResolverInfo(resolve, {real})





@export()
@KindOfProvider.variant._set_default_impl
class VariantProvider(AliasProvider[T_UsingVariant]):

    __slots__ = ()


@export()
class CallableProvider(Provider):

    __slots__ = ('_sig', '_params')
    concrete: Callable[..., T]

    def _defaults_(self) -> dict:
        return dict(cache=None)
        
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

    def provide(self, scope: 'Scope', token: T_Injectable,  *args, **kwds) -> ResolverInfo:

        func = self.concrete
        cache = self.cache

        sig = self.signature
        arguments = self.arguments
        bound = sig.bind_partial(*arguments.args, **arguments.kwargs) or None
        
        if bound is None:
            def resolve(at):
                nonlocal func, cache
                return InjectorVar(at, make=func, cache=cache)
        else:
            def resolve(at):
                nonlocal cache
                def make(*a, **kw):
                    nonlocal at, func, bound
                    return func(*bound.inject_args(at, kw), *a, **bound.inject_kwargs(at, kw))

                return InjectorVar(at, make=make, cache=cache)

        return ResolverInfo(resolve)





@KindOfProvider.func._set_default_impl
class FunctionProvider(CallableProvider):
    __slots__ = ()



@KindOfProvider.type._set_default_impl
class TypeProvider(CallableProvider):
    __slots__ = ()
    


@KindOfProvider.meta._set_default_impl
class MetaProvider(CallableProvider):
    __slots__ = ()


