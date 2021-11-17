# from __future__ import annotations
from logging import getLogger
from operator import le
from types import GenericAlias
import typing as t 
from abc import abstractmethod
from djx.common.abc import Orderable
from djx.common.collections import Arguments

from collections.abc import  Callable, Hashable
from djx.common.typing import NoneType, get_args, get_origin



from djx.common.utils import export
from .inspect import ordered_id


from .common import (
    KindOfProvider, ResolverInfo, InjectorVar, ResolverFunc,
    Injectable, T_Injected, T_Injectable
)


if t.TYPE_CHECKING:
    from . import Scope, InjectableSignature, Injector, Depends


logger = getLogger(__name__)



_T_Using = t.TypeVar('_T_Using')


T_UsingAlias = Injectable
T_UsingVariant = Injectable
T_UsingValue = T_Injected

T_UsingFunc = Callable[..., T_Injected]
T_UsingType = type[T_Injected]

T_UsingCallable = t.Union[T_UsingType, T_UsingFunc]

T_UsingFactory = Callable[['Provider', 'Scope', Injectable], t.Union[ResolverFunc[T_Injected], None]]

T_UsingResolver = ResolverFunc[T_Injected]

T_UsingAny = t.Union[T_UsingCallable, T_UsingFactory, T_UsingResolver, T_UsingAlias, T_UsingValue]





@export()
class Provider(Orderable, t.Generic[_T_Using]):

    # __slots__ = ()

    concrete: _T_Using
    arguments: Arguments


    kind: t.Final[KindOfProvider] = None

    _sig: 'InjectableSignature'

    __pos: int

    def __init__(self, concrete: t.Any=..., /, **kwds) -> None:

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

    @property
    def factory(self):
        if callable(res := getattr(self.concrete, '__inject_new__', self.concrete)):
            return res

    @property
    def signature(self):
        try:
            return self._sig
        except AttributeError:
            from .inspect import signature
            if func := self.factory:
                self._sig = signature(func, evaltypes=True)
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

    # def clone(self):
    #     return copy(self)
        
    # def replace(self, **kwds):
    #     return self.clone()._assing(**kwds)

    def implicit_tag(self):
        if isinstance(self.concrete, Hashable):
            return self.concrete
        return NotImplemented

    @abstractmethod
    def provide(self, scope: 'Scope', token: T_Injectable,  *args, **kwds) -> ResolverInfo:
        ...
    
    def can_provide(self, scope: 'Scope', dep: T_Injectable) -> bool:
        if func := getattr(self.concrete, '__can_provide__', None):
            return bool(func(self, scope, dep))
        return True

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

    def can_provide(self, scope: 'Scope', dep: T_Injectable) -> bool:
        return True





@export()
class CallableProvider(Provider):

    __slots__ = ('_sig', '_params')
    concrete: Callable[..., _T_Using]

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

        func = self.factory
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




@export()
@KindOfProvider.alias._set_default_impl
class AliasProvider(Provider[T_UsingAlias]):

    __slots__ = ()

    def implicit_tag(self):
        return NotImplemented

    def _defaults_(self) -> dict:
        return dict(cache=None)
    
    def can_provide(self, scope: 'Scope', token: Injectable) -> bool:
        return scope.is_provided(self.concrete)

    def provide(self, scope: 'Scope', dep: T_Injectable,  *_args, **_kwds) -> ResolverInfo:
        
        arguments = self.arguments or None
        real = self.concrete
        cache = self.cache

        if not (arguments or cache):
            def resolve(at: 'Injector'):
                nonlocal real
                return at.vars[real]
        elif arguments:
            args, kwargs = arguments.args, arguments.kwargs
            def resolve(at: 'Injector'):
                if inner := at.vars[real]:
                    def make(*a, **kw):
                        nonlocal inner, args, kwargs
                        return inner.make(*args, *a, **dict(kwargs, **kw))

                    return InjectorVar(at, make=make, cache=cache)

        else:
            def resolve(at: 'Injector'):
                nonlocal real, cache
                if inner := at.vars[real]:
                    return InjectorVar(at, make=lambda *a, **kw: inner.make(*a, **kw), cache=cache)

        return ResolverInfo(resolve, {real})






@export()
class UnionProvider(AliasProvider):

    __slots__ = ()

    _implicit_types_ = frozenset([type(None)]) 

    def get_all_args(self, scope: 'Scope', token: Injectable):
        return get_args(token)

    def get_injectable_args(self, scope: 'Scope', token: Injectable, *, include_implicit=True) -> tuple[Injectable]:
        implicits = self._implicit_types_ if include_implicit else set()
        return tuple(a for a in self.get_all_args(scope, token) if a in implicits or scope.is_provided(a))
    
    def can_provide(self, scope: 'Scope', token: Injectable) -> bool:
        return len(self.get_injectable_args(scope, token, include_implicit=False)) > 0

    def provide(self, scope: 'Scope', token):
        
        args = self.get_injectable_args(scope, token)

        def resolve(at: 'Injector'):
            nonlocal args
            return next((v for a in args if (v := at.vars[a])), None)

        return ResolverInfo(resolve, {*args})



@export()
class AnnotationProvider(UnionProvider):

    __slots__ = ()
    _implicit_types_ = frozenset() 

    def get_all_args(self, scope: 'Scope', token: Injectable):
        return token.__metadata__[::-1]



@export()
class DependsProvider(AliasProvider):

    __slots__ = ()

    def can_provide(self, scope: 'Scope', token: 'Depends') -> bool:
        if token.on is ...:
            return False
        return scope.is_provided(token.on, start=token.at)

    def provide(self, scope: 'Scope', token: 'Depends',  *_args, **_kwds) -> ResolverInfo:

        real = token.on
        arguments = self.arguments or None

        if at := None if token.at is ... else token.at:
            at = scope.ioc.scopekey(at)

            def resolve(inj: 'Injector'):
                nonlocal real, at
                return inj[at].vars[real]
        
        else:
            def resolve(inj: 'Injector'):
                nonlocal real
                return inj.vars[real]

        return ResolverInfo(resolve, {real})



