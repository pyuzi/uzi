# from __future__ import annotations
from collections import ChainMap
from functools import wraps
from logging import getLogger
from operator import le
from types import GenericAlias
import typing as t 
from inspect import Parameter, Signature
from abc import abstractmethod
from dataclasses import KW_ONLY, InitVar, dataclass, field
from laza.common.abc import Orderable
from laza.common.collections import Arguments, frozendict, orderedset

from collections.abc import  Callable as TCallable, Hashable, Mapping, Sequence
from laza.common.typing import get_args, typed_signature


from laza.common.functools import export, Void

from laza.common.enum import IntEnum

from libs.common.laza.common.collections import KwargDict
from libs.common.laza.common.enum import StrEnum
from .util import unique_id


from .common import (
    InjectedLookup, KindOfProvider, InjectorVar,
    Injectable, T_Injected, T_Injectable
)

from .resolvers import Resolver, ResolverFunc


if t.TYPE_CHECKING:
    from . import Scope as TScope, InjectableSignature, Injector, Depends, IocContainer



logger = getLogger(__name__)

_py_dataclass = dataclass
@wraps(dataclass)
def dataclass(cls=None, /, **kw):
    kwds = dict(eq=False, slots=True)
    return _py_dataclass(cls, **(kwds | kw))


_T_Using = t.TypeVar('_T_Using')


T_UsingAlias = Injectable
T_UsingVariant = Injectable
T_UsingValue = T_Injected

T_UsingFunc = TCallable[..., T_Injected]
T_UsingType = type[T_Injected]

T_UsingCallable = t.Union[T_UsingType, T_UsingFunc]


T_UsingResolver = ResolverFunc[T_Injected]

T_UsingFactory = TCallable[['Provider', 'TScope', Injectable], t.Union[ResolverFunc[T_Injected], None]]

T_UsingAny = t.Union[T_UsingCallable, T_UsingFactory, T_UsingResolver, T_UsingAlias, T_UsingValue]



class ScopeName(StrEnum):
    main = 'main'
    local = 'local'
    # module = 'module'



class ProviderCondition(t.Callable[['Provider', 'TScpoe', T_Injectable], bool]):

    __class_getitem__ = classmethod(GenericAlias)

    def __call__(self, provider: 'Provider', scope: 'TScope', key: T_Injectable) -> bool:
        ...




@export()
@dataclass
class Provider(t.Generic[_T_Using]):

    provide: InitVar[Injectable] = None
    provides: Injectable = field(init=False)
    
    using: InitVar[_T_Using] = None
    uses: _T_Using = field(init=False)

    _: KW_ONLY
    scope: str = None 
    shared: bool = None
    """Whether to share the resolved instance.
    """
    when: tuple[ProviderCondition] = ()


    # def __init_subclass__(cls, **kwds) -> None:
    #     return dataclass(cls, )
    #     return super().__init_subclass__()

    def __post_init__(self, provide=None, using=None):
        if not hasattr(self, 'provides'):
            self._set_provides(provide)    
        if not hasattr(self, 'uses'):
            self._set_uses(using)        
    
    def _set_provides(self, provide):
        self.provides = provide
    
    def _set_uses(self, using):
        self.uses = self.provides if using is None else using
    
    def implicit_tag(self):
        if isinstance(self.uses, Hashable):
            return self.uses
        return NotImplemented

    @abstractmethod
    def _provide(self, scope: 'TScope', token: T_Injectable,  *args, **kwds) -> Resolver:
        ...
    
    def can_provide(self, scope: 'TScope', dep: T_Injectable) -> bool:
        if func := getattr(self.uses, '__can_provide__', None):
            return bool(func(self, scope, dep))
        return True

    def __call__(self, scope: 'TScope', token: T_Injectable,  *args, **kwds) -> ResolverFunc:
        func, deps = Resolver.coerce(self._provide(scope, token, *args, **kwds))
        if func is not None and deps:
            scope.register_dependency(token, *deps)
        return func




@export()
@dataclass
class Factory(Provider[T_UsingFactory]):

    def _provide(self, scope: 'TScope', dep: T_Injectable) -> Resolver:
        return Resolver.coerce(self.uses(self, scope, dep))





@export()
@dataclass
class Object(Provider[T_UsingValue]):

    shared: t.ClassVar = True

    def _provide(self, scope: 'TScope', dep: T_Injectable,  *args, **kwds) -> Resolver:
        value = self.uses
        return Resolver(dep, self, lambda at: InjectorVar(at, value))

    def can_provide(self, scope: 'TScope', dep: T_Injectable) -> bool:
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
@dataclass
class Callable(Provider[_T_Using]):

    EMPTY: t.ClassVar = _EMPTY
    _argument_view_cls: t.ClassVar = ArgumentView

    _: KW_ONLY
    args: InitVar[tuple] = None
    kwargs: InitVar[KwargDict] = None
    arguments: Arguments = field(init=False)

    deps: dict[str, Injectable] = field(default_factory=frozendict)

    def __post_init__(self, args=None, kwargs=None, **kwds):
        super().__post_init__(**kwds)
        self.arguments = Arguments(args, kwargs)

    # def check(self):
    #     super().check()
    #     assert callable(self.uses), (
    #             f'`concrete` must be a valid Callable. Got: {type(self.uses)}'5
    #         )

    def get_signature(self, scope: 'TScope', token: T_Injectable) -> t.Union[Signature, None]:
        return typed_signature(self.uses)

    def get_available_deps(self, sig: Signature, scope: 'TScope', deps: Mapping):
        return { n: d for n, d in deps.items() if scope.is_provided(d) }

    def get_explicit_deps(self, sig: Signature, scope: 'TScope'):
        ioc = scope.ioc
        return  { n: d for n, d in self.deps.items() if ioc.is_injectable(d) }

    def get_implicit_deps(self, sig: Signature, scope: 'TScope'):
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

    def _provide(self, scope: 'TScope', token: T_Injectable,  *args, **kwds) -> Resolver:

        func = self.uses
        shared = self.shared

        sig = self.get_signature(scope, token)

        arguments = self.arguments.merge(*args, **kwds)

        bound = sig.bind_partial(*arguments.args, **arguments.kwargs) or None
        
        if not sig.parameters:
        
            def resolve(at):
                nonlocal func, shared
                return InjectorVar(at, make=func, shared=shared)

            return Resolver(resolve)

        defaults = frozendict(bound.arguments)

        
        expl_deps = self.get_explicit_deps(sig, scope)
        impl_deps = self.get_implicit_deps(sig, scope)

        all_deps = dict(impl_deps, **expl_deps)
        deps = self.get_available_deps(sig, scope, all_deps)
        argv = self.create_arguments_view(sig, defaults, deps)
        
        def resolve(at: 'Injector'):
            nonlocal shared
            def make(inj, *a, **kw):
                nonlocal func, argv, at
                return func(*argv.args(at, kw), *a, **argv.kwds(at, kw))

            return make

            return InjectorVar(at, make=make, shared=shared)

        return Resolver(factory=resolve, deps=set(all_deps.values()))




@export()
@dataclass
class Function(Callable[TCallable[..., _T_Using]]):
    ...





@export()
@dataclass
class Type(Callable[type[_T_Using]]):
    ...



@export()
@dataclass
class Alias(Provider[T_UsingAlias]):

    shared: t.ClassVar = None

    def implicit_tag(self):
        return NotImplemented

    def can_provide(self, scope: 'TScope', token: Injectable) -> bool:
        return scope.is_provided(self.uses)

    def _provide(self, scope: 'TScope', dep: T_Injectable,  *_args, **_kwds) -> Resolver:
        
        arguments = self.arguments or None
        real = self.uses
        shared = self.shared

        if not (arguments or shared):
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

                    return InjectorVar(at, make=make, shared=shared)
        else:
            def resolve(at: 'Injector'):
                nonlocal real, shared
                if inner := at.vars[real]:

                    return InjectorVar(at, make=lambda *a, **kw: inner.make(*a, **kw), shared=shared)

        return Resolver(resolve, {real})




@export()
@dataclass
class Union(Alias):

    using: InitVar[_T_Using] = None

    _implicit_types_ = frozenset([type(None)]) 

    def get_all_args(self, scope: 'TScope', token: Injectable):
        return get_args(token)

    def get_injectable_args(self, scope: 'TScope', token: Injectable, *, include_implicit=True) -> tuple[Injectable]:
        implicits = self._implicit_types_ if include_implicit else set()
        return tuple(a for a in self.get_all_args(scope, token) if a in implicits or scope.is_provided(a))
    
    def can_provide(self, scope: 'TScope', token: Injectable) -> bool:
        return len(self.get_injectable_args(scope, token, include_implicit=False)) > 0

    def _provide(self, scope: 'TScope', token):
        
        args = self.get_injectable_args(scope, token)

        def resolve(at: 'Injector'):
            nonlocal args
            return next((v for a in args if (v := at.vars[a])), None)

        return Resolver(resolve, {*args})




@export()
@dataclass
class Annotation(Union):

    _implicit_types_ = frozenset() 

    def get_all_args(self, scope: 'TScope', token: Injectable):
        return token.__metadata__[::-1]



@export()
@dataclass
class Dependency(Alias):

    def can_provide(self, scope: 'TScope', token: 'Depends') -> bool:
        if token.on is ...:
            return False
        return scope.is_provided(token.on, start=token.at)

    def _provide(self, scope: 'TScope', token: 'Depends') -> Resolver:

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

        return Resolver(resolve, {dep})





@export()
@dataclass
class Lookup(Alias):

    def can_provide(self, scope: 'TScope', token: 'InjectedLookup') -> bool:
        return scope.is_provided(token.depends)

    def _provide(self, scope: 'TScope', token: 'InjectedLookup',  *_args, **_kwds) -> Resolver:

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

        return Resolver(resolve, {dep})

