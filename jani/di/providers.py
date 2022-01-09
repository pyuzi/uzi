# from __future__ import annotations
from collections import ChainMap
from logging import getLogger
from operator import le
import typing as t 
from inspect import Parameter, Signature
from abc import abstractmethod
from jani.common.abc import Orderable
from jani.common.collections import Arguments, frozendict, orderedset

from collections.abc import  Callable, Hashable, Mapping, Sequence
from jani.common.typing import get_args, typed_signature



from jani.common.utils import export
from jani.common.utils.void import Void
from .util import unique_id


from .common import (
    InjectedLookup, KindOfProvider, ResolverInfo, InjectorVar, ResolverFunc,
    Injectable, T_Injected, T_Injectable
)


if t.TYPE_CHECKING:
    from . import Scope, InjectableSignature, Injector, Depends, IocContainer


logger = getLogger(__name__)



_T_Using = t.TypeVar('_T_Using')


T_UsingAlias = Injectable
T_UsingVariant = Injectable
T_UsingValue = T_Injected

T_UsingFunc = Callable[..., T_Injected]
T_UsingType = type[T_Injected]

T_UsingCallable = t.Union[T_UsingType, T_UsingFunc]


T_UsingResolver = ResolverFunc[T_Injected]

T_UsingFactory = Callable[['Provider', 'Scope', Injectable], t.Union[ResolverFunc[T_Injected], None]]

T_UsingAny = t.Union[T_UsingCallable, T_UsingFactory, T_UsingResolver, T_UsingAlias, T_UsingValue]





@export()
class Provider(Orderable, t.Generic[_T_Using]):

    # __slots__ = ('target', 'arguments', '')

    ioc: 'IocContainer' = None

    target: _T_Using
    arguments: Arguments

    deps: dict[str, Injectable]


    kind: t.Final[KindOfProvider] = None

    _sig: 'InjectableSignature'

    __pos: int

    def __init__(self, concrete: t.Any=..., /, **kwds) -> None:

        self.target = concrete

        self.arguments = Arguments.coerce(kwds.pop('arguments', None))\
            .extend(kwds.pop('args', None) or (), kwds.pop('kwargs', None) or ())

        kwds = dict(self._defaults_() or (), **kwds)
        kwds['priority'] = kwds.get('priority', 1) or 0
        
        self._assing(**kwds)
        self._boot_()
        
    def _defaults_(self) -> dict:
        return dict(deps=frozendict())

    def _boot_(self):
        self.__pos = unique_id()

    @property
    def factory(self):
        if callable(res := getattr(self.target, '__inject_new__', self.target)):
            return res

    # @property
    # def signature(self) -> Signature:
    #     try:
    #         return self._sig
    #     except AttributeError:
    #         from .inspect import signature
    #         if func := self.factory:

    #             self._sig = signature(func, evaltypes=True)
    #         else:
    #             self._sig = None
    #         return self._sig

    @property
    def signature(self) -> t.Union[Signature, None]:
        if func := self.factory:
            return typed_signature(func)

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
        if isinstance(self.target, Hashable):
            return self.target
        return NotImplemented

    @abstractmethod
    def provide(self, scope: 'Scope', token: T_Injectable,  *args, **kwds) -> ResolverInfo:
        ...
    
    def can_provide(self, scope: 'Scope', dep: T_Injectable) -> bool:
        if func := getattr(self.target, '__can_provide__', None):
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
        return f'{self.__class__.__name__}({self.target!r})'



@export()
@KindOfProvider.factory._set_default_impl
class FactoryProvider(Provider[T_UsingFactory]):

    __slots__ = ()

    def provide(self, scope: 'Scope', dep: T_Injectable,  *args, **kwds) -> ResolverInfo:
        return ResolverInfo.coerce(self.target(self, scope, dep, *args, **kwds))



@export()
@KindOfProvider.resolver._set_default_impl
class ResolverProvider(Provider[T_UsingResolver]):
    __slots__ = ()

    def provide(self, scope: 'Scope', dep: T_Injectable,  *args, **kwds) -> ResolverInfo:
        return ResolverInfo.coerce(self.target)



@export()
@KindOfProvider.value._set_default_impl
class ValueProvider(Provider[T_UsingValue]):

    __slots__ = ()

    def provide(self, scope: 'Scope', dep: T_Injectable,  *args, **kwds) -> ResolverInfo:
        value = self.target
        return ResolverInfo(lambda at: InjectorVar(at, value))

    def can_provide(self, scope: 'Scope', dep: T_Injectable) -> bool:
        return True




class InjectedArgumentsDict(dict[str, t.Any]):
    
    __slots__ = 'inj',

    inj: 'Injector'

    def __init__(self, inj: 'Injector', /, deps=()):
        dict.__init__(self, deps)
        self.inj = inj

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, key: str):
        return self.inj[super().__getitem__(key)]


_EMPTY = Parameter.empty

_T_Empty = t.Literal[_EMPTY] # type: ignore

_T_ArgViewTuple = tuple[str, t.Any, t.Union[Injectable, _T_Empty], t.Any]
class ArgumentView:

    __slots__ = '_args', '_kwargs', '_kwds', '_var_arg', '_var_kwd', '_non_kwds',

    _args: tuple[_T_ArgViewTuple, ...]
    _kwargs: tuple[_T_ArgViewTuple, ...]
    _kwds: tuple[_T_ArgViewTuple, ...]
    _var_arg: t.Union[_T_ArgViewTuple, None]
    _var_kwd: t.Union[_T_ArgViewTuple, None]

    def __new__(cls, args=(), kwargs=(), kwds=(), var_arg=None, var_kwd=None):
        self = object.__new__(cls)
        self._args = tuple(args)
        self._kwargs = tuple(kwargs)
        self._kwds = tuple(kwds)
        self._var_arg = var_arg
        self._var_kwd = var_kwd
        if var_kwd:
            self._non_kwds = frozenset(a for a, *_ in kwargs),
        else:
            self._non_kwds = frozenset()

        return self

    def args(self, inj: 'Injector', vals: dict[str, t.Any]=frozendict()):
        for n, v, i, d in self._args:
            if v is not _EMPTY:
                yield v
                continue
            elif i is not _EMPTY:
                if d is _EMPTY:
                    yield inj[i]
                else:
                    yield inj.get(i, d)
                continue
            elif d is not _EMPTY:
                yield d
                continue
            return
        
        if _var := self._var_arg:
            n, v, i = _var
            if v is not _EMPTY:
                yield from v
            elif i is not _EMPTY:
                yield from inj.get(i, ())
        else:
        # elif  self._kwargs:
            # yield from self.kwargs(inj, vals)
            for n, v, i, d in self._kwargs:
                v = vals.pop(n, v)
                if v is not _EMPTY:
                    yield v
                    continue
                elif i is not _EMPTY:
                    if d is _EMPTY:
                        yield inj[i]
                    else:
                        yield inj.get(i, d)
                    continue
                elif d is not _EMPTY:
                    yield d
                    continue
                break

    def var_arg(self, inj: 'Injector', vals: Mapping[str, t.Any]=frozendict()):
        if _var := self._var_arg:
            n, v, i = _var
            if v is not _EMPTY:
                yield from v
            elif i is not _EMPTY:
                yield from inj.get(i, ())

    def kwargs(self, inj: 'Injector', vals: dict[str, t.Any]=frozendict()):
        if vals:
            for n, v, i, d in self._kwargs:
                v = vals.pop(n, v)
                if v is not _EMPTY:
                    yield v
                    continue
                elif i is not _EMPTY:
                    if d is _EMPTY:
                        yield inj[i]
                    else:
                        yield inj.get(i, d)
                    continue
                elif d is not _EMPTY:
                    yield d
                    continue
                break
        else:
            for n, v, i, d in self._kwargs:
                if v is not _EMPTY:
                    yield v
                    continue
                elif i is not _EMPTY:
                    if d is _EMPTY:
                        yield inj[i]
                    else:
                        yield inj.get(i, d)
                    continue
                elif d is not _EMPTY:
                    yield d
                    continue
                break

    def kwds(self, inj: 'Injector', vals: dict[str, t.Any]=frozendict()):
        kwds = dict()
        if vals:
            for n, v, i, d in self._kwds:
                v = vals.pop(n, v)
                if v is not _EMPTY:
                    kwds[n] = v
                    continue
                elif i is not _EMPTY:
                    if d is _EMPTY:
                        kwds[n] = inj[i]
                    else:
                        kwds[n] = inj.get(i, d)
                    continue
                elif d is not _EMPTY:
                    kwds[n] = v
                    continue
                break
        else:
            for n, v, i, d in self._kwds:
                if v is not _EMPTY:
                    kwds[n] = v
                    continue
                elif i is not _EMPTY:
                    if d is _EMPTY:
                        kwds[n] = inj[i]
                    else:
                        kwds[n] = inj.get(i, d)
                    continue
                elif d is not _EMPTY:
                    kwds[n] = v
                    continue
                break

        if _var := self._var_kwd:
            n, v, i = _var
            if v is not _EMPTY:
                kwds.update(v)
            elif i is not _EMPTY:
                kwds.update(inj.get(i, ()))

        vals and kwds.update(vals)
        return kwds

    def var_kwd(self, inj: 'Injector', vals: Mapping[str, t.Any]=frozendict()):
        kwds = dict()
        if _var := self._var_kwd:
            n, v, i = _var
            if v is not _EMPTY:
                kwds.update(v)
            elif i is not _EMPTY:
                kwds.update(inj.get(i, ()))

        vals and kwds.update(vals)
        return kwds



@export()
class CallableProvider(Provider):

    # __slots__ = ('_sig', '_params')
    target: Callable[..., _T_Using]

    EMPTY = _EMPTY

    _argument_view_cls = ArgumentView

    def _defaults_(self) -> dict:
        return dict(cache=None, deps=frozendict())
        
    def check(self):
        super().check()
        assert callable(self.target), (
                f'`concrete` must be a valid Callable. Got: {type(self.target)}'
            )

    def get_available_deps(self, sig: Signature, scope: 'Scope', deps: Mapping):
        return { n: d for n, d in deps.items() if scope.is_provided(d) }

    def get_explicit_deps(self, sig: Signature, scope: 'Scope'):
        ioc = scope.ioc
        return  { n: d for n, d in self.deps.items() if ioc.is_injectable(d) }

    def get_implicit_deps(self, sig: Signature, scope: 'Scope'):
        ioc = scope.ioc
        return  { n: p.annotation
            for n, p in sig.parameters.items() 
                if  p.annotation is not _EMPTY and ioc.is_injectable(p.annotation)
        }

    def eval_arg_params(self, sig: Signature, defaults: Mapping[str, t.Any], deps: Mapping[str, Injectable]):
        return [ 
            (p.name, defaults.get(p.name, self.EMPTY), deps.get(p.name, self.EMPTY), p.default) 
                for p in self.iter_arg_params(sig)
        ]

    def iter_arg_params(self, sig: Signature):
        for p in sig.parameters.values():
            if p.kind is Parameter.POSITIONAL_ONLY:
                yield p

    def eval_kwarg_params(self, sig: Signature, defaults: Mapping[str, t.Any], deps: Mapping[str, Injectable]):
        return [ 
            (p.name, defaults.get(p.name, self.EMPTY), deps.get(p.name, self.EMPTY), p.default) 
                for p in self.iter_kwarg_params(sig)
        ]

    def iter_kwarg_params(self, sig: Signature):
        for p in sig.parameters.values():
            if p.kind is Parameter.POSITIONAL_OR_KEYWORD:
                yield p

    def eval_var_arg_param(self, sig: Signature, defaults: Mapping[str, t.Any], deps: Mapping[str, Injectable]):
        if p := self.get_var_arg_param(sig):
            return p.name, defaults.get(p.name, self.EMPTY), deps.get(p.name, self.EMPTY)

    def get_var_arg_param(self, sig: Signature):
        return next((p for p in sig.parameters.values() if p.kind is Parameter.VAR_POSITIONAL), None)

    def eval_kwd_params(self, sig: Signature, defaults: Mapping[str, t.Any], deps: Mapping[str, Injectable]):
        return [ 
            *(
                (p.name, defaults.get(p.name, self.EMPTY), deps.get(p.name, self.EMPTY), p.default) 
                for p in self.iter_kwd_params(sig)
            ),
            *( 
                (extra := (orderedset(defaults.keys()) | deps.keys()) - sig.parameters.keys()) 
                    and (
                        (n, defaults.get(n, self.EMPTY), deps.get(n, self.EMPTY), self.EMPTY) 
                        for n in extra
                     ) 
            )
        ] 

    def iter_kwd_params(self, sig: Signature):
        for p in sig.parameters.values():
            if p.kind is Parameter.KEYWORD_ONLY:
                yield p

    def eval_var_kwd_param(self, sig: Signature, defaults: Mapping[str, t.Any], deps: Mapping[str, Injectable]):
        if p := self.get_var_kwd_param(sig):
            return p.name, defaults.get(p.name, self.EMPTY), deps.get(p.name, self.EMPTY)

    def get_var_kwd_param(self, sig: Signature):
        return next((p for p in sig.parameters.values() if p.kind is Parameter.VAR_KEYWORD), None)

    def create_arguments_view(self, sig: Signature, defaults: Mapping[str, t.Any], deps: Mapping[str, Injectable]):
        return ArgumentView(
            self.eval_arg_params(sig, defaults, deps),
            self.eval_kwarg_params(sig, defaults, deps),
            self.eval_kwd_params(sig, defaults, deps),
            self.eval_var_arg_param(sig, defaults, deps),
            self.eval_var_kwd_param(sig, defaults, deps)
        )

    def provide(self, scope: 'Scope', token: T_Injectable,  *args, **kwds) -> ResolverInfo:

        func = self.factory
        cache = self.cache

        sig = self.signature
        arguments = self.arguments

        bound = sig.bind_partial(*arguments.args, **arguments.kwargs) or None
        
        if not sig.parameters:
        
            def resolve(at):
                nonlocal func, cache
                return InjectorVar(at, make=func, cache=cache)

            return ResolverInfo(resolve)

        defaults = frozendict(bound.arguments)

        
        expl_deps = self.get_explicit_deps(sig, scope)
        impl_deps = self.get_implicit_deps(sig, scope)

        all_deps = dict(impl_deps, **expl_deps)
        deps = self.get_available_deps(sig, scope, all_deps)
        argv = self.create_arguments_view(sig, defaults, deps)
        
        def resolve(at: 'Injector'):
            nonlocal cache
            def make(*a, **kw):
                nonlocal func, argv, at
                return func(*argv.args(at, kw), *a, **argv.kwds(at, kw))

            return InjectorVar(at, make=make, cache=cache)

        return ResolverInfo(resolve, set(all_deps.values()))


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
        return scope.is_provided(self.target)

    def provide(self, scope: 'Scope', dep: T_Injectable,  *_args, **_kwds) -> ResolverInfo:
        
        arguments = self.arguments or None
        real = self.target
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

        dep = token.on
        at = None if token.at is ... or token.at else token.at
        arguments = token.arguments or None

        if at in scope.aliases:
            at = None

        # if at and arguments:
        

        if at is None is arguments:
            def resolve(at: 'Injector'):
                nonlocal dep
                return at.vars[dep]
        elif arguments is None:
            at = scope.ioc.scopekey(at)
            def resolve(inj: 'Injector'):
                nonlocal dep, at
                return inj[at].vars[dep]
        elif at is None:
            args, kwargs = arguments.args, arguments.kwargs
            def resolve(inj: 'Injector'):
                nonlocal dep
                if inner := inj.vars[dep]:
                    def make(*a, **kw):
                        nonlocal inner, args, kwargs
                        return inner.make(*args, *a, **dict(kwargs, **kw))

                    return InjectorVar(inj, make=make)
        else:
            at = scope.ioc.scopekey(at)
            args, kwargs = arguments.args, arguments.kwargs
            def resolve(inj: 'Injector'):
                nonlocal at, dep
                inj = inj[at]
                if inner := inj.vars[dep]:
                    def make(*a, **kw):
                        nonlocal inner, args, kwargs
                        return inner.make(*args, *a, **dict(kwargs, **kw))

                    return InjectorVar(inj, make=make)

        return ResolverInfo(resolve, {dep})






@export()
class LookupProvider(AliasProvider):

    __slots__ = ()

    def can_provide(self, scope: 'Scope', token: 'InjectedLookup') -> bool:
        return scope.is_provided(token.depends)

    def provide(self, scope: 'Scope', token: 'InjectedLookup',  *_args, **_kwds) -> ResolverInfo:

        dep = token.depends
        path = token.path

        def resolve(at: 'Injector'):
            nonlocal dep, path
            if var := at.vars[dep]:
                if var.value is Void:
                    return InjectorVar(at, make=lambda: path.get(var.get()))

                # px = proxy(lambda: path.get(var.get()))
                return InjectorVar(at, make=lambda: path.get(var.value))
            return 

        return ResolverInfo(resolve, {dep})



