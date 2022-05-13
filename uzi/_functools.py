import typing as t
from asyncio import AbstractEventLoop, Future, ensure_future, get_running_loop
from collections.abc import Callable, ItemsView, Iterator, Mapping, ValuesView
from contextlib import AbstractAsyncContextManager
from inspect import Parameter, Signature
from logging import getLogger

import attr
from typing_extensions import Self

from uzi._common import FrozenDict

from .markers import Injectable, is_injectable_annotation
from .markers import DependencyMarker

if t.TYPE_CHECKING:  # pragma: no cover
    from .graph.nodes import Node
    from .containers import Container
    from .injectors import Injector
    from .graph.core import Graph


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


_frozendict = FrozenDict()


_object_new = object.__new__
_object_setattr = object.__setattr__


class BoundParam:
    """A bound param"""

    __slots__ = (
        "param",
        "key",
        "value",
        "injectable",
        "dependency",
        "has_default",
    )

    param: Parameter
    name: str
    annotation: t.Any
    value: _T
    default: t.Any
    injectable: Injectable
    dependency: "Node"

    def __new__(
        cls, param: Parameter, value: t.Any = _EMPTY, key: t.Union[str, int] = None
    ):
        self = object.__new__(cls)
        self.param = param
        self.key = key or param.name
        self.dependency = self.injectable = None
        self.has_default = False

        if isinstance(value, DependencyMarker):
            self.injectable = value
        elif not value is _EMPTY:
            self.value = value

        if isinstance(param.default, DependencyMarker):
            if None is self.injectable:
                self.injectable = param.default
        else:
            self.has_default = not param.default is _EMPTY

        if None is self.injectable:
            annotation = param.annotation
            if not annotation is _EMPTY and is_injectable_annotation(annotation):
                self.injectable = annotation

        return self

    @property
    def name(self):
        return self.param.name

    @property
    def is_async(self):
        if dep := self.dependency:
            return dep.is_async

    @property
    def is_injectable(self):
        return not self.injectable is None

    @property
    def has_value(self):
        return hasattr(self, "value")

    @property
    def default(self):
        return self.param.default

    @property
    def annotation(self):
        return self.param.annotation

    @property
    def kind(self):
        return self.param.kind


@attr.s(slots=True, frozen=True)
class BoundParams:
    """A collection of bound params"""

    params: tuple[BoundParam] = attr.ib(converter=tuple)

    args: tuple[BoundParam] = attr.ib(converter=tuple, kw_only=True)
    aw_args: tuple[int] = attr.ib(converter=tuple)
    kwds: tuple[BoundParam] = attr.ib(converter=tuple)
    aw_kwds: tuple[str] = attr.ib(converter=tuple)
    is_async: bool = attr.ib()
    vals: FrozenDict[str, t.Any] = attr.ib(converter=FrozenDict)
    _pos_vals: int = attr.ib(converter=int)
    _pos_deps: int = attr.ib(converter=int)

    @property
    def dependencies(self) -> set["Node"]:
        return dict.fromkeys(p.dependency for p in self.params if p.dependency).keys()

    @classmethod
    def make(cls, params: tuple[BoundParam]) -> None:
        args = []
        kwds = []
        vals = {}
        aw_args = []
        aw_kwds = []
        pos_vals = pos_deps = i = 0
        skip_pos = False

        params = tuple(params)
        for p in params:
            if p.kind in _POSITIONAL_KINDS:
                if skip_pos is False:
                    if p.has_value or p.dependency:
                        args.append(p)
                        p.is_async and aw_args.append(i)
                        pos_vals += p.has_value
                        pos_deps += not not p.dependency and not p.has_value
                    else:
                        skip_pos = True
                    i += 1
                continue
            elif p.has_value:
                vals[p.key] = p.value
            elif p.dependency:
                kwds.append(p)
                p.is_async and aw_kwds.append(p.key)
        return cls(
            params=params,
            args=args,
            kwds=kwds,
            vals=vals,
            pos_vals=pos_vals,
            pos_deps=pos_deps,
            aw_args=aw_args,
            aw_kwds=aw_kwds,
            is_async=not not (aw_args or aw_kwds),
        )

    @classmethod
    def bind(
        cls,
        sig: Signature,
        scope: "Graph" = None,
        container: "Container" = None,
        args: tuple = (),
        kwargs: dict = FrozenDict(),
    ) -> Self:
        return cls.make(cls._iter_bind(sig, scope, container, args, kwargs))

    @classmethod
    def _iter_bind(
        cls,
        sig: Signature,
        scope: "Graph" = None,
        container: "Container" = None,
        args=(),
        kwargs=FrozenDict(),
    ):
        bound = sig.bind_partial(*args, **kwargs).arguments
        container = container or scope.container
        for n, p in sig.parameters.items():
            if p.kind is Parameter.VAR_POSITIONAL:
                p = p.replace(annotation=Parameter.empty)
                for v in bound.get(n) or (Parameter.empty,):
                    bp = BoundParam(p, v)
                    if scope and bp.is_injectable:
                        bp.dependency = scope[bp.injectable]
                    yield bp
            elif p.kind is Parameter.VAR_KEYWORD:
                p = p.replace(annotation=Parameter.empty)
                for k, v in (bound.get(n) or {n: Parameter.empty}).items():
                    bp = BoundParam(p, v, key=k)
                    if scope and bp.is_injectable:
                        bp.dependency = scope[bp.injectable]
                    yield bp
            else:
                bp = BoundParam(p, bound.get(n, Parameter.empty))
                if scope and bp.is_injectable:
                    bp.dependency = scope[bp.injectable]
                yield bp

    def __bool__(self):
        return not not self.params


class _PositionalArgs(tuple[tuple[t.Any, Callable[[], _T]]], t.Generic[_T]):

    __slots__ = ()

    __raw_new__ = classmethod(tuple.__new__)

    # def __reduce__(self): return tuple, (tuple(self),)

    def copy(self):
        return self[:]

    __copy__ = copy

    @t.overload
    def __getitem__(self, index: int) -> tuple[_T, bool]:
        ...  # pragma: no cover

    @t.overload
    def __getitem__(self, slice: slice) -> Self:
        ...  # pragma: no cover

    def __getitem__(self, index: t.Union[int, slice]) -> t.Union[tuple[_T, bool], Self]:
        v, fn = self.get_raw(index)
        if not fn:
            return v
        return fn()

    def __iter__(self) -> "Iterator[tuple[_T, bool]]":
        for v, fn in self.iter_raw():
            if not fn:
                yield v
            else:
                yield fn()

    if t.TYPE_CHECKING:  # pragma: no cover

        def get_raw(index: int) -> tuple[t.Any, Callable[[], _T]]:
            ...  # pragma: no cover

        def iter_raw() -> Iterator[tuple[t.Any, Callable[[], _T]]]:
            ...  # pragma: no cover

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

    __slots__ = (
        "_func",
        "_args",
        "_kwargs",
        "_vals",
        "_aw_args",
        "_aw_kwargs",
        "_aw_call",
    )

    _func: Callable
    _args: "_PositionalArgs"
    _kwargs: "_KeywordDeps"
    _vals: Mapping

    def __new__(
        cls,
        func,
        vals: Mapping = FrozenDict(),
        args: "_PositionalArgs" = FrozenDict(),
        kwargs: "_KeywordDeps" = FrozenDict(),
        *,
        aw_args: tuple[int] = FrozenDict(),
        aw_kwargs: tuple[str] = FrozenDict(),
        aw_call: bool = True,
    ) -> Self:
        self = _object_new(cls)
        self._func = func
        self._vals = vals
        self._args = args
        self._kwargs = kwargs
        self._aw_args = aw_args
        self._aw_kwargs = aw_kwargs
        self._aw_call = aw_call
        return self

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}:{self._func.__module__}.{self._func.__qualname__}()"

    def __call__(self):
        loop = get_running_loop()
        if aw_args := self._aw_args:
            _args = self._args
            aw_args = {i: ensure_future(_args[i], loop=loop) for i in aw_args}
        if aw_kwargs := self._aw_kwargs:
            aw_kwargs = {n: ensure_future(d(), loop=loop) for n, d in aw_kwargs}

        return FactoryFuture(self, aw_args, aw_kwargs, loop=loop)


class FutureCallableWrapper(FutureFactoryWrapper):

    __slots__ = ()

    def __call__(self, *a, **kw):
        loop = get_running_loop()
        if aw_args := self._aw_args:
            _args = self._args
            aw_args = {i: ensure_future(_args[i], loop=loop) for i in aw_args}
        if aw_kwargs := self._aw_kwargs:
            aw_kwargs = {
                n: ensure_future(d(), loop=loop) for n, d in aw_kwargs if not n in kw
            }

        return CallableFuture(self, aw_args, aw_kwargs, args=a, kwargs=kw, loop=loop)


class FutureResourceWrapper(FutureFactoryWrapper):  # pragma: no cover

    __slots__ = (
        "_aw_enter",
        "_ctx",
    )

    _aw_enter: bool
    _ctx: "Injector"

    if not t.TYPE_CHECKING:  # pragma: no cover

        def __new__(cls, ctx, *args, aw_enter: bool = None, **kwargs):
            self = super().__new__(cls, *args, **kwargs)
            self._ctx = ctx
            self._aw_enter = aw_enter
            return self

    def __call__(self, *a, **kw):
        loop = get_running_loop()
        if aw_args := self._aw_args:
            _args = self._args
            aw_args = {i: ensure_future(_args[i], loop=loop) for i in aw_args}
        if aw_kwargs := self._aw_kwargs:
            aw_kwargs = {n: ensure_future(d(), loop=loop) for n, d in aw_kwargs}

        return ResourceFuture(self, aw_args, aw_kwargs, loop=loop)


class FactoryFuture(Future):

    _asyncio_future_blocking = False
    _loop: AbstractEventLoop
    _factory: FutureFactoryWrapper
    _aws: tuple[dict[int, Future[_T]], dict[str, Future[_T]]]
    # _aws: tuple[Future[_T], dict[str, Future[_T]]]

    def __init__(
        self, factory, aw_args=FrozenDict(), aw_kwargs=FrozenDict(), *, loop=None
    ) -> Self:
        Future.__init__(self, loop=loop)
        self._factory = factory
        self._aws = aw_args, aw_kwargs

    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            factory = self._factory
            aw_args, aw_kwargs = self._aws

            if aw_args:
                for k in aw_args:
                    aw_args[k] = yield from aw_args[k]
                _args = factory._args
                args = (
                    aw_args[i] if i in aw_args else _args[i] for i in range(len(_args))
                )
            else:
                args = factory._args

            if aw_kwargs:
                for k in aw_kwargs:
                    aw_kwargs[k] = yield from aw_kwargs[k]
            else:
                aw_kwargs = _frozendict

            res = factory._func(*args, **aw_kwargs, **factory._kwargs, **factory._vals)
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
    _extra_kwargs: Mapping[str, t.Any]

    def __init__(
        self,
        factory,
        aw_args=FrozenDict(),
        aw_kwargs=FrozenDict(),
        *,
        args: tuple = (),
        kwargs: dict[str, t.Any] = FrozenDict(),
        loop=None,
    ) -> Self:
        Future.__init__(self, loop=loop)
        self._factory = factory
        self._aws = aw_args, aw_kwargs
        self._extra_args = args
        self._extra_kwargs = kwargs

    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            factory = self._factory
            aw_args, aw_kwargs = self._aws

            if aw_args:
                for k in aw_args:
                    aw_args[k] = yield from aw_args[k]
                _args = factory._args
                args = (
                    aw_args[i] if i in aw_args else _args[i] for i in range(len(_args))
                )
            else:
                args = factory._args

            if aw_kwargs:
                for k, aw in aw_kwargs.items():
                    aw_kwargs[k] = yield from aw_kwargs[k]

            if kwargs := self._extra_kwargs:
                vals = factory._vals | kwargs
                kwargs = factory._kwargs.skip(kwargs)
            else:
                vals = factory._vals
                kwargs = factory._kwargs

            res = factory._func(*args, *self._extra_args, **aw_kwargs, **kwargs, **vals)
            if factory._aw_call:
                res = yield from ensure_future(res, loop=self._loop)
            self.set_result(res)  # res
            return res
        return self.result()

    __iter__ = __await__


class ResourceFuture(Future):  # pragma: no cover

    _asyncio_future_blocking = False
    _loop: AbstractEventLoop
    _factory: FutureResourceWrapper
    _aws: tuple[dict[int, Future[_T]], dict[str, Future[_T]]]
    # _aws: tuple[Future[_T], dict[str, Future[_T]]]
    _extra_args: tuple[t.Any]
    _extra_kwargs: Mapping[str, t.Any]

    def __init__(
        self,
        factory,
        aw_args=FrozenDict(),
        aw_kwargs=FrozenDict(),
        *,
        args: tuple = (),
        kwargs: dict[str, t.Any] = FrozenDict(),
        loop=None,
    ) -> Self:
        Future.__init__(self, loop=loop)
        self._factory = factory
        self._aws = aw_args, aw_kwargs
        self._extra_args = args
        self._extra_kwargs = kwargs

    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            factory = self._factory
            aw_args, aw_kwargs = self._aws

            if aw_args:
                for k in aw_args:
                    aw_args[k] = yield from aw_args[k]
                _args = factory._args
                args = (
                    aw_args[i] if i in aw_args else _args[i] for i in range(len(_args))
                )
            else:
                args = factory._args

            if aw_kwargs:
                for k, aw in aw_kwargs.items():
                    aw_kwargs[k] = yield from aw_kwargs[k]

            if kwargs := self._extra_kwargs:
                vals = factory._vals | kwargs
                kwargs = factory._kwargs.skip(kwargs)
            else:
                vals = factory._vals
                kwargs = factory._kwargs

            res = factory._func(*args, *self._extra_args, **aw_kwargs, **kwargs, **vals)
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
