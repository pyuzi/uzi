# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False


import asyncio
from contextlib import AbstractAsyncContextManager
import typing as t
from asyncio import AbstractEventLoop, ensure_future
from asyncio import get_running_loop
from collections.abc import (
    Callable,
    ItemsView,
    Iterator,
    Mapping,
    ValuesView,
)
from enum import Enum
from inspect import Parameter, Signature, iscoroutinefunction
from logging import getLogger
from threading import Lock
from typing_extensions import Self

from .._common.asyncio.futures import Future
from .._common.collections import Arguments, frozendict
from .._common import Missing, typed_signature

from .. import (
    Injectable,
    InjectionMarker,
    is_injectable_annotation,
)

if t.TYPE_CHECKING:
    from ..scopes import Scope
    from ..injectors import Injector
    from ..containers import Container


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




_object_new = object.__new__
_object_setattr = object.__setattr__



def _is_aync_provider(obj) -> bool:
    return getattr(obj, "is_async", False) is True




class _ParamBindType(Enum):
    awaitable: "_ParamBindType" = "awaitable"
    callable: "_ParamBindType" = "callable"
    default: "_ParamBindType" = "default"
    value: "_ParamBindType" = "value"
    none: "_ParamBindType" = None


_PARAM_AWAITABLE = _ParamBindType.awaitable
_PARAM_CALLABLE = _ParamBindType.callable
_PARAM_VALUE = _ParamBindType.value


class BoundParam:

    __slots__ = (
        "param",
        "key",
        "value",
        "injectable",
        "dependency",
        # "default",
        "has_value",
        "has_default",
        "has_dependency",
        "_value_factory",
        "_default_factory",
        "_bind_type",
        "is_async",
    )

    param: Parameter
    name: str
    annotation: t.Any
    value: _T
    default: t.Any
    injectable: Injectable
    dependency: Injectable
    is_async: bool
    has_value: bool
    has_dependency: bool

    # _aw_value: 'AwaitValue'
    # _aw_default: 'AwaitValue'

    def __new__(
        cls, param: Parameter, value: t.Any = _EMPTY, key: t.Union[str, int] = None
    ):
        self = object.__new__(cls)
        self.param = param
        self.key = key or param.name
        self.dependency = None
        self.has_value = self.is_async = self.has_default = self.has_dependency = False

        if isinstance(value, InjectionMarker):
            self.injectable = value
            self.has_dependency = True
        elif not value is _EMPTY:
            self.has_value = True
            self.value = value

        if isinstance(param.default, InjectionMarker):
            if self.has_dependency is False:
                self.injectable = param.default
                self.has_dependency = True
        else:
            self.has_default = not param.default is _EMPTY

        if False is self.has_dependency:
            annotation = param.annotation
            if is_injectable_annotation(annotation):
                self.injectable = annotation
                self.has_dependency = isinstance(annotation, InjectionMarker) or None

        return self

    @property
    def name(self):
        return self.param.name

    @property
    def bind_type(self):
        try:
            return self._bind_type
        except AttributeError:
            if self.has_value:
                self._bind_type = _PARAM_VALUE
            elif self.is_async:
                self._bind_type = _PARAM_AWAITABLE
            elif self.has_dependency:
                self._bind_type = _PARAM_CALLABLE
            elif self.has_default:
                self._bind_type = _ParamBindType.default
            else:
                self._bind_type = _ParamBindType.none
            return self._bind_type

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
                raise AttributeError(f"`value`") from e
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
                raise AttributeError(f"`default_factory`")
            return self._default_factory


class FactoryBinding:

    __slots__ = (
        "factory",
        "signature",
        "container",
        "decorators",
        "scope",
        "args",
        "aw_call",
        "aw_args",
        "aw_kwds",
        "kwds",
        "deps",
        "vals",
        "_pos_vals",
        "_pos_deps",
        "_wrapper_method",
    )

    factory: Callable
    scope: "Scope"
    container: 'Container'
    arguments: dict[str, t.Any]
    signature: Signature
    decorators: list[Callable[[Callable], Callable]]

    # aws: frozenorderedset[BoundParam]
    deps: frozenset[BoundParam]
    args: tuple[BoundParam]
    aw_args: tuple[int]
    kwds: tuple[BoundParam]
    aw_kwds: tuple[str]
    vals: frozendict[str, t.Any]
    aw_call: bool

    def __init__(
        self,
        scope: "Scope",
        factory: Callable,
        container: t.Union['Container', None]=None,
        signature: Signature = None,
        *,
        is_async: bool = None,
        arguments: Arguments = None,
    ):
        self.factory = factory
        self.scope = scope
        self.container = container
        self.aw_call = iscoroutinefunction(factory) if is_async is None else is_async
        self.signature = signature or typed_signature(factory)
        self._evaluate(self._parse_arguments(arguments))

    @property
    def is_async(self):
        return self.aw_call or not not (self.aw_kwds or self.aw_args)

    @property
    def dependencies(self):
        return {
            p.dependency for _ in (self.args, self.kwds) for p in _ if p.has_dependency
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
        aw_args = []
        aw_kwds = []
        pos_vals = pos_deps = i = 0
        skip_pos = False
        for p in self._iter_bind_params(arguments):
            self._evaluate_param_dependency(p)
            if p.kind in _POSITIONAL_KINDS:
                if skip_pos is False:
                    if p.has_value or p.has_dependency:
                        args.append(p)
                        p.is_async and aw_args.append(i)
                        pos_vals += p.has_value
                        pos_deps += not not p.has_dependency and not p.has_value
                    else:
                        skip_pos = True
                    i += 1
                continue
            elif p.has_value:
                vals[p.key] = p.value
            elif p.has_dependency:
                kwds.append(p)
                p.is_async and aw_kwds.append(p.key)

        self.args = tuple(args)
        self.kwds = tuple(kwds)
        self.vals = frozendict(vals)
        self._pos_vals = pos_vals
        self._pos_deps = pos_deps
        self.aw_args = tuple(aw_args)
        self.aw_kwds = tuple(aw_kwds)

    def _evaluate_param_dependency(self, p: BoundParam):
        if not False is p.has_dependency:
            dep = p.dependency = self.scope.resolve_dependency(p.injectable, self.container)
            if bound := dep and self.scope[dep:]:
                p.has_dependency = True
                p.is_async = _is_aync_provider(bound)

        return p.has_dependency

    def resolve_args(self, ctx: "Injector"):
        if self.args:
            if self._pos_vals > 0 < self._pos_deps:
                return _PositionalArgs(
                    (
                        p.bind_type,
                        p.value
                        if p.bind_type is _PARAM_VALUE
                        else ctx.find(p.dependency, default=p.default_factory),
                    )
                    for p in self.args
                )
            elif self._pos_deps > 0:
                return _PositionalDeps(
                    ctx.find(p.dependency, default=p.default_factory) for p in self.args
                )
            else:
                return tuple(p.value for p in self.args)
        return ()

    def resolve_aw_args(self, ctx: "Injector"):
        return self.resolve_args(ctx), self.aw_args

    def resolve_kwds(self, ctx: "Injector"):
        return _KeywordDeps(
            (p.key, ctx.find(p.dependency, default=p.default_factory))
            for p in self.kwds
        )

    def resolve_aw_kwds(self, ctx: "Injector"):
        if self.aw_kwds:
            deps = self.resolve_kwds(ctx)
            return deps, tuple((n, deps.pop(n)) for n in self.aw_kwds)
        else:
            return self.resolve_kwds(ctx), ()

    def __call__(self, ctx: "Injector") -> Callable:
        return self.make_wrapper(ctx)

    if t.TYPE_CHECKING:
        def make_wrapper(self, ctx: "Injector") -> Callable:
            ...

    @property
    def make_wrapper(self):
        try:
            return self._wrapper_method
        except AttributeError:
            self._wrapper_method = self._evaluate_make_wrapper()
            return self._wrapper_method

    def _evaluate_make_wrapper(self):
        meth = self._evaluate_wrapper_method()
        return lambda ctx: meth(self, ctx)

    def _evaluate_wrapper_method(self):
        cls = self.__class__
        if not self.signature.parameters:
            if self.is_async:
                return cls.async_plain_wrapper
            else:
                return cls.plain_wrapper
        elif not self.args:
            if self.aw_kwds:
                return cls.aw_kwds_wrapper
            elif self.is_async:
                return cls.async_kwds_wrapper
            else:
                return cls.kwds_wrapper
        elif not self.kwds:
            if self.aw_args:
                return cls.aw_args_wrapper
            elif self.is_async:
                return cls.async_args_wrapper
            else:
                return cls.args_wrapper
        else:
            if self.aw_kwds or self.aw_args:
                return cls.aw_args_kwds_wrapper
            elif self.is_async:
                return cls.async_args_kwds_wrapper
            else:
                return cls.args_kwds_wrapper

    def make_future_wrapper(self: Self, ctx: 'Injector', **kwds):
        kwds.setdefault("aw_call", self.aw_call)
        return FutureFactoryWrapper(self.factory, self.vals, **kwds)

    def plain_wrapper(self, ctx: "Injector"):
        return self.factory

    def async_plain_wrapper(self, ctx: "Injector"):
        return self.plain_wrapper(ctx)

    def args_wrapper(self: Self, ctx: "Injector"):
        args = self.resolve_args(ctx)
        vals = self.vals
        func = self.factory
        return lambda: func(*args, **vals)

    def async_args_wrapper(self, ctx: "Injector"):
        return self.args_wrapper(ctx)

    def aw_args_wrapper(self: Self, ctx: "Injector"):
        args, aw_args = self.resolve_aw_args(ctx)
        return self.make_future_wrapper(ctx, args=args, aw_args=aw_args)

    def kwds_wrapper(self: Self, ctx: "Injector"):
        kwds = self.resolve_kwds(ctx)
        vals = self.vals
        func = self.factory
        return lambda: func(**kwds, **vals)

    def async_kwds_wrapper(self, ctx: "Injector"):
        return self.kwds_wrapper(ctx)

    def aw_kwds_wrapper(self: Self, ctx: "Injector"):
        kwds, aw_kwds = self.resolve_aw_kwds(ctx)
        return self.make_future_wrapper(ctx, kwds=kwds, aw_kwds=aw_kwds)

    def args_kwds_wrapper(self: Self, ctx: "Injector"):
        args = self.resolve_args(ctx)
        kwds = self.resolve_kwds(ctx)
        vals = self.vals
        func = self.factory
        return lambda: func(*args, **kwds, **vals)

    def async_args_kwds_wrapper(self, ctx: "Injector"):
        return self.args_kwds_wrapper(ctx)

    def aw_args_kwds_wrapper(self: Self, ctx: "Injector"):
        args, aw_args = self.resolve_aw_args(ctx)
        kwds, aw_kwds = self.resolve_aw_kwds(ctx)
        return self.make_future_wrapper(
            ctx, args=args, kwds=kwds, aw_args=aw_args, aw_kwds=aw_kwds
        )




class SingletonFactoryBinding(FactoryBinding):

    __slots__ = ("thread_safe",)

    @t.overload
    def __init__(
        self,
        scope: "Scope",
        factory: Callable,
        container: 'Container' = None,
        signature: Signature = None,
        *,
        is_async: bool = None,
        arguments: Arguments = None,
        thread_safe: bool = False,
    ):
        ...

    def __init__(self, *args, thread_safe: bool = False, **kwds):
        self.thread_safe = thread_safe
        super().__init__(*args, **kwds)

    def __call__(self, ctx: "Injector") -> Callable:
        func = self.make_wrapper(ctx)
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

    def async_plain_wrapper(self, ctx: "Injector"):
        return self.make_future_wrapper(ctx)

    def async_args_wrapper(self, ctx: "Injector"):
        return self.aw_args_wrapper(ctx)

    def async_kwds_wrapper(self, ctx: "Injector"):
        return self.aw_kwds_wrapper(ctx)

    def async_args_kwds_wrapper(self, ctx: "Injector"):
        return self.aw_args_kwds_wrapper(ctx)





class ResourceFactoryBinding(SingletonFactoryBinding):

    __slots__ = ('aw_enter',)

    @t.overload
    def __init__(
        self,
        injector: "Scope",
        factory: Callable,
        container: 'Container' = None,
        signature: Signature = None,
        *,
        is_async: bool = None,
        arguments: Arguments = None,
        aw_enter: bool = None,
        thread_safe: bool = False,
    ):
        ...

    @property
    def is_async(self):
        return super().is_async or not not self.aw_enter

    def __init__(self, *args, aw_enter: bool = None, **kwds):
        self.aw_enter = aw_enter
        super().__init__(*args, **kwds)

    def __call__(self, ctx: "Injector") -> Callable:
        func = self.make_wrapper(ctx)
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

    def make_future_wrapper(self: Self, ctx: 'Injector', **kwds):
        kwds.setdefault("aw_call", self.aw_call)
        kwds.setdefault("aw_enter", self.aw_enter)
        return FutureResourceWrapper(ctx, self.factory, self.vals, **kwds)

    def _sync_enter_context_wrap(self, ctx: 'Injector', func):
        return lambda: ctx.exitstack.enter(func())

    def plain_wrapper(self, ctx: "Injector"):
        return self._sync_enter_context_wrap(ctx, super().plain_wrapper(ctx))

    def args_wrapper(self: Self, ctx: "Injector"):
        return self._sync_enter_context_wrap(ctx, super().args_wrapper(ctx))
   
    def kwds_wrapper(self: Self, ctx: "Injector"):
        return self._sync_enter_context_wrap(ctx, super().kwds_wrapper(ctx))

    def args_kwds_wrapper(self: Self, ctx: "Injector"):
        return self._sync_enter_context_wrap(ctx, super().args_kwds_wrapper(ctx))




class PartialFactoryBinding(FactoryBinding):

    __slots__ = ()

    def make_future_wrapper(self: Self, ctx: 'Injector',  **kwds):
        kwds.setdefault("aw_call", self.aw_call)
        return FutureCallableWrapper(self.factory, self.vals, **kwds)

    def plain_wrapper(self, ctx: "Injector"):
        return self.factory

    def args_wrapper(self: Self, ctx: "Injector"):
        args = self.resolve_args(ctx)
        vals = self.vals
        func = self.factory

        def make(*a, **kw):
            nonlocal func, args, vals
            return func(*args, *a, **(vals | kw))

        return make

    def kwds_wrapper(self: Self, ctx: "Injector"):
        kwds = self.resolve_kwds(ctx)
        vals = self.vals
        func = self.factory

        def make(*a, **kw):
            nonlocal func, kwds, vals
            return func(*a, **(vals | kw), **kwds.skip(kw))

        return make

    def args_kwds_wrapper(self: Self, ctx: "Injector"):
        args = self.resolve_args(ctx)
        kwds = self.resolve_kwds(ctx)
        vals = self.vals
        func = self.factory

        def make(*a, **kw):
            nonlocal func, args, kwds, vals
            return func(*args, *a, **(vals | kw), **kwds.skip(kw))

        return make
    
    


class CallableFactoryBinding(PartialFactoryBinding):

    __slots__ = ()

    def plain_wrapper(self, ctx: "Injector"):
        make = super().plain_wrapper(ctx)
        return lambda: make

    def args_wrapper(self: Self, ctx: "Injector"):
        make = super().args_wrapper(ctx)
        return lambda: make

    def aw_args_wrapper(self: Self, ctx: "Injector"):
        make = super().aw_args_wrapper(ctx)
        return lambda: make

    def kwds_wrapper(self: Self, ctx: "Injector"):
        make = super().kwds_wrapper(ctx)
        return lambda: make

    def aw_kwds_wrapper(self: Self, ctx: "Injector"):
        make = super().aw_kwds_wrapper(ctx)
        return lambda: make

    def args_kwds_wrapper(self: Self, ctx: "Injector"):
        make = super().args_kwds_wrapper(ctx)
        return lambda: make

    def aw_args_kwds_wrapper(self: Self, ctx: "Injector"):
        make = super().aw_args_kwds_wrapper(ctx)
        return lambda: make
























class _PositionalArgs(tuple[tuple[_ParamBindType, Callable[[], _T]]], t.Generic[_T]):

    __slots__ = ()

    __raw_new__ = classmethod(tuple.__new__)

    def __reduce__(self):
        return tuple, (tuple(self),)

    def copy(self):
        return self[:]

    __copy__ = copy

    @t.overload
    def __getitem__(self, index: int) -> tuple[_T, bool]:
        ...

    @t.overload
    def __getitem__(self, slice: slice) -> Self:
        ...

    def __getitem__(self, index: t.Union[int, slice]) -> t.Union[tuple[_T, bool], Self]:
        bt, item = self.get_raw(index)
        if bt is _PARAM_VALUE:
            return item
        return item()

    def __iter__(self) -> "Iterator[tuple[_T, bool]]":
        for bt, yv in self.iter_raw():
            if bt is _PARAM_VALUE:
                yield yv
            else:
                yield yv()

    if t.TYPE_CHECKING:

        def get_raw(index: int) -> tuple[_ParamBindType, Callable[[], _T]]:
            ...

        def iter_raw() -> Iterator[tuple[_ParamBindType, Callable[[], _T]]]:
            ...

    else:
        get_raw = tuple.__getitem__
        iter_raw = tuple.__iter__


class _PositionalDeps(_PositionalArgs):
    __slots__ = ()

    def __getitem__(self, index: t.Union[int, slice]) -> t.Union[tuple[_T, bool], Self]:
        return self.get_raw(index)()

    def __iter__(self) -> "Iterator[tuple[_T, bool]]":
        for yv in self.iter_raw():
            yield yv()


class _KeywordDeps(dict[str, Callable[[], _T]], t.Generic[_T]):

    __slots__ = ()

    def __getitem__(self, name: str):
        return self.get_raw(name)()

    def __iter__(self) -> "Iterator[_T]":
        return self.iter_raw()

    def __reduce__(self):
        return dict, (tuple(self.items()),)

    def copy(self):
        return self.__class__(self)

    __copy__ = copy

    def items(self) -> "ItemsView[tuple[str, _T]]":
        return ItemsView(self)

    def values(self) -> "ValuesView[_T]":
        return ValuesView(self)

    def skip(self, skip: Mapping[str, t.Any]):
        if skip:
            return {k: self.get_raw(k)() for k in self.iter_raw() if not k in skip}
        else:
            return self

    iter_raw = dict.__iter__
    get_raw = dict.__getitem__
    raw_items = dict.items
    raw_values = dict.values







class FutureFactoryWrapper:

    __slots__ = "_func", "_args", "_kwds", "_vals", "_aw_args", "_aw_kwds", "_aw_call"

    _func: Callable
    _args: '_PositionalArgs'
    _kwds: '_KeywordDeps'
    _vals: Mapping

    def __new__(
        cls,
        func,
        vals: Mapping = frozendict(),
        args: '_PositionalArgs' = frozendict(),
        kwds: '_KeywordDeps' = frozendict(),
        *,
        aw_args: tuple[int] = frozendict(),
        aw_kwds: tuple[str] = frozendict(),
        aw_call: bool = True,
    ) -> Self:
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
        return f"{self.__class__.__name__}:{self._func.__module__}.{self._func.__qualname__}()"

    def __call__(self):
        loop = get_running_loop()
        if aw_args := self._aw_args:
            _args = self._args
            aw_args = {i: ensure_future(_args[i], loop=loop) for i in aw_args}
        if aw_kwds := self._aw_kwds:
            aw_kwds = {n: ensure_future(d(), loop=loop) for n, d in aw_kwds}

        return FactoryFuture(self, aw_args, aw_kwds, loop=loop)




class FutureCallableWrapper(FutureFactoryWrapper):

    __slots__ = ()

    def __call__(self, *a, **kw):
        loop = get_running_loop()
        if aw_args := self._aw_args:
            _args = self._args
            aw_args = {i: ensure_future(_args[i], loop=loop) for i in aw_args}
        if aw_kwds := self._aw_kwds:
            aw_kwds = {n: ensure_future(d(), loop=loop) for n, d in aw_kwds if not n in kw}

        return CallableFuture(self, aw_args, aw_kwds, args=a, kwds=kw, loop=loop)




class FutureResourceWrapper(FutureFactoryWrapper):

    __slots__ = ('_aw_enter', '_ctx',)

    _aw_enter: bool
    _ctx: 'Injector'

    if not t.TYPE_CHECKING:
        def __new__(cls, ctx,  *args, aw_enter: bool=None, **kwds):
            self = super().__new__(cls, *args, **kwds)
            self._ctx = ctx
            self._aw_enter = aw_enter
            return self

    def __call__(self, *a, **kw):
        loop = get_running_loop()
        if aw_args := self._aw_args:
            _args = self._args
            aw_args = {i: ensure_future(_args[i], loop=loop) for i in aw_args}
        if aw_kwds := self._aw_kwds:
            aw_kwds = {n: ensure_future(d(), loop=loop) for n, d in aw_kwds}

        return ResourceFuture(self, aw_args, aw_kwds, loop=loop)






class FactoryFuture(Future):

    _asyncio_future_blocking = False
    _loop: AbstractEventLoop
    _factory: FutureFactoryWrapper
    _aws: tuple[dict[int, Future[_T]], dict[str, Future[_T]]]
    # _aws: tuple[Future[_T], dict[str, Future[_T]]]

    def __init__(
        self, factory, aw_args=frozendict(), aw_kwds=frozendict(), *, loop=None
    ) -> Self:
        Future.__init__(self, loop=loop)
        self._factory = factory
        self._aws = aw_args, aw_kwds

    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            factory = self._factory
            aw_args, aw_kwds = self._aws

            if aw_args:
                for k in aw_args:
                    aw_args[k] = yield from aw_args[k]
                _args = factory._args
                args = (
                    aw_args[i] if i in aw_args else _args[i] for i in range(len(_args))
                )
            else:
                args = factory._args

            if aw_kwds:
                for k in aw_kwds:
                    aw_kwds[k] = yield from aw_kwds[k]

            res = factory._func(*args, **aw_kwds, **factory._kwds, **factory._vals)
            if factory._aw_call:
                res = yield from ensure_future(res, loop=self._loop)
            self.set_result(res)  # res
            return res
        return self.result()

    __iter__ = __await__



class CallableFuture(Future):

    _asyncio_future_blocking = False
    _loop: AbstractEventLoop
    _factory: FutureCallableWrapper
    _aws: tuple[dict[int, Future[_T]], dict[str, Future[_T]]]
    # _aws: tuple[Future[_T], dict[str, Future[_T]]]
    _extra_args: tuple[t.Any]
    _extra_kwds: Mapping[str, t.Any]

    def __init__(
        self,
        factory,
        aw_args=frozendict(),
        aw_kwds=frozendict(),
        *,
        args: tuple = (),
        kwds: dict[str, t.Any]=frozendict(),
        loop=None,
    ) -> Self:
        Future.__init__(self, loop=loop)
        self._factory = factory
        self._aws = aw_args, aw_kwds
        self._extra_args = args
        self._extra_kwds = kwds

    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            factory = self._factory
            aw_args, aw_kwds = self._aws

            if aw_args:
                for k in aw_args:
                    aw_args[k] = yield from aw_args[k]
                _args = factory._args
                args = (
                    aw_args[i] if i in aw_args else _args[i] for i in range(len(_args))
                )
            else:
                args = factory._args

            if aw_kwds:
                for k, aw in aw_kwds.items():
                    aw_kwds[k] = yield from aw_kwds[k]

            if kwds := self._extra_kwds:
                vals = factory._vals | kwds
                kwds = factory._kwds.skip(kwds)
            else:
                vals = factory._vals
                kwds = factory._kwds

            res = factory._func(*args, *self._extra_args, **aw_kwds, **kwds, **vals)
            if factory._aw_call:
                res = yield from ensure_future(res, loop=self._loop)
            self.set_result(res)  # res
            return res
        return self.result()

    __iter__ = __await__



class ResourceFuture(Future):

    _asyncio_future_blocking = False
    _loop: AbstractEventLoop
    _factory: FutureResourceWrapper
    _aws: tuple[dict[int, Future[_T]], dict[str, Future[_T]]]
    # _aws: tuple[Future[_T], dict[str, Future[_T]]]
    _extra_args: tuple[t.Any]
    _extra_kwds: Mapping[str, t.Any]

    def __init__(
        self,
        factory,
        aw_args=frozendict(),
        aw_kwds=frozendict(),
        *,
        args: tuple = (),
        kwds: dict[str, t.Any]=frozendict(),
        loop=None,
    ) -> Self:
        Future.__init__(self, loop=loop)
        self._factory = factory
        self._aws = aw_args, aw_kwds
        self._extra_args = args
        self._extra_kwds = kwds

    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            factory = self._factory
            aw_args, aw_kwds = self._aws

            if aw_args:
                for k in aw_args:
                    aw_args[k] = yield from aw_args[k]
                _args = factory._args
                args = (
                    aw_args[i] if i in aw_args else _args[i] for i in range(len(_args))
                )
            else:
                args = factory._args

            if aw_kwds:
                for k, aw in aw_kwds.items():
                    aw_kwds[k] = yield from aw_kwds[k]

            if kwds := self._extra_kwds:
                vals = factory._vals | kwds
                kwds = factory._kwds.skip(kwds)
            else:
                vals = factory._vals
                kwds = factory._kwds

            res = factory._func(*args, *self._extra_args, **aw_kwds, **kwds, **vals)
            if factory._aw_call:
                res = yield from ensure_future(res, loop=self._loop)

            aw_enter = factory._aw_enter
            cm = factory._ctx.exitstack
            if aw_enter is False:
                res = cm.enter(res)
            elif aw_enter is True:
                res = yield from self._loop.create_task(cm.enter_async(res))
            elif isinstance(res, AbstractAsyncContextManager):
                factory._aw_enter = True
                res = yield from self._loop.create_task(cm.enter_async(res))
            else:
                factory._aw_enter = False
                res = cm.enter(res)

            self.set_result(res)  # res
            return res
        return self.result()

    __iter__ = __await__
