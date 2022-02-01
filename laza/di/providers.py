# from __future__ import annotations
from functools import wraps
from logging import getLogger
from types import GenericAlias
import typing as t 
from inspect import Parameter, Signature
from abc import abstractmethod
from dataclasses import InitVar, dataclass, field
from laza.common.collections import Arguments, frozendict, orderedset

from collections.abc import  Callable as TCallable, Hashable, Mapping
from laza.common.typing import get_args, typed_signature


from laza.common.functools import export, Void


from laza.common.collections import KwargDict


from .common import (
    InjectedLookup, InjectorVar,
    Injectable, Depends,
    T_Injected, T_Injectable, 
    ResolverInfo, ResolverFunc
)



if t.TYPE_CHECKING:
    from .scopes import AbcScope
    from .injectors import Injector




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

T_UsingFactory = TCallable[..., t.Union[ResolverFunc[T_Injected], None]]

T_UsingAny = t.Union[T_UsingCallable, T_UsingFactory, T_UsingResolver, T_UsingAlias, T_UsingValue]



class ProviderCondition(t.Callable[..., bool]):

    __class_getitem__ = classmethod(GenericAlias)

    def __call__(self, provider: 'Provider', scope: 'AbcScope', key: T_Injectable) -> bool:
        ...




@export()
@dataclass
class Provider(t.Generic[_T_Using]):

    # provide: InitVar[Injectable] = None
    # provides: Injectable = field(init=False)
    
    use: InitVar[_T_Using] = None
    uses: _T_Using = field(init=False)

    shared: bool = None


    """Whether to share the resolved instance.
    """
    when: tuple[ProviderCondition] = ()

    def __post_init__(self, use=None):
        self._setup()   
        if not hasattr(self, 'uses'):
            self._set_uses(use)     
    
    def _set_uses(self, using):
        self.uses = using
    
    def _setup(self):
        ...
    
    def implicit_token(self):
        return NotImplemented

    @abstractmethod
    def _provide(self, scope: 'AbcScope', token: T_Injectable,  *args, **kwds) -> ResolverInfo:
        ...
    
    def can_provide(self, scope: 'AbcScope', dep: T_Injectable) -> bool:
        # if func := getattr(self.uses, '__can_provide__', None):
        #     return bool(func(self, scope, dep))
        return True

    # def __call__(self, scope: 'AbcScope', token: T_Injectable,  *args, **kwds) -> ResolverFunc:
    #     func, deps = ResolverInfo.coerce(self._provide(scope, token, *args, **kwds))
    #     if func is not None and deps:
    #         scope.register_dependency(token, *deps)
    #     return func




@export()
@dataclass
class FactoryProvider(Provider[T_UsingFactory]):

    def _provide(self, scope: 'AbcScope', dep: T_Injectable) -> ResolverInfo:
        return ResolverInfo.coerce(self.uses(self, scope, dep))
    




@export()
@dataclass
class ValueProvider(Provider[T_UsingValue]):

    shared: t.ClassVar = True

    def _provide(self, scope: 'AbcScope', dep: T_Injectable,  *args, **kwds) -> ResolverInfo:
        var = InjectorVar(self.uses)
        return ResolverInfo(lambda at: var)

    def can_provide(self, scope: 'AbcScope', dep: T_Injectable) -> bool:
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
class CallableProvider(Provider[_T_Using]):

    EMPTY: t.ClassVar = _EMPTY
    _argument_view_cls: t.ClassVar = ArgumentView

    arguments: Arguments = None

    deps: dict[str, Injectable] = field(default_factory=frozendict)

    def _setup(self):
        self.arguments = Arguments.coerce(self.arguments)

    def get_signature(self, scope: 'AbcScope', token: T_Injectable) -> t.Union[Signature, None]:
        return typed_signature(self.uses)

    def get_available_deps(self, sig: Signature, scope: 'AbcScope', deps: Mapping):
        return { n: d for n, d in deps.items() if scope.is_provided(d) }

    def get_explicit_deps(self, sig: Signature, scope: 'AbcScope'):
        return  { n: d for n, d in self.deps.items() if isinstance(d, Injectable) }

    def get_implicit_deps(self, sig: Signature, scope: 'AbcScope'):
        return  { n: p.annotation
            for n, p in sig.parameters.items() 
                if  p.annotation is not _EMPTY and isinstance(p.annotation, Injectable)
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

    def _provide(self, scope: 'AbcScope', token: T_Injectable,  *args, **kwds) -> ResolverInfo:

        func = self.uses
        shared = self.shared

        sig = self.get_signature(scope, token)

        arguments = self.arguments.merge(*args, **kwds)

        bound = sig.bind_partial(*arguments.args, **arguments.kwargs) or None
        
        if not sig.parameters:
        
            def resolve(at):
                nonlocal func, shared
                return InjectorVar(make=func, shared=shared)

            return ResolverInfo(resolve)

        defaults = frozendict(bound.arguments)
        
        expl_deps = self.get_explicit_deps(sig, scope)
        impl_deps = self.get_implicit_deps(sig, scope)

        all_deps = dict(impl_deps, **expl_deps)
        deps = self.get_available_deps(sig, scope, all_deps)
        argv = self.create_arguments_view(sig, defaults, deps)
        
        def resolve(inj: 'Injector'):
            nonlocal shared
            def make(*a, **kw):
                nonlocal func, argv, inj
                return func(*argv.args(inj, kw), *a, **argv.kwds(inj, kw))
            return InjectorVar(make=make, shared=shared)

        return ResolverInfo(resolve, set(all_deps.values()))




@export()
@dataclass
class FunctionProvider(CallableProvider[TCallable[..., _T_Using]]):
    

    def implicit_token(self):
        return self.uses






@export()
@dataclass
class TypeProvider(CallableProvider[type[_T_Using]]):

    def implicit_token(self):
        return self.uses





@export()
@dataclass
class AliasProvider(Provider[T_UsingAlias]):

    shared: t.ClassVar = None

    def can_provide(self, scope: 'AbcScope', token: Injectable) -> bool:
        return scope.is_provided(self.uses)

    def _provide(self, scope: 'AbcScope', dep: T_Injectable,  *_args, **_kwds) -> ResolverInfo:
        
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

                    return InjectorVar(make=make, shared=shared)
        else:
            def resolve(at: 'Injector'):
                nonlocal real, shared
                if inner := at.vars[real]:
                    return InjectorVar(make=lambda *a, **kw: inner.make(*a, **kw), shared=shared)

        return ResolverInfo(resolve, {real})




@export()
@dataclass
class UnionProvider(AliasProvider):

    using: InitVar[_T_Using] = None

    _implicit_types_ = frozenset([type(None)]) 

    def get_all_args(self, scope: 'AbcScope', token: Injectable):
        return get_args(token)

    def get_injectable_args(self, scope: 'AbcScope', token: Injectable, *, include_implicit=True) -> tuple[Injectable]:
        implicits = self._implicit_types_ if include_implicit else set()
        return tuple(a for a in self.get_all_args(scope, token) if a in implicits or scope.is_provided(a))
    
    def can_provide(self, scope: 'AbcScope', token: Injectable) -> bool:
        return len(self.get_injectable_args(scope, token, include_implicit=False)) > 0

    def _provide(self, scope: 'AbcScope', token):
        
        args = self.get_injectable_args(scope, token)

        def resolve(at: 'Injector'):
            nonlocal args
            return next((v for a in args if (v := at.vars[a])), None)

        return ResolverInfo(resolve, {*args})




@export()
@dataclass
class AnnotationProvider(UnionProvider):

    _implicit_types_ = frozenset() 

    def get_all_args(self, scope: 'AbcScope', token: Injectable):
        return token.__metadata__[::-1]



@export()
@dataclass
class DependencyProvider(AliasProvider):

    def can_provide(self, scope: 'AbcScope', token: 'Depends') -> bool:
        if token.on is ...:
            return False
        return scope.is_provided(token.on, start=token.at)

    def _provide(self, scope: 'AbcScope', token: 'Depends') -> ResolverInfo:

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

                    return InjectorVar(make=make)
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

                    return InjectorVar(make=make)

        return ResolverInfo(resolve, {dep})





@export()
@dataclass
class LookupProvider(AliasProvider):

    def can_provide(self, scope: 'AbcScope', token: 'InjectedLookup') -> bool:
        return scope.is_provided(token.depends)

    def _provide(self, scope: 'AbcScope', token: 'InjectedLookup',  *_args, **_kwds) -> ResolverInfo:

        dep = token.depends
        path = token.path

        def resolve(at: 'Injector'):
            nonlocal dep, path
            if var := at.vars[dep]:
                if var.value is Void:
                    return InjectorVar(make=lambda: path.get(var.get()))

                # px = proxy(lambda: path.get(var.get()))
                return InjectorVar(make=lambda: path.get(var.value))
            return 

        return ResolverInfo(resolve, {dep})

