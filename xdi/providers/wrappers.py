# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False


import asyncio
from functools import partial
import typing as t
from asyncio import AbstractEventLoop, ensure_future, get_running_loop
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from enum import Enum
from logging import getLogger
from threading import Lock

import attr
from typing_extensions import Self

from asyncio import Future
from .._common.collections import frozendict

if t.TYPE_CHECKING:
    from ..injectors import Injector
    from .functools import BoundParams


logger = getLogger(__name__)

_T = t.TypeVar("_T")

_object_new = object.__new__

class _CallShape(t.NamedTuple):
    args: bool = False
    kwargs: bool = False
    aws: bool = False
    async_: bool = False


class CallShape(_CallShape, Enum):

    plain: 'CallShape'               = ()
    plain_async: 'CallShape'         = _CallShape(async_=True)

    args: 'CallShape'                = _CallShape(args=True)
    aw_args: 'CallShape'             = _CallShape(args=True, aws=True)
    args_async: 'CallShape'          = _CallShape(args=True, async_=True)
    aw_args_async: 'CallShape'       = _CallShape(args=True, aws=True, async_=True)

    kwargs: 'CallShape'              = _CallShape(kwargs=True)
    aw_kwargs: 'CallShape'           = _CallShape(kwargs=True, aws=True)
    kwargs_async: 'CallShape'        = _CallShape(kwargs=True, async_=True)
    aw_kwargs_async: 'CallShape'     = _CallShape(kwargs=True, aws=True, async_=True)

    args_kwargs: 'CallShape'          = _CallShape(args=True, kwargs=True)
    aw_args_kwargs: 'CallShape'       = _CallShape(args=True, kwargs=True, aws=True)
    args_kwargs_async: 'CallShape'    = _CallShape(args=True, kwargs=True, async_=True)
    aw_args_kwargs_async: 'CallShape' = _CallShape(args=True, kwargs=True, aws=True, async_=True)


















class FutureFactoryWrapper:

    __slots__ = "_func", "_args", "_kwargs", "_vals", "_aw_args", "_aw_kwargs", "_aw_call"

    _func: Callable
    _args: "_PositionalArgs"
    _kwargs: "_KeywordDeps"
    _vals: Mapping

    def __new__(
        cls,
        func,
        vals: Mapping = frozendict(),
        args: "_PositionalArgs" = frozendict(),
        kwargs: "_KeywordDeps" = frozendict(),
        *,
        aw_args: tuple[int] = frozendict(),
        aw_kwargs: tuple[str] = frozendict(),
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


class FutureResourceWrapper(FutureFactoryWrapper):

    __slots__ = (
        "_aw_enter",
        "_ctx",
    )

    _aw_enter: bool
    _ctx: "Injector"

    if not t.TYPE_CHECKING:

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
        self, factory, aw_args=frozendict(), aw_kwargs=frozendict(), *, loop=None
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
        aw_args=frozendict(),
        aw_kwargs=frozendict(),
        *,
        args: tuple = (),
        kwargs: dict[str, t.Any] = frozendict(),
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


class ResourceFuture(Future):

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
        aw_args=frozendict(),
        aw_kwargs=frozendict(),
        *,
        args: tuple = (),
        kwargs: dict[str, t.Any] = frozendict(),
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









def plain_wrapper(func, params: "BoundParams", injector: "Injector"):
    return func
plain_async_wrapper = plain_wrapper

def plain_future_wrapper(func, params: "BoundParams", injector: "Injector", *, aw_call: bool=True, cls=FutureFactoryWrapper, **kwds):
    return cls(func, aw_call=aw_call, **kwds)

resource_plain_future_wrapper = partial(plain_future_wrapper, cls=FutureResourceWrapper)


def args_wrapper(func, params: "BoundParams", injector: "Injector"):
    args = params.resolve_args(injector)
    vals = params.vals
    return lambda: func(*args, **vals)
args_async_wrapper = args_wrapper



def aw_args_wrapper(func, params: "BoundParams", injector: "Injector", *, aw_call: bool=False, cls=FutureFactoryWrapper, **kwds):
    args, aw_args = params.resolve_aw_args(injector)
    return cls(func, params.vals, args=args, aw_args=aw_args, aw_call=aw_call, **kwds)

aw_args_async_wrapper = partial(aw_args_wrapper, aw_call=True)
resource_aw_args_wrapper = partial(aw_args_wrapper, cls=FutureResourceWrapper)
resource_aw_args_async_wrapper = partial(aw_args_wrapper, aw_call=True, cls=FutureResourceWrapper)



def kwargs_wrapper(func, params: "BoundParams", injector: "Injector"):
    kwargs = params.resolve_kwargs(injector)
    vals = params.vals
    return lambda: func(**kwargs, **vals)
kwargs_async_wrapper = kwargs_wrapper

def aw_kwargs_wrapper(func, params: "BoundParams", injector: "Injector", *, aw_call: bool=False):
    kwargs, aw_kwargs = params.resolve_aw_kwargs(injector)
    return FutureFactoryWrapper(func, params.vals, kwargs=kwargs, aw_kwargs=aw_kwargs, aw_call=aw_call)

aw_kwargs_async_wrapper = partial(aw_kwargs_wrapper, aw_call=True)


resource_aw_kwargs_wrapper = partial(aw_kwargs_wrapper, cls=FutureResourceWrapper)
resource_aw_kwargs_async_wrapper = partial(aw_kwargs_wrapper, aw_call=True, cls=FutureResourceWrapper)


def args_kwargs_wrapper(func, params: "BoundParams", injector: "Injector"):
    args = params.resolve_args(injector)
    kwargs = params.resolve_kwargs(injector)
    vals = params.vals
    return lambda: func(*args, **kwargs, **vals)
args_kwargs_async_wrapper = args_kwargs_wrapper


def aw_args_kwargs_wrapper(func, params: "BoundParams", injector: "Injector", *, aw_call: bool=False):
    args, aw_args = params.resolve_aw_args(injector)
    kwargs, aw_kwargs = params.resolve_aw_kwargs(injector)
    return FutureFactoryWrapper(
        func,
        params.vals,
        args=args,
        kwargs=kwargs,
        aw_args=aw_args,
        aw_kwargs=aw_kwargs,
        aw_call=aw_call,
    )

aw_args_kwargs_async_wrapper = partial(aw_args_kwargs_wrapper, aw_call=True)


resource_aw_args_kwargs_wrapper = partial(aw_args_kwargs_wrapper, cls=FutureResourceWrapper)
resource_aw_args_kwargs_async_wrapper = partial(aw_args_kwargs_wrapper, aw_call=True, cls=FutureResourceWrapper)

def enter_context_pipe(wrap, **kwds):
    def wrapper(func, params: "BoundParams", injector: "Injector", **kw):
        func = wrap(func, params, injector, **(kwds | kw))
        return lambda: injector.exitstack.enter(func())
    return wrapper




def partial_plain_wrapper(func, params: "BoundParams", injector: "Injector"):
    return params.factory

def partial_args_wrapper(func, params: "BoundParams", injector: "Injector"):
    args = params.resolve_args(injector)
    vals = params.vals
    def make(*a, **kw):
        nonlocal func, args, vals
        return func(*args, *a, **(vals | kw))

    return make

def partial_kwargs_wrapper(func, params: "BoundParams", injector: "Injector"):
    kwargs = params.resolve_kwargs(injector)
    vals = params.vals
    def make(*a, **kw):
        nonlocal func, kwargs, vals
        return func(*a, **(vals | kw), **kwargs.skip(kw))

    return make

def partial_args_kwargs_wrapper(func, params: "BoundParams", injector: "Injector"):
    args = params.resolve_args(injector)
    kwargs = params.resolve_kwargs(injector)
    vals = params.vals
    def make(*a, **kw):
        nonlocal func, args, kwargs, vals
        return func(*args, *a, **(vals | kw), **kwargs.skip(kw))

    return make


# partial_aw_args_wrapper = partial(aw_args_wrapper, aw_call=True)
# partial_aw_args_async_wrapper = partial(aw_args_wrapper, aw_call=True)
# partial_aw_args_async_wrapper = partial(aw_args_wrapper, aw_call=True)
