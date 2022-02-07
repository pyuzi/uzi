# from __future__ import annotations
from functools import lru_cache, wraps
from inspect import ismemberdescriptor, signature
from logging import getLogger
from types import FunctionType, GenericAlias, new_class
import typing as t 
from inspect import Parameter, Signature
from abc import ABC, ABCMeta, abstractmethod
from laza.common.collections import Arguments, frozendict, orderedset

from collections import ChainMap
from collections.abc import  Callable, Set, Mapping
from laza.common.typing import get_args, typed_signature, Self, get_origin


from laza.common.functools import Missing, export, cache, cached_slot


from laza.common.enum import BitSetFlag, auto
from laza.common.collections import fallbackdict



from .vars import ScopeVar, FactoryScopeVar, SingletonScopeVar, ValueScopeVar, Scope
from .common import (
    InjectedLookup,
    Injectable, Depends,
    T_Injected, T_Injectable, 
)



if t.TYPE_CHECKING:
    from .containers import IocContainer
    from .injectors import Injector




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
    def decorator(func: _T_Fn) -> _T_Fn:

        if t.TYPE_CHECKING:
            @t.overload
            def wrapper(self, v, *a, **kwds) -> Self: ...
            @t.overload
            def wrapper(self, **kwds) -> Callable[[_T], _T]: ...

            if fluent is True:
                @wraps(func)
                def wrapper(self, v=default, /, *args, **kwds) -> t.Union[_T, Callable[..., _T]]:
                    ...
            else:
                @wraps(func)
                def wrapper(self, v: _T=default, /, *args, **kwds) -> t.Union[_T, Callable[..., _T]]:
                    ...
        
        fn = func
        while hasattr(fn, '_is_fluent_decorator'):
            fn = fn.__wrapped__

        @wraps(func)
        def wrapper(self, v=default, /, *args, **kwds):
            nonlocal func, default, fluent
            if v is default:
                def decorator(val: _T) -> _T:
                    nonlocal func, v, args, kwds
                    rv = func(self, val, *args, **kwds)
                    return rv if fluent is True else val
                return decorator
            return func(self, v, *args, **kwds)
        
        wrapper._is_fluent_decorator = True

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

    def __call__(self, scope: 'Scope', token: T_Injectable=None) -> ScopeVar:
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

    @provides.setter
    def provides(self, val):
        if self._provides is Missing:
            self.__set_attr('_provides', val)
        elif val is not self._provides:
            raise AttributeError(
                f'cannot {val=}. {self} already provides {self._provides}.')
        self.bound or self._bind()

    @property
    def uses(self) -> _T_Using:
        val = self._uses
        if val is Missing:
            val = self._uses_fallback()
            if val is Missing:
                raise AttributeError(f'{"uses"!r} in {self}')
        return val
    
    @uses.setter
    def uses(self, val):
        self.__set_attr('_uses', val)
        self.bound or self._bind()
    
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
            self._add_to_container()

    def _add_to_container(self):
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
        self.__set_attr('provides', provide)
        return self
        
    @t.overload
    def using(self) -> Callable[[_T], _T]: ...
    @t.overload
    def using(self, using: t.Any) -> Self: ...
    @_fluent_decorator()
    def using(self, using):
        self.__set_attr('uses', using)
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

    def __repr__(self):
        using =self._uses_fallback() if self._uses is Missing else self._uses 
        provides =self._provides_fallback() if self._provides is Missing else self._provides 
        return f'{self.__class__.__name__}({provides=!r}, {using=!r})'

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
        # if var_kwd:
        #     self._non_kwds = frozenset(a for a, *_ in kwargs),
        # else:
        #     self._non_kwds = frozenset()

        return self

    def args(self, scp: 'Scope', vals: dict[str, t.Any]=frozendict()):
        for n, v, i, d in self._args:
            if v is not _EMPTY:
                yield v
                continue
            elif i is not _EMPTY:
                if d is _EMPTY:
                    yield scp[i].get()
                else:
                    v = scp.get(i)
                    yield d if v is None else v.get()
                continue
            elif d is not _EMPTY:
                yield d
                continue
            else:
                return
        
        if _var := self._var_arg:
            n, v, i = _var
            if v is not _EMPTY:
                yield from v
            elif i is not _EMPTY:
                v = scp.get(i)
                if v is not None:
                    yield from v.get()
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
                        yield scp[i]
                    else:
                        yield scp.get(i, d)
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
    is_partial: bool = False
    
    
    deps: dict[str, Injectable] = _Attr(default_factory=frozendict)


    def __init__(self, provide: Injectable=..., using: Callable[..., T_Injectable]=..., /, *args, **kwargs) -> None:
        super().__init__(
            Missing if provide in (None, ...) else provide,
            Missing if using in (None, ...) else using
        )
            
        args and self.args(*args)
        kwargs and self.kwargs(**kwargs)

    @property
    @cache
    def signature(self) -> Signature:
        return self._eval_signature()

    def _uses_fallback(self):
        if callable(self._provides):
            return self._provides
        
        return super()._uses_fallback()

    def _provides_fallback(self):
        if isinstance(self._uses, Injectable):
            return self._uses
        return super()._provides_fallback()

    def depends(self, **deps) -> Self:
        self.__set_attr('deps', frozendict(deps))
        return self

    def args(self, *args) -> Self:
        self.__set_attr('arguments', self.arguments.replace(args))
        return self

    def kwargs(self, **kwargs) -> Self:
        self.__set_attr('arguments', self.arguments.replace(kwargs=kwargs))
        return self

    def partial(self, is_partial: bool = True) -> Self:
        self.__set_attr('is_partial', is_partial)
        return self

    def singleton(self, is_singleton: bool = True) -> Self:
        self.__set_attr('is_singleton', is_singleton)
        return self

    def _eval_signature(self) -> Signature:
        return typed_signature(self.uses)

    def get_available_deps(self, sig: Signature, deps: Mapping):
        return { n: d for n, d in deps.items() if self.container.is_provided(d) }

    def get_explicit_deps(self, sig: Signature):
        return  { 
            n: p.default
            for n, p in sig.parameters.items() 
                if isinstance(p.default, Depends)
        } | self.deps

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




    def _old_compile(self, ____token: T_Injectable) -> Handler:

        func = self.uses
        shared = self.is_singleton

        sig = self._eval_signature()

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

        def handler(scp: 'Scope'):
            nonlocal var_cls
            def make(*a, **kw):
                nonlocal func, argv, scp
                return func(*argv.args(scp, kw), *a, **argv.kwds(scp, kw))

            return var_cls(make)

        handler.deps = set(all_deps.values())
        return handler

    
    def _compile(self, ____token: T_Injectable) -> Handler:

        func = self.uses
        is_singleton = self.is_singleton
        is_partial = self.is_partial

        sig = self.signature
        injector = self.container if self.bound else {}
 
        if is_singleton and is_partial:
            raise ValueError(
                f'`is_singleton` and `is_partial` are mutually exclusive. '
                f'`is_singleton` == True == `is_partial` in {self}'
            )

        varcls = SingletonScopeVar if is_singleton else FactoryScopeVar
        
        if not (self.arguments or self.deps or sig.parameters):
            def handler(scp):
                nonlocal func, varcls
                return varcls(func)

            return handler

        
        pos_only_params = _pos_only_params(sig)
        v_args_param = _var_pos_param(sig)
        kwd_params = _kwd_params(sig)
        v_kwd_param = _var_kwd_param(sig)


        bound = sig.bind_partial(*self.arguments.args, **self.arguments.kwargs)

        _get_empty = lambda k: _EMPTY

        skip_params = {v_args_param, v_kwd_param}

        values = fallbackdict(_get_empty, ( 
            (n, v) for n, v in bound.arguments.items() 
                if not isinstance(v, Depends) 
                    and n not in skip_params
        ))

        bound.apply_defaults()
        arguments = bound.arguments

        arg_deps = { 
            n: v for n, v in arguments.items() if isinstance(v, Depends)
        }

        skip_params.update(values, arg_deps)

        anno_deps = { n: p.annotation
            for n, p in sig.parameters.items() 
                if n not in skip_params 
                    and p.annotation is not _EMPTY 
                        and isinstance(p.annotation, Injectable)
        }   

        deps = fallbackdict(_get_empty, anno_deps | arg_deps)

        defaults = fallbackdict(_get_empty, ( 
            (n, v) for n, v in arguments.items() if n not in skip_params
        ))
        
        _vals = { n: values[n] for n in kwd_params if n in values }
        
        _args = []
        for v in pos_only_params:
            _args.append((values[v], deps[v], defaults[v]))

        if v_args_param:
            for v in arguments[v_args_param]:
                if isinstance(v, Depends):
                    _args.append((_EMPTY, v, _EMPTY))
                else:
                    _args.append((v, _EMPTY, _EMPTY))


        _kwds = [ (n, deps[n], defaults[n]) for n in kwd_params if n in deps ]

        if v_kwd_param:
            for n, v in arguments[v_kwd_param].items():
                if isinstance(v, Depends):
                    _kwds.append((v, _EMPTY))
                else: 
                    _vals[n] = v

        if _args and _kwds:
            def handler(scp: 'Scope'):
                nonlocal varcls, _args, _vals, _kwds

                args = [ (v, scp[i], d) for v, i, d in _args ]
                kwds = [ (n, scp[i], d) for n, i, d in _kwds ]

                def make():
                    nonlocal func, args, kwds, _vals
                    return func(*_iargs(args), **_vals, **_ikwds(kwds))
                return varcls(make)
        elif _args:
             def handler(scp: 'Scope'):
                nonlocal varcls, _args, _vals
                args = [ (v, scp[i], d) for v, i, d in _args ]

                def make():
                    nonlocal func, args, _vals
                    return func(*_iargs(args), **_vals)
                return varcls(make)
        else:
             def handler(scp: 'Scope'):
                nonlocal varcls, _vals, _kwds

                kwds = [ (n, scp[i], d) for n, i, d in _kwds ]

                def make():
                    nonlocal func, kwds, _vals
                    return func(**_vals, **_ikwds(kwds))
                return varcls(make)
        

        handler.deps = set(deps.values())
        return handler




def _pos_only_params(sig: Signature):
    return [
        n for n, p in sig.parameters.items() if p.kind is p.POSITIONAL_ONLY
    ]

def _var_pos_param(sig: Signature):
    for n, p in sig.parameters.items():
        if p.kind is p.VAR_POSITIONAL:
            return n

def _kwd_params(sig: Signature):
    return [
        n for n, p in sig.parameters.items() if p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]


def _var_kwd_param(sig: Signature):
    for n, p in sig.parameters.items():
        if p.kind is p.VAR_KEYWORD:
            return n


def _iargs(args: list[tuple[t.Any, ScopeVar, t.Any]]):
    for v, i, d in args:
        if v is _EMPTY:
            if i is _EMPTY:
                if d is _EMPTY:
                    break
                yield d
            yield i.get()
        yield v


def _ikwds(kwds: list[tuple[str, ScopeVar, t.Any]]):
    vals = {}
    for n, i, d in kwds:
        if i is _EMPTY:
            if d is _EMPTY:
                continue
            vals[n] = d
        vals[n] = i.get()
    return vals





@export()
class Function(Factory[T_Injected]):
    ...

   

@export()
class Type(Factory[T_Injected]):
    ...





@export()
class InjectionProvider(Factory[T_Injected]):


    @property
    def wrapped(self):
        return self.uses

    @property
    @cache
    def wrapper(self):
        return self._make_wrapper()

    def _make_wrapper(self):
        wrapped = self.wrapped
        @wraps(wrapped)
        def wrapper(*a, **kw):
            nonlocal self, wrapped
            return self.container._context()[wrapped].get()

        wrapper.__injects__ = wrapped
        return wrapper



@export()
class Alias(Provider[T_UsingAlias, T_Injected]):

    def _compile(self, ____token: T_Injectable) -> Handler:
        real = self.uses

        def handler(scope: 'Scope'):
            nonlocal real
            return scope[real]

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
            for a in args:
                v = scp.vars[a]
                if v is not None:
                    return v

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
                return scp.vars[dep]
              

        resolve.deps = {dep}
        return resolve






@export()
class LookupProvider(Alias):

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
    
    def inject(self, func: Callable[..., _T]=None, **opts):
        def decorator(fn: Callable[..., _T]):
            pro = InjectionProvider(fn)
            self.register_provider(pro)
            return pro.wrapper

        if func is None:
            return decorator
        else:
            return decorator(func)    