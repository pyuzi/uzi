# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False


from email.generator import Generator
from email.policy import default
from enum import Enum
from itertools import starmap
from threading import Lock
import typing as t
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence, Collection, Iterator, Mapping, ItemsView, ValuesView
from inspect import Parameter, Signature, isawaitable, iscoroutinefunction
from asyncio import AbstractEventLoop, ensure_future, gather as async_gather, get_running_loop
import asyncio

from logging import getLogger
from inject import T

from laza.common.abc import abstractclass
from laza.common.asyncio.futures import Future
from laza.common.collections import Arguments, frozendict, orderedset, emptydict
from laza.common.functools import Missing, export
from laza.common.typing import Self, typed_signature
from pytest import yield_fixture

from libs.common.laza.common.collections import FactoryDict, frozenorderedset

from .. import Injectable, InjectionMarker, T_Injectable, T_Injected, is_injectable_annotation


if t.TYPE_CHECKING:
    from ..injectors import Injector, InjectorContext




import cython

logger = getLogger(__name__)

_POSITIONAL_ONLY = Parameter.POSITIONAL_ONLY
_VAR_POSITIONAL = Parameter.VAR_POSITIONAL
_POSITIONAL_KINDS = frozenset([_POSITIONAL_ONLY, _VAR_POSITIONAL])
_POSITIONAL_OR_KEYWORD = Parameter.POSITIONAL_OR_KEYWORD
_KEYWORD_ONLY = Parameter.KEYWORD_ONLY
_VAR_KEYWORD = Parameter.VAR_KEYWORD
_KEYWORD_KINDS = frozenset(
    [Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY, Parameter.VAR_KEYWORD]
)

_EMPTY = Parameter.empty

_T = t.TypeVar("_T")


# if cython.compiled:
#     # print(f'RUNNING: "{__name__}" IN COMPILED MODE')
# else:
#     # print(f'RUNNING IN PYTHON')


_object_new = object.__new__
_object_setattr = object.__setattr__


@abstractclass
class decorators:
    @staticmethod
    def singleton(func: Callable, ctx: "InjectorContext", *, is_async: bool=False):
        lock = ctx.lock()
        value = Missing
        if lock is None:

            def run() -> T_Injected:
                nonlocal func, value
                if value is Missing:
                    value = func()
                return value

        else:

            def run() -> T_Injected:
                nonlocal lock, func, value
                if value is Missing:
                    with lock:
                        if value is Missing:
                            value = func()
                return value

        return run

    @staticmethod
    def resource(func: Callable, ctx: "InjectorContext", *, is_async: bool=False):
        lock = ctx.lock()
        value = Missing

        if lock is None:

            def run() -> T_Injected:
                nonlocal func, value, ctx
                if value is Missing:
                    value = ctx.enter(func())
                return value

        else:

            def run() -> T_Injected:
                nonlocal lock, func, value, ctx
                if value is Missing:
                    with lock:
                        if value is Missing:
                            value = ctx.enter(func())
                return value

        return run

    @staticmethod
    def contextmanager(cm, ctx: "InjectorContext", *, is_async: bool=False):
        lock = ctx.lock()
        value = Missing

        if lock is None:

            def run():
                nonlocal cm, value, ctx
                if value is Missing:
                    value = ctx.enter(cm)
                return value

        else:

            def run():
                nonlocal cm, value, lock, ctx
                if value is Missing:
                    with lock:
                        if value is Missing:
                            value = ctx.enter(cm)
                return value

        return run




def _is_aync_provider(obj) -> bool:
    return getattr(obj, 'is_async', False) is True



class _ParamBindType(Enum):
    awaitable: '_ParamBindType'  = 'awaitable'
    callable: '_ParamBindType'  = 'callable'
    value: '_ParamBindType'  = 'value'


_PARAM_AWAITABLE = _ParamBindType.awaitable
_PARAM_CALLABLE = _ParamBindType.callable
_PARAM_VALUE = _ParamBindType.value


class BoundParam:

    __slots__ = (
        "param",
        "key",
        "value",
        "dependency",
        # "default",
        "has_value",
        "has_default",
        "has_dependency",
        "_value_factory",
        "_default_factory",
        "is_async",
    )

    param: Parameter
    name: str
    annotation: t.Any
    value: _T
    default: t.Any
    dependency: Injectable
    is_async: bool
    has_value: bool
    has_dependency: bool

    # _aw_value: 'AwaitValue'
    # _aw_default: 'AwaitValue'

    def __new__(cls, param: Parameter, value: t.Any = _EMPTY, key: t.Union[str, int]=None):
        self = object.__new__(cls)
        self.param = param
        self.key = key or param.name
        self.has_value = self.is_async = self.has_default = self.has_dependency = False
       
        if isinstance(value, InjectionMarker):
            self.dependency = value
            self.has_dependency = True
        elif not value is _EMPTY:
            self.has_value = True
            self.value = value

        if isinstance(param.default, InjectionMarker):
            if self.has_dependency is False:
                self.dependency = param.default
                self.has_dependency = True
        else:
            self.has_default = not param.default is _EMPTY

        if False is self.has_dependency:
            annotation = param.annotation
            if is_injectable_annotation(annotation):
                self.dependency = annotation
                self.has_dependency = isinstance(annotation, InjectionMarker) or None
       
        return self

    @property
    def name(self):
        return self.param.name
        
    @property
    def default(self):
        return self.param.default
        
    @property
    def annotation(self):
        return self.param.annotation
        
    @property
    def kind(self):
        return self.param.kind
        
    @property
    def value_factory(self) -> None:
        try:
            return self._value_factory 
        except AttributeError as e:
            if not self.has_value:
                raise AttributeError(f'`value`') from e
            value = self.value
            self._value_factory = lambda: value
            return self._value_factory

    @property
    def default_factory(self) -> None:
        try:
            return self._default_factory 
        except AttributeError as e:
            if self.has_default is True:
                default = self.default
                self._default_factory = lambda: default 
            elif self.has_dependency is True:
                self._default_factory = Missing
            else:
                raise AttributeError(f'`default_factory`')
            return self._default_factory





@export
class FactoryBinding:

    __slots__ = (
        "factory",
        "signature",
        "decorators",
        "injector",
        "args",
        "aw_call",
        "aw_args",
        "aw_kwds",
        "kwds",
        "deps",
        "vals",
        "_wrapper_factory",
    )

    factory: Callable
    injector: 'Injector'
    arguments: dict[str, t.Any]
    signature: Signature
    decorators: list[Callable[[Callable], Callable]]

    aws: frozenorderedset[BoundParam]
    deps: frozenset[BoundParam]
    args: tuple[BoundParam]
    aw_args: bool
    kwds: tuple[BoundParam]
    aw_kwds: bool
    vals: frozendict[str, t.Any]
    aw_call: bool

    def __init__(
        self,
        injector: 'Injector',
        factory: Callable,
        signature: Signature = None,
        *,
        is_async: bool = None,
        arguments: Arguments = None,
    ):
        # self = object.__new__(cls)
        self.factory = factory
        self.injector = injector
        self.aw_call = iscoroutinefunction(factory) if is_async is None else is_async
        self.signature = signature or typed_signature(factory)
        self._evaluate(self._parse_arguments(arguments))

    @property
    def is_async(self):
        return self.aw_call or self.aw_kwds or self.aw_args

    @property
    def dependencies(self):
        return {
            p.dependency 
                for _ in (self.args, self.kwds) 
                    for p in _ 
                        if p.has_dependency
        }

    def _parse_arguments(self, arguments: Arguments = None):
        if arguments:
            bound = self.signature.bind_partial(*arguments.args, **arguments.kwargs)
        else:
            bound = self.signature.bind_partial()
        return bound.arguments

    def _iter_bind_params(self, arguments: dict):
        i = 0
        for n, p in self.signature.parameters.items():
            if p.kind is _VAR_POSITIONAL:
                p = p.replace(annotation=_EMPTY)
                for v in arguments.get(n, ()):
                    yield self._bind_param(p, v)
            elif p.kind is _VAR_KEYWORD:
                p = p.replace(annotation=_EMPTY)
                for k, v in arguments.get(n, {}).items():
                    yield self._bind_param(p, v, key=k)
            else:
                yield self._bind_param(p, arguments.get(n, _EMPTY))
            i += 1

    def _bind_param(self, param: Parameter, value=_EMPTY, key=None):
        return BoundParam(param, value, key=key)

    def _evaluate(self, arguments: dict):
        args = []
        kwds = []
        vals = {}
        aw_args = 0
        aw_kwds = 0
        skip_pos = False
        for p in self._iter_bind_params(arguments):
            self._evaluate_param_dependency(p)
            if p.kind in _POSITIONAL_KINDS:
                if skip_pos is False:
                    if p.has_value or p.has_dependency:
                        args.append(p)
                        aw_args += p.is_async
                    else:
                        skip_pos = True
                continue
            elif p.has_value:
                vals[p.key] = p.value
            elif p.has_dependency:
                kwds.append(p)
                aw_kwds += p.is_async


        self.args = tuple(args)
        self.kwds = tuple(kwds)
        self.vals = frozendict(vals)
        self.aw_args = not not aw_args
        self.aw_kwds = not not aw_kwds

    def _evaluate_param_dependency(self, p: BoundParam):
        if not False is p.has_dependency:
            if bound := self.injector.get_bound(p.dependency):
                p.has_dependency = True
                p.is_async = _is_aync_provider(bound)
            
        return p.has_dependency

    def resolve_args(self, ctx: "InjectorContext"):
        return _PositionalDeps(
            (_PARAM_VALUE, p.value) if p.has_value 
                else (_PARAM_CALLABLE, ctx.find(p.dependency, default=p.default_factory))
            for p in self.args
        )

    def resolve_aw_args(self, ctx: "InjectorContext"):
        if self.aw_args:
            aw = []
            args = []
            i = 0
            for p in self.args:
                if p.has_value is True:
                    args.append((_PARAM_VALUE, p.value))
                else:
                    func = ctx.find(p.dependency, default=p.default_factory)
                    if p.is_async:
                        aw.append(i)
                        args.append((_PARAM_AWAITABLE, func))
                    else:
                        args.append((_PARAM_CALLABLE, func))
                i += 1

            return _PositionalDeps(args), tuple(aw)
        else:
            return self.resolve_args(ctx), ()

    def resolve_kwds(self, ctx: "InjectorContext"):
        return _KeywordDeps(
            (p.key, ctx.find(p.dependency, default=p.default_factory))
            for p in self.kwds
        )

    def resolve_aw_kwds(self, ctx: "InjectorContext"):
        if self.aw_kwds:
            aw = []
            return _KeywordDeps(
                kv for p in self.kwds
                    if (kv := (p.key, ctx.find(p.dependency, default=p.default_factory)))
                    and (not p.is_async or aw.append(kv))
            ), tuple(aw)
        else:
            return self.resolve_kwds(ctx), ()
  
    def __call__(self, ctx: 'InjectorContext') -> Callable:
        return self._get_wrapper(ctx)

    def _get_wrapper(self, ctx):
        try:
            fn = self._wrapper_factory
        except AttributeError:
            self._wrapper_factory = fn = self._evaluate_wrapper()
        return fn(self, ctx) 

    def _evaluate_wrapper(self):
        cls = self.__class__
        if not self.signature.parameters:
            if self.aw_call:
                return cls.aw_plain_wrapper
            elif self.aw_call:
                return cls.async_plain_wrapper
            else:
                return cls.plain_wrapper
        elif not self.args:
            if self.aw_kwds:
                return cls.aw_kwds_wrapper  
            elif self.aw_call:
                return cls.async_kwds_wrapper
            else:
                return cls.kwds_wrapper
        elif not self.kwds:
            if self.aw_args:
                return cls.aw_args_wrapper  
            elif self.aw_call:
                return cls.async_args_wrapper
            else:
                return cls.args_wrapper
        else:
            if self.aw_kwds or self.aw_args:
                return cls.aw_args_kwds_wrapper  
            elif self.aw_call:
                return cls.async_args_kwds_wrapper
            else:
                return cls.args_kwds_wrapper

    def plain_wrapper(self, ctx: 'InjectorContext'):
        return self.factory

    def async_plain_wrapper(self, ctx: 'InjectorContext'):
        return self.plain_wrapper(ctx)

    def aw_plain_wrapper(self, ctx: 'InjectorContext'):
        return self.factory

    def args_wrapper(self: Self, ctx: 'InjectorContext'):
        args = self.resolve_args(ctx)
        vals = self.vals
        func = self.factory
        def make():
            nonlocal func, args, vals
            return func(*args, **vals)
        return make

    def async_args_wrapper(self, ctx: 'InjectorContext'):
        return self.args_wrapper(ctx)

    def aw_args_wrapper(self: Self, ctx: 'InjectorContext'):
        args, aw_args = self.resolve_aw_args(ctx)
        return FutureFactoryWrapper(self.factory, self.vals, args=args, aw_args=aw_args, aw_call=self.aw_call)
     
    def kwds_wrapper(self: Self, ctx: 'InjectorContext'):
        kwds = self.resolve_kwds(ctx)
        vals = self.vals
        func = self.factory
        def make():
            nonlocal func, kwds, vals
            return func(**vals, **kwds)
        return make

    def async_kwds_wrapper(self, ctx: 'InjectorContext'):
        return self.kwds_wrapper(ctx)

    def aw_kwds_wrapper(self: Self, ctx: 'InjectorContext'):
        kwds, aw_kwds = self.resolve_aw_kwds(ctx)
        return FutureFactoryWrapper(self.factory, self.vals, kwds=kwds, aw_kwds=aw_kwds, aw_call=self.aw_call)

    def args_kwds_wrapper(self: Self, ctx: 'InjectorContext'):
        args = self.resolve_args(ctx)
        kwds = self.resolve_kwds(ctx)
        vals = self.vals
        func = self.factory
        def make():
            nonlocal func, args, kwds, vals
            return func(*args, **vals, **kwds)
        return make

    def async_args_kwds_wrapper(self, ctx: 'InjectorContext'):
        return self.args_kwds_wrapper(ctx)

    def aw_args_kwds_wrapper(self: Self, ctx: 'InjectorContext'):
        args, aw_args = self.resolve_aw_args(ctx)
        kwds, aw_kwds = self.resolve_aw_kwds(ctx)
        return FutureFactoryWrapper(self.factory, self.vals, args=args, kwds=kwds, aw_args=aw_args, aw_kwds=aw_kwds, aw_call=self.aw_call)
       
       


class SingletonFactoryBinding(FactoryBinding):

    __slots__ = 'thread_safe',

    @t.overload
    def __init__(
        self,
        injector: 'Injector',
        factory: Callable,
        signature: Signature = None,
        *,
        is_async: bool = None,
        arguments: Arguments = None,
        thread_safe: bool=False,
    ): ...

    def __init__(self, *args, thread_safe: bool=False, **kwds):
        self.thread_safe = thread_safe
        super().__init__(*args, **kwds)

    def plain_wrapper(self, ctx: 'InjectorContext'):
        func = self.factory
        value = Missing
        lock = Lock() if self.thread_safe else None
        def make():
            nonlocal func, value
            if value is Missing:
                lock and lock.acquire(blocking=True)
                try:
                    if value is Missing:
                        value = func()
                finally:
                    lock and lock.release()
            return value
        return make

    def async_plain_wrapper(self, ctx: 'InjectorContext'):
        return self.aw_plain_wrapper(ctx)
    
    def aw_plain_wrapper(self, ctx: 'InjectorContext'):
        return FutureSingletonWrapper(self.factory,  aw_call=True, thread_safe=self.thread_safe)

    def args_wrapper(self: Self, ctx: 'InjectorContext'):
        args = self.resolve_args(ctx)
        vals = self.vals
        func = self.factory

        value = Missing
        lock = Lock() if self.thread_safe else None
        def make():
            nonlocal func, value, args, vals
            if value is Missing:
                lock and lock.acquire(blocking=True)
                try:
                    if value is Missing:
                        value = func(*args, **vals)
                finally:
                    lock and lock.release()
            return value
        return make

    def async_args_wrapper(self, ctx: 'InjectorContext'):
        return self.aw_args_wrapper(ctx)

    def aw_args_wrapper(self: Self, ctx: 'InjectorContext'):
        args, aw_args = self.resolve_aw_args(ctx)
        return FutureSingletonWrapper(self.factory, self.vals, args=args, aw_args=aw_args, aw_call=self.aw_call, thread_safe=self.thread_safe)
     
    def kwds_wrapper(self: Self, ctx: 'InjectorContext'):
        kwds = self.resolve_kwds(ctx)
        vals = self.vals
        func = self.factory

        value = Missing
        lock = Lock() if self.thread_safe else None
        def make():
            nonlocal func, value, kwds, vals
            if value is Missing:
                lock and lock.acquire(blocking=True)
                try:
                    if value is Missing:
                        value = func(**kwds, **vals)
                finally:
                    lock and lock.release()
            return value
        return make

    def async_kwds_wrapper(self, ctx: 'InjectorContext'):
        return self.aw_kwds_wrapper(ctx)

    def aw_kwds_wrapper(self: Self, ctx: 'InjectorContext'):
        kwds, aw_kwds = self.resolve_aw_kwds(ctx)
        return FutureSingletonWrapper(self.factory, self.vals, kwds=kwds, aw_kwds=aw_kwds, aw_call=self.aw_call, thread_safe=self.thread_safe)

    def args_kwds_wrapper(self: Self, ctx: 'InjectorContext'):
        args = self.resolve_args(ctx)
        kwds = self.resolve_kwds(ctx)
        vals = self.vals
        func = self.factory

        value = Missing
        lock = Lock() if self.thread_safe else None
        def make():
            nonlocal func, value, args, kwds, vals
            if value is Missing:
                lock and lock.acquire(blocking=True)
                try:
                    if value is Missing:
                        value = func(*args, **kwds, **vals)
                finally:
                    lock and lock.release()
            return value
        return make

    def async_args_kwds_wrapper(self, ctx: 'InjectorContext'):
        return self.aw_args_kwds_wrapper(ctx)

    def aw_args_kwds_wrapper(self: Self, ctx: 'InjectorContext'):
        args, aw_args = self.resolve_aw_args(ctx)
        kwds, aw_kwds = self.resolve_aw_kwds(ctx)
        return FutureSingletonWrapper(self.factory, self.vals, args=args, kwds=kwds, aw_args=aw_args, aw_kwds=aw_kwds, aw_call=self.aw_call, thread_safe=self.thread_safe)
       
       




class CallableFactoryResolver(FactoryBinding):

    __slots__ = ()

    def plain_wrap_func(self, func):
        return lambda: func

    def arg_wrap_func(self, func, args, vals):
        if vals:
            fn = lambda *a, **kw: func(*self.iargs(args, a), **(vals | kw))
        else:
            fn = lambda *a, **kw: func(*self.iargs(args, a), **kw)
        return lambda: fn

    def kwd_wrap_func(self, func, kwds, vals):
        if vals:
            def make(*a, **kw):
                nonlocal self, func, kwds, vals
                kw = vals | kw
                return func(*a, **kw, **self.ikwds(kwds, kw))

            make.is_async = False
        else:
            make = lambda *a, **kw: func(*a, **kw, **self.ikwds(kwds, kw))
        return lambda: make

    def arg_kwd_wrap_func(self, func, args, kwds, vals):
        if vals:

            def make(*a, **kw):
                nonlocal self, func, kwds, vals
                kw = vals | kw
                return func(
                        *self.iargs(args, a),
                        **kw,
                        **self.ikwds(kwds, kw),
                    )

            make.is_async = False

        else:
            make = lambda *a, **kw: func(
                *self.iargs(args, a), **kw, **self.ikwds(kwds, kw)
            )
        return lambda: make





_blank_slice = slice(None, None, None)


_tuple_new = tuple.__new__
_tuple_blank = ()

__base_positional_deps = () if t.TYPE_CHECKING else (tuple,)


class _PositionalDeps(tuple[tuple[_ParamBindType, Callable[[], _T]]], t.Generic[_T]):

    __slots__ = ()
    
    __raw_new__ = classmethod(tuple.__new__)

    def __reduce__(self):
        return tuple, (tuple(self),) 

    def copy(self):
        return self[:]
    __copy__ = copy

    @t.overload
    def __getitem__(self, index: int) -> tuple[_T, bool]: ...
    @t.overload
    def __getitem__(self, slice: slice) -> Self: ...

    def __getitem__(self, index: t.Union[int, slice]) -> t.Union[tuple[_T, bool], Self]:
        bt, item = self.get_raw(index)
        if bt is _PARAM_VALUE:
            return item
        return item()

    def __iter__(self) -> 'Iterator[tuple[_T, bool]]':
        for bt, yv in self.iter_raw():
            if bt is _PARAM_VALUE:
                yield yv
            else:
                yield yv()
            
    if t.TYPE_CHECKING:
        def get_raw(index: int) -> tuple[_ParamBindType, Callable[[], _T]]: ...
        def iter_raw() -> Iterator[tuple[_ParamBindType, Callable[[], _T]]]: ...
    else:
        get_raw = tuple.__getitem__
        iter_raw = tuple.__iter__


   
class _KeywordDeps(dict[str, Callable[[], _T]], t.Generic[_T]):

    __slots__ = ()

    def __reduce__(self):
        return tuple, (tuple(self),) 

    def copy(self):
        return self[:]
    __copy__ = copy

    def __getitem__(self, name: str):
        return self.get_raw(name)()

    def __iter__(self) -> 'Iterator[_T]':
        return self.iter_raw()

    def __reduce__(self):
        return dict, (tuple(self.items()),)

    def copy(self):
        return self.__class__(self)

    __copy__ = copy

    def items(self) -> 'ItemsView[tuple[str, _T]]':
        return ItemsView(self)

    def values(self) -> 'ValuesView[_T]':
        return ValuesView(self)
            
    if t.TYPE_CHECKING:
        def get_raw(name: str) -> Callable[[], _T]: ...
        def iter_raw() -> Iterator[str]: ...
        raw_items = dict[str, Callable[[], _T]].items
        raw_values = dict[str, Callable[[], _T]].values

    iter_raw = dict.__iter__
    get_raw = dict.__getitem__
    raw_items = dict.items
    raw_values = dict.values






class FutureFactoryWrapper:

    __slots__ = '_func', '_args', '_kwds', '_vals', '_aw_args', '_aw_kwds', '_aw_call'

    _func: Callable
    _args: _PositionalDeps
    _kwds: _KeywordDeps
    _vals: Mapping

    def __new__(cls, func, vals: Mapping=frozendict(), args: _PositionalDeps=emptydict(), kwds: _KeywordDeps=emptydict(), *, aw_args: tuple[int]=emptydict(), aw_kwds: tuple[str]=emptydict(), aw_call: bool=True) -> Self:
        self = _object_new(cls)
        self._func = func
        self._vals = vals
        self._args = args
        self._kwds = kwds
        self._aw_args = aw_args
        self._aw_kwds = aw_kwds
        self._aw_call = aw_call
        return self

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}:{self._func.__module__}.{self._func.__qualname__}()'

    def __call__(self):
        if aw_args := self._aw_args:
            _args = self._args
            aw_args = { i: ensure_future(_args[i]) for i in aw_args }
        if aw_kwds := self._aw_kwds:
            aw_kwds = { n: ensure_future(d()) for n, d in aw_kwds }
        
        return FactoryFuture(self, aw_args, aw_kwds)



class FutureSingletonWrapper(FutureFactoryWrapper):

    __slots__ = '__value', '__lock',

    __lock: Lock

    if not t.TYPE_CHECKING:
        def __new__(cls, *args, thread_safe: bool, **kwds) -> Self:
            self = FutureFactoryWrapper.__new__(cls, *args, **kwds)
            self.__value = Missing
            self.__lock = Lock() if thread_safe else None
            return self
        
    def __call__(self):
        if self.__value is Missing:
            if lock := self.__lock:
                lock.acquire(blocking=True)
            try:
                if self.__value is Missing:
                    self.__value = super().__call__()
            finally:
                lock and lock.release()

        return self.__value




class FactoryFuture(Future):

    _asyncio_future_blocking = False
    _loop: AbstractEventLoop
    _factory: FutureFactoryWrapper
    _aws: tuple[dict[int, Future[_T]], dict[str, Future[_T]]]

    def __init__(self, factory, aw_args=emptydict(), aw_kwds=emptydict(), *, loop=None) -> Self:
        Future.__init__(self, loop=loop)
        self._factory = factory
        self._aws = aw_args, aw_kwds
    
    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            factory = self._factory
            aw_args, aw_kwds = self._aws

            if aw_args:
                for k, aw in aw_args.items():
                    aw_args[k] = yield from aw
                _args = factory._args
                args = ((aw_args[i] if i in aw_args else _args[i] for i in range(len(_args))))
            else:
                args = factory._args

            if aw_kwds:
                for k, aw in aw_kwds.items():
                    aw_kwds[k] = yield from aw
            
            res = factory._func(*args, **aw_kwds, **factory._kwds, **factory._vals)
            if factory._aw_call:
                res = yield from ensure_future(res, loop=self._loop)
            self.set_result(res) # res
            return res
        return self.result()

    __iter__ = __await__
