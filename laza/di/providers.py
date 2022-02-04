# from __future__ import annotations
from functools import lru_cache, wraps
from inspect import ismemberdescriptor
from logging import getLogger
from types import FunctionType, GenericAlias, new_class
import typing as t 
from inspect import Parameter, Signature
from abc import ABC, ABCMeta, abstractmethod
from laza.common.collections import Arguments, frozendict, orderedset

from collections import ChainMap
from collections.abc import  Callable, Set, Mapping
from laza.common.typing import get_args, typed_signature, Self, get_origin


from laza.common.functools import Missing, export, cached_property, cache


from laza.common.enum import BitSetFlag, auto




from .common import (
    FactoryScopeVar, InjectedLookup, ScopeVar,
    Injectable, Depends, SingletonScopeVar,
    T_Injected, T_Injectable, 
    ResolverFunc
)


if t.TYPE_CHECKING:
    from .containers import IocContainer
    from .injectors import Injector
    from .scopes import Scope




logger = getLogger(__name__)



_T = t.TypeVar('_T')
_T_Fn = t.TypeVar('_T_Fn', bound=Callable, covariant=True)
_T_Using = t.TypeVar('_T_Using')


T_UsingAlias = T_Injectable
T_UsingVariant = T_Injectable
T_UsingValue = T_Injected

T_UsingFunc = Callable[..., T_Injected]
T_UsingType = type[T_Injected]

T_UsingCallable = t.Union[T_UsingType, T_UsingFunc]




T_UsingAny = t.Union[T_UsingCallable, T_UsingAlias, T_UsingValue]



def _fluent_decorator(default=Missing, *, fluent: bool=False):
    def decorator(fn: _T_Fn) -> _T_Fn:
        
        if t.TYPE_CHECKING:
            @t.overload
            def wrapper(self, v, *a, **kwds) -> Self: ...
            @t.overload
            def wrapper(self, **kwds) -> Callable[[_T], _T]: ...

            if fluent is True:
                @wraps(fn)
                def wrapper(self, v=default, /, *args, **kwds) -> t.Union[_T, Callable[..., _T]]:
                    ...
            else:
                @wraps(fn)
                def wrapper(self, v: _T=default, /, *args, **kwds) -> t.Union[_T, Callable[..., _T]]:
                    ...
        @wraps(fn)
        def wrapper(self, v=default, /, *args, **kwds):
            nonlocal fn, default, fluent
            if v is default:
                def decorator(val: _T) -> _T:
                    nonlocal fn, v, args, kwds
                    rv = fn(self, val, *args, **kwds)
                    return rv if fluent is True else val
                return decorator
            return fn(self, v, *args, **kwds)
        
        return wrapper

    return decorator
    

class Flag(BitSetFlag):
    aot: 'Flag'         = auto()
    """Compile the provider `Ahead of Time`
    """
    shared: 'Flag'         = auto()
    """Compile the provider `Ahead of Time`
    """
    


class ProviderCondition(Callable[..., bool]):

    __class_getitem__ = classmethod(GenericAlias)

    def __call__(self, provider: 'Provider', scope: 'Injector', key: T_Injectable) -> bool:
        ...




@export()
class Handler(t.Protocol[T_Injected]):

    deps: t.Optional[Set[T_Injectable]]

    def __call__(self, provider: 'Provider', scope: 'Injector', token: T_Injectable) -> ScopeVar:
        ...


def _is_attr(anno, val:bool=False):
    return get_origin(anno) not in (t.ClassVar, t.Final if val else ...)


class _Attr(t.Generic[_T]):

    __slots__ = 'default', '__call__',
    
    def __new__(cls: type[Self], default: _T=..., *, default_factory: Callable[[], _T]=...) -> Self:
        if isinstance(default, cls):
            return default

        self = object.__new__(cls)
        if default_factory is ... is default:
            raise ValueError(f'default not provided')
        elif default_factory is ...:
            def __call__(): return default
        else:
            __call__ = default_factory

        self.default = default
        self.__call__ = __call__
        return self
        
    def __set_name__(self, owner, name):
        raise RuntimeError(f'{self.__class__.__name__} is not a true destcriptor.')





class ProviderType(ABCMeta):

    _tp__uses: t.Final[type[_T_Using]] = None
    _tp__provides: t.Final[type[T_Injected]] = None

    @classmethod
    def __prepare__(mcls, name, bases, **kwds):
        ns = super().__prepare__(name, bases)
        print(f'{name=}, {ns=}, {kwds=}')
        
        if any(isinstance(b, ProviderType) for b in bases):
            return ns
        return ns

    def __new__(mcls, name: str, bases: tuple[type], ns: dict, **kwds):
        ann = ns.setdefault('__annotations__', {})
        
        if '__setattr__' not in ns:
            ns['__setattr__'] = Provider.__frozen_setattr__
        

        attrset = f'_{name}__set_attr'
        if attrset not in ns:
            ns[attrset] = Provider.__setattr__

        slots = tuple(
            n for n, a in ann.items() 
                if (get_origin(a) or a) not in (t.ClassVar, n in ns or t.Final)
        )

        ns.setdefault('__slots__', slots)
        ns['__attr_defaults__'] = None

        defaults = ChainMap(
            { n : ns.pop(n) for n in slots if n in ns  }, 
            *(b.__attr_defaults__ for b in bases if isinstance(b, ProviderType))
        )
        
        cls = super().__new__(mcls, name, bases, ns)

        cls.__attr_defaults__ = { 
            n: _Attr(v) 
            for n, v in defaults.items() 
                if not hasattr(cls, n) or ismemberdescriptor(getattr(cls, n))
        }

        return cls

    # def __getitem__(self, params):
    #     if not isinstance(params, tuple):
    #         params = params,
        
    #     cls = self._typed__class(params)
    #     params = params+ self.__parameters__[len(params):]
    #     if params:
    #         cls = GenericAlias(cls, params)
    #     return cls

    # @cache
    # def _typed__class(self: Self, params):
    #     tu = tp = None

    #     if params and self._tp__uses is None:
    #         if not isinstance(params[0], t.TypeVar):
    #             tu, *params = params
        
    #     if params and self._tp__provides is None:
    #         if not isinstance(params[0], t.TypeVar):
    #             tp, *params = params
        
    #     if tu is None is tp:
    #         return self

    #     fn = lambda ns: (tu and ns.update(_tp__uses=tu)) \
    #         or (tp and ns.update(_tp__provides=tp))

    #     return t.cast(Self, new_class(self.__name__, (self,), None, fn))
            






@export()
class Provider(t.Generic[_T_Using, T_Injected], metaclass=ProviderType):

    __attr_defaults__: t.Final[dict[str, _Attr]] = ...

    container: 'IocContainer'
    """The IocContainer bound to this instance.
    """

    bound: bool = False
    """Whether or not this provider is bound to its container.
    """

    _provides: T_Injectable = Missing
    """The Injectable/token provided by this provider
    """

    _uses: _T_Using = Missing
    """The object used to resolve 
    """

    def __init__(self, provide: Injectable=Missing, using=Missing) -> None:
        self.__init_attrs__()
        provide is Missing or self.provide(provide)
        using is Missing or self.using(using)

    @property
    def provides(self) -> T_Injectable:
        """The Injectable/token provided by this provider
        """
        val = self._provides
        if val is Missing:
            val = self._provides_fallback()
            if val is Missing:
                raise AttributeError(f'{"provides"!r} in {self}')
        return val

    @property
    def uses(self) -> _T_Using:
        val = self._uses
        if val is Missing:
            val = self._uses_fallback()
            if val is Missing:
                raise AttributeError(f'{"uses"!r} in {self}')
        return val
    
    def _uses_fallback(self):
        return Missing

    def _provides_fallback(self):
        return Missing

    def bind(self, bind: 'IocContainer') -> Self:
        if hasattr(self, 'container'):
            if self.container is not bind:
                raise RuntimeError(f'provider {self} already bound to {self.container}')
            elif self.bound is True:
                return self
        else:
            self.__set_attr('container', bind)

        self._bind()
        return self

    def _bind(self):
        if self.bound:
            raise RuntimeError(
                    f'cannot bind {self}. already bound to {self.container}.')
        elif self._can_bind():
            self.__set_attr('bound', True)
            self.container.register_provider(self)

    def _can_bind(self):
        if self.bound:
            return False
        try:
            self.provides, self.container, self.uses
            return True
        except AttributeError:
            return False

    @t.overload
    def provide(self) -> Callable[[T_Injectable], T_Injectable]: ...
    @t.overload
    def provide(self, provide: T_Injectable) -> Self: ...
    @_fluent_decorator()
    def provide(self, provide: T_Injectable):
        if self._provides is Missing:
            self.__set_attr('_provides', provide)
        elif provide is not self._provides:
            raise AttributeError(
                f'cannot {provide=}. {self} already provides {self._provides}.')
        self.bound or self._bind()
        return self

    @t.overload
    def using(self) -> Callable[[_T], _T]: ...
    @t.overload
    def using(self, using: t.Any) -> Self: ...
    @_fluent_decorator()
    def using(self, using):
        self.__set_attr('_uses', using)
        self.bound or self._bind()
        return self
    
    def compile(self, token: T_Injectable) -> Handler:
        return self._compile(token)
    
    @abstractmethod
    def _compile(self, token: T_Injectable) -> Handler:
        ...
    
    # def can_provide(self, scope: 'Injector', dep: T_Injectable) -> bool:
    #     return True

    def __init_attrs__(self):
        for k, attr in self.__attr_defaults__.items():
            self.__set_attr(k, attr())

    t.Final
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)

    if t.TYPE_CHECKING:
        t.Final
        def __set_attr(self, name, value) -> Self:
            ...

    __set_attr = __setattr__

    t.Final
    def __frozen_setattr__(self, name, value):
        getattr(self, name)
        AttributeError(f'{self.__class__.__name__}.{name} is not writable')
       






@export()
class Value(Provider[T_UsingValue, T_Injected]):

    def _compile(self, dep: T_Injectable) -> Handler:
        var = ScopeVar(self.uses)
        return lambda at: var





class InjectedArgumentsDict(dict[str, t.Any]):
    
    __slots__ = 'inj',

    inj: 'Scope'

    def __init__(self, inj: 'Scope', /, deps=()):
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

    def args(self, inj: 'Scope', vals: dict[str, t.Any]=frozendict()):
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

    def var_arg(self, inj: 'Scope', vals: Mapping[str, t.Any]=frozendict()):
        if _var := self._var_arg:
            n, v, i = _var
            if v is not _EMPTY:
                yield from v
            elif i is not _EMPTY:
                yield from inj.get(i, ())

    def kwargs(self, inj: 'Scope', vals: dict[str, t.Any]=frozendict()):
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

    def kwds(self, inj: 'Scope', vals: dict[str, t.Any]=frozendict()):
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

    def var_kwd(self, inj: 'Scope', vals: Mapping[str, t.Any]=frozendict()):
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
class Factory(Provider[Callable[..., T_Injected], T_Injected]):
    
    EMPTY: t.ClassVar = _EMPTY
    _argument_view_cls: t.ClassVar = ArgumentView

    arguments: Arguments = _Attr(default_factory=Arguments)
    is_singleton: bool = False
    deps: dict[str, Injectable] = _Attr(default_factory=frozendict)

    def __init__(self, provide: Callable[..., T_Injectable]=None, *args, **kwargs) -> None:
        super().__init__(provide)
        args and self.args(*args)
        kwargs and self.kwargs(**kwargs)

    def _uses_fallback(self):
        if callable(self._provides):
            return self._provides
        
        return super()._uses_fallback()

    def _provides_fallback(self):
        if isinstance(self._uses, Injectable):
            return self._uses
        return super()._provides_fallback()

    def args(self, *args) -> Self:
        return self.__set_attr('arguments', self.arguments.extend(args))

    def kwargs(self, **kwargs) -> Self:
        return self.__set_attr('arguments', self.arguments.extend(kwargs))

    def singleton(self, is_singleton: bool = True) -> Self:
        return self.__set_attr('is_singleton', is_singleton)

    def get_signature(self) -> t.Union[Signature, None]:
        return typed_signature(self.uses)

    def get_available_deps(self, sig: Signature, deps: Mapping):
        return { n: d for n, d in deps.items() if self.container.is_provided(d) }

    def get_explicit_deps(self, sig: Signature):
        return  { n: d for n, d in self.deps.items() if isinstance(d, Injectable) }

    def get_implicit_deps(self, sig: Signature):
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

    def _compile(self, ____token: T_Injectable) -> Handler:

        func = self.uses
        shared = self.is_singleton

        sig = self.get_signature()

        arguments = self.arguments

        bound = sig.bind_partial(*arguments.args, **arguments.kwargs) or None
        var_cls = SingletonScopeVar if shared else FactoryScopeVar
        
        if not sig.parameters:
            def handler(scp):
                nonlocal func, var_cls
                return var_cls(func)

            return handler

        defaults = frozendict(bound.arguments)
        
        expl_deps = self.get_explicit_deps(sig)
        impl_deps = self.get_implicit_deps(sig)

        all_deps = dict(impl_deps, **expl_deps)
        deps = all_deps # self.get_available_deps(sig, all_deps)
        argv = self.create_arguments_view(sig, defaults, deps)

        # print(f'compile -> {func} \n ***{all_deps=}*** \n ***{deps}***')

        def handler(scp: 'Scope'):
            nonlocal var_cls
            
            def make(*a, **kw):
                nonlocal func, argv, scp
                return func(*argv.args(scp, kw), *a, **argv.kwds(scp, kw))

            return var_cls(make)

        handler.deps = set(all_deps.values())
        return handler




@export()
class Function(Factory[T_Injected]):
    ...

   



@export()
class Type(Factory[T_Injected]):
    ...


@export()
class Alias(Provider[T_UsingAlias, T_Injected]):

    def _compile(self, ____token: T_Injectable) -> Handler:
        real = self.uses

        def handler(scope: 'Scope'):
            nonlocal real
            return scope.vars[real]

        handler.deps = {real}
        return handler




@export()
class UnionProvider(Alias):

    uses = t.Union

    _implicit_types_ = frozenset([type(None)]) 

    def get_all_args(self, token: Injectable):
        return get_args(token)

    def get_injectable_args(self, token: Injectable, *, include_implicit=True) -> tuple[Injectable]:
        implicits = self._implicit_types_ if include_implicit else set()
        return tuple(a for a in self.get_all_args(token) if a in implicits or self.container.is_provided(a))
    
    # def can_provide(self, scope: 'Injector', token: Injectable) -> bool:
    #     return len(self.get_injectable_args(scope, token, include_implicit=False)) > 0

    def _compile(self, token):
        
        args = self.get_injectable_args(token)

        def handle(scp: 'Scope'):
            nonlocal args
            return next((v for a in args if (v := scp.vars[a])), None)

        handle.deps = {*args}
        return handle




@export()
class AnnotationProvider(UnionProvider):

    # use: InitVar[_T_Using] = t.Annotated
    uses: t.Final = t.Annotated

    _implicit_types_ = frozenset() 

    def get_all_args(self, token: Injectable):
        return token.__metadata__[::-1]



@export()
class DependencyProvider(Alias):

    # use: InitVar[_T_Using] = Depends

    # def can_provide(self, scope: 'Injector', token: 'Depends') -> bool:
    #     if token.on is ...:
    #         return False
    #     return scope.is_provided(token.on, start=token.at)

    def _compile(self, token: 'Depends') -> Handler:

        dep = token.on
        arguments = token.arguments or None

        if arguments:
            args, kwargs = arguments.args, arguments.kwargs
            def resolve(scp: 'Scope'):
                nonlocal dep
                if inner := scp.vars[dep]:
                    def make(*a, **kw):
                        nonlocal inner, args, kwargs
                        return inner.make(*args, *a, **(kwargs | kw))

                    return FactoryScopeVar(make=make)
        else:
            def resolve(scp: 'Scope'):
                nonlocal dep
                if inner := scp.vars[dep]:
                    return FactoryScopeVar(make=inner.make)


        resolve.deps = {dep}
        return resolve

        # if at in scope.aliases:
        #     at = None

        # # if at and arguments:
        
        # if arguments:
        #     def resolve(inj: 'Injector'):
        #         nonlocal dep
        #         return InjectorVar(make=inj.vars[dep].make(), )
        # elif arguments is None:
        #     def resolve(inj: 'Injector'):
        #         nonlocal dep
        #         return inj.vars[dep]
        # elif at is None:
        #     args, kwargs = arguments.args, arguments.kwargs
        #     def resolve(inj: 'Injector'):
        #         nonlocal dep
        #         if inner := inj.vars[dep]:
        #             def make(*a, **kw):
        #                 nonlocal inner, args, kwargs
        #                 return inner.make(*args, *a, **dict(kwargs, **kw))

        #             return InjectorVar(make=make)
        # else:
        #     at = scope.ioc.scopekey(at)
        #     args, kwargs = arguments.args, arguments.kwargs
        #     def resolve(inj: 'Injector'):
        #         nonlocal at, dep
        #         inj = inj[at]
        #         if inner := inj.vars[dep]:
        #             def make(*a, **kw):
        #                 nonlocal inner, args, kwargs
        #                 return inner.make(*args, *a, **dict(kwargs, **kw))

        #             return InjectorVar(make=make)

        # # return Handler(resolve, {dep})
        # resolve.deps = {dep}
        # return resolve





@export()
class LookupProvider(Alias):

    # def can_provide(self, scope: 'Injector', token: 'InjectedLookup') -> bool:
    #     return scope.is_provided(token.depends)

    def _compile(self, token: 'InjectedLookup') -> Handler:

        dep = token.depends
        path = token.path

        def hander(scp: 'Scope'):
            nonlocal dep, path
            if var := scp.vars[dep]:
                if var.value is Missing:
                    return FactoryScopeVar(make=lambda: path.get(var.get()))
                return FactoryScopeVar(make=lambda: path.get(var.value))
            return 

        hander.deps = {dep}
        return hander









def _provder_factory_method(cls: type[_T]):
    @wraps(cls)
    def wrapper(self: 'RegistrarMixin', *a, **kw) -> type[_T]:
        val = cls(*a, **kw)
        self.register_provider(val)
        return val
    return t.cast(cls, wrapper)



@export()
class RegistrarMixin(ABC, t.Generic[T_Injected]):

    __slots__ = ()

    @abstractmethod
    def register_provider(self, provider: Provider[T_UsingAny, T_Injected]) -> Self:
        ...

    def alias(self, *a, **kw) -> Alias: ...
    def value(self, *a, **kw) -> Value: ...
    def factory(self, *a, **kw) -> Factory: ...
    def function(self, *a, **kw) -> Function: ...
    def type(self, *a, **kw) -> Type: ...

    if t.TYPE_CHECKING:
        alias = Alias
        value = Value
        factory = Factory
        function = Function
        type = Type
    else:
        alias = _provder_factory_method(Alias)
        value = _provder_factory_method(Value)
        factory = _provder_factory_method(Factory)
        function = _provder_factory_method(Function)
        type = _provder_factory_method(Type)
        