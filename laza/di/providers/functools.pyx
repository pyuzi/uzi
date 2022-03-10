# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False


import asyncio
import typing as t
from functools import partial
from asyncio import FIRST_EXCEPTION, AbstractEventLoop, CancelledError, Future, Task, create_task, ensure_future, gather as async_gather, get_running_loop
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence, Iterator
from inspect import Parameter, Signature, isawaitable, iscoroutinefunction
from logging import getLogger
from inject import T

from laza.common.abc import abstractclass, immutableclass
from laza.common.collections import Arguments, frozendict, orderedset
from laza.common.functools import Missing, export
from laza.common.typing import Self, typed_signature

from .. import Injectable, InjectionMarker, T_Injectable, T_Injected


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


if cython.compiled:
    print(f'RUNNING: "{__name__}" IN COMPILED MODE')
else:
    print(f'RUNNING IN PYTHON')


_object_new = object.__new__
_object_setattr = object.__setattr__


@abstractclass
class decorators:
    @staticmethod
    def singleton(func: Callable, ctx: "InjectorContext"):
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
    def resource(func: Callable, ctx: "InjectorContext"):
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
    def contextmanager(cm, ctx: "InjectorContext"):
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


class ParamResolver:

    __slots__ = (
        "annotation",
        "value",
        "dependency",
        "default",
        "has_value",
        "has_default",
    )
    annotation: t.Any
    value: _T
    default: t.Any
    dependency: Injectable

    def __new__(
        cls, value: t.Any = _EMPTY, default=_EMPTY, annotation=_EMPTY
    ):
        if isinstance(value, InjectionMarker):
            dependency = value
        elif isinstance(default, InjectionMarker):
            dependency = default
        else:
            dependency = annotation

        self = object.__new__(cls)
        self.annotation = annotation
        self.dependency = dependency
        self.value = value
        self.default = default

        self.has_value = not (value is _EMPTY or isinstance(value, InjectionMarker))
        self.has_default = not (
            default is _EMPTY or isinstance(default, InjectionMarker)
        )

        return self

    def bind(self, injector: "Injector"):
        if not self.has_value:
            dep = self.dependency
            if not dep is _EMPTY and injector.is_provided(dep):
                return dep

    def resolve(self, ctx: "InjectorContext"):
        if self.has_value:
            return self.value, _EMPTY, _EMPTY
        elif self.dependency is _EMPTY:
            return _EMPTY, _EMPTY, self.default if self.has_default else _EMPTY
        elif self.has_default:
            return _EMPTY, ctx.find(self.dependency, default=_EMPTY), self.default
        else:
            return _EMPTY, ctx.find(self.dependency, default=_EMPTY), _EMPTY

    def __repr__(self):
        value, annotation, default = (
            "..." if x is _EMPTY else x
            for x in (self.value, self.annotation, self.default)
        )
        if isinstance(annotation, type):
            annotation = annotation.__name__

        return f'<{self.__class__.__name__}: {"Any" if annotation == "..." else annotation} ={default}, value={value}>'


@export
class FactoryResolver:

    __slots__ = (
        "factory",
        "arguments",
        "signature",
        "decorators",
        "async_call",
    )
    is_async = False
    factory: Callable
    arguments: dict[str, t.Any]
    signature: Signature
    decorators: list[Callable[[Callable], Callable]]

    def __init__(
        self,
        factory: Callable,
        signature: Signature = None,
        *,
        is_async: bool = None,
        arguments: Arguments = None,
        decorators: Sequence = (),
    ):
        self.factory = factory
        self.async_call = iscoroutinefunction(factory) if is_async is None else is_async
        self.signature = signature or typed_signature(factory)
        self.decorators = decorators
        self.arguments = self.parse_arguments(arguments)
        self._post_init()

    def _post_init(self):
        pass

    def __call__(
        self,
        injector: "Injector",
        provides: T_Injectable = None,
    ) -> Callable:
        _args, _kwds, _vals, deps = self.evaluate(injector)
        return self.make_resolver(provides, self.factory, _args, _kwds, _vals), deps

    def parse_arguments(self, arguments: Arguments = None):
        if arguments:
            bound = self.signature.bind_partial(*arguments.args, **arguments.kwargs)
        else:
            bound = self.signature.bind_partial()
        return bound.arguments

    def iter_param_resolvers(self):
        arguments = self.arguments
        for n, p in self.signature.parameters.items():
            if p.kind is _VAR_POSITIONAL:
                p = p.replace(annotation=_EMPTY)
                for v in arguments.get(n, ()):
                    yield n, p, self.make_param_resolver(p, v)
            elif p.kind is _VAR_KEYWORD:
                p = p.replace(annotation=_EMPTY)
                for k, v in arguments.get(n, {}).items():
                    yield k, p, self.make_param_resolver(p, v)
            else:
                yield n, p, self.make_param_resolver(p, arguments.get(n, _EMPTY))

    def make_param_resolver(self, param: Parameter, value=_EMPTY):
        return ParamResolver(value, param.default, param.annotation)

    def evaluate(self, injector: "Injector"):
        args = []
        kwds = []
        vals = {}
        deps = defaultdict(list)

        skip_pos = False
        for n, p, r in self.iter_param_resolvers():
            dep = r.bind(injector)
            if p.kind in _POSITIONAL_KINDS:
                if skip_pos is False:
                    if not dep is None:
                        args.append(r)
                        deps[dep].append(n)
                    elif r.has_value or r.has_default:
                        args.append(r)
                    else:
                        skip_pos = True
                continue
            elif r.has_value:
                vals[n] = r.value
            elif not dep is None:
                kwds.append((n, r))
                deps[dep].append(n)

        return tuple(args), tuple(kwds), vals, dict(deps)

    # def iresolve_args(self, args: Iterable, ctx: "InjectorContext"):
    #     for r in args:
    #         yield r.resolve(ctx)

    # def iresolve_kwds(
    #     self, kwds: Iterable, ctx: "InjectorContext"
    # ):
    #     for n, r in kwds:
    #         v, f, d = r.resolve(ctx)
    #         if not f is _EMPTY:
    #             yield n, f

    def resolve_args(self, args: Iterable, ctx: "InjectorContext"):
        aws = []
        res = []
        for r in args:
            val, dep = r.resolve(ctx)[:-1]
            if _EMPTY is val is dep:
                break

            val is _EMPTY and hasattr(dep, 'is_async') and dep.is_async and aws.append(dep)
            res.append((val, dep))
        return tuple(res), tuple(aws)

    def resolve_kwds(
        self, kwds: Iterable, ctx: "InjectorContext"
    ):
        aws = []
        res = []
        i = 0
        for n, r in kwds:
            dep = r.resolve(ctx)[1]
            if not _EMPTY is dep:
                hasattr(dep, 'is_async') and  dep.is_async and aws.append(dep)
                res.append((n, dep))
            i += 0

        return tuple(res), tuple(aws)

    def _decorate(self, func, ctx: "InjectorContext"):
        is_async = self.is_async
        for fn in self.decorators:
            func = fn(func, ctx, is_async=is_async)
        return func

    def iargs(self, args: Iterable):
        for v, fn in args:
            if v is _EMPTY:
                yield fn()  # if (v := fn.value) is Missing else v
            else:
                yield v

    def ikwds(self, kwds: Iterable, skip=None):
        vals = {}
        if skip:
            for n, fn in kwds:
                if not n in skip:
                    vals[n] = fn()  # if (v := fn.value) is Missing else v
        else:
            for n, fn in kwds:
                vals[n] = fn()  # if (v := fn.value) is Missing else v
                # vals[n] = fn()

        return vals

    if t.TYPE_CHECKING:

        def _iargs(self, args: Iterable):
            ...

        def _ikwds(self, kwds: Iterable, skip=None):
            ...

    else:
        _iargs = iargs
        _ikwds = ikwds

    def make_resolver(self, provides, func, _args, _kwds, _vals):
        if not self.signature.parameters:
            return self.make_plain_resolver(provides, func)
        elif not _args:
            return self.make_kwds_resolver(provides, func, _kwds, _vals)
        elif not _kwds:
            return self.make_args_resolver(provides, func, _args, _vals)
        else:
            return self.make_args_kwds_resolver(provides, func, _args, _kwds, _vals)

    def make_plain_resolver(self, provides, func):
        def provider(ctx: "InjectorContext"):
            nonlocal func
            return self._decorate(self.plain_wrap_func(func), ctx)

        return provider

    def make_args_resolver(self, provides, func, _args: Sequence, vals):
        def provider(ctx: "InjectorContext"):
            nonlocal _args, vals, self
            args, aws = self.resolve_args(_args, ctx)
            return self._decorate(self.arg_wrap_func(func, args, vals, aws), ctx)

        return provider

    def make_kwds_resolver(self, provides, func, _kwds, vals):
        def provider(ctx: "InjectorContext"):
            nonlocal vals, _kwds, self
            kwds, aws = self.resolve_kwds(_kwds, ctx)
            return self._decorate(self.kwd_wrap_func(func, kwds, vals, aws), ctx)

        return provider

    def make_args_kwds_resolver(self, provides, func, _args, _kwds, vals):
        def provider(ctx: "InjectorContext"):
            nonlocal _args, vals, _kwds, self
            args, aw_args = self.resolve_args(_args, ctx)
            kwds, aw_kwds = self.resolve_kwds(_kwds, ctx)
            return self._decorate(self.arg_kwd_wrap_func(func, args, kwds, vals, aw_args, aw_kwds), ctx)

        return provider

    def plain_wrap_func(self, func):
        if self.async_call:
            future = FutureCall(func)
            def make():
                nonlocal future
                return __future_call(future)
            make.is_async = True
        else:
            def make():
                nonlocal func
                return func()
            make.is_async = False
        return make

    def arg_wrap_func( # type: ignore
        self,
        func,
        args: tuple,
        vals: dict,
        aws: tuple = (),
    ):
        if aws:
            future = FutureCall(
                func, vals=vals, args=args, aw_args=aws, aw_call=self.async_call
            )
            def make():
                nonlocal future
                # return __future_call_aw_args(future)
            make.is_async = True
        elif self.async_call:
            future = FutureCall(func, vals=vals, args=args, aw_args=aws)
            def make():
                nonlocal future
                return __future_call(future)
            make.is_async = True
        else:
            def make():
                nonlocal self, func, args, vals
                return func(*self.iargs(args), **vals)

            make.is_async = False
        return make

    def kwd_wrap_func(
        self,
        func,
        kwds: tuple,
        vals: dict,
        aws: tuple = (),
    ):
        if aws:
            future = FutureCall(
                func, vals=vals, kwds=kwds, aw_kwds=aws, aw_call=self.async_call
            )
            def make():
                nonlocal future
                return __future_call(future)
            make.is_async = True
        elif self.async_call:
            future = FutureCall(func, vals=vals, kwds=kwds, aw_kwds=aws)
            def make():
                nonlocal future
                return __future_call(future)
            make.is_async = True
        else:

            def make():
                nonlocal self, func, kwds, vals
                return func(**vals, **self.ikwds(kwds))

            make.is_async = False

        return make

    def arg_kwd_wrap_func(
        self,
        func,
        args: tuple,
        kwds: tuple,
        vals: dict,
        aw_args: tuple = (),
        aw_kwds: tuple = (),
    ):
        if aw_kwds or aw_args:
            future = FutureCall(
                func, vals=vals, args=args, kwds=kwds, aw_kwds=aw_kwds, aw_call=self.async_call
            )
            def make():
                nonlocal future
                return __future_call(future)
            make.is_async = True

        elif self.async_call:
            future = FutureCall(func, vals=vals, args=args, kwds=kwds, aw_kwds=aw_kwds)
            def make():
                nonlocal future
                return __future_call(future)
            make.is_async = True
        else:

            def make():
                nonlocal self, func, args, kwds, vals
                return func(*self.iargs(args), **vals, **self.ikwds(kwds))

            make.is_async = False
        return make





class CallableFactoryResolver(FactoryResolver):

    __slots__ = ()

    # def iargs(self, args, a=()):
    #     if self.is_partial:
    #         yield from self._iargs(args)
    #         yield from a
    #     else:
    #         yield from a
    #         yield from super().iargs(args[len(a):])

    def iargs(self, args, a=()):
        return a + tuple(self._iargs(args[len(a) :]))
        # yield from a
        # yield from self._iargs(args[len(a):])

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





cdef class FutureCall: # type: ignore

    __slots__ = "func", "args", "kwds", "vals", "aws", "aw_args", "aw_kwds", "aw_call", 

    is_async = True

    def __cinit__(
        self,
        func,
        vals=frozendict(),
        args=(),
        kwds=(),
        aw_args=(),
        aw_kwds=(),
        *,
        aw_call: bool = True,
    ):
        self.func = func
        self.vals = vals
        self.args = args
        self.kwds = kwds
        self.aws = aw_args + aw_kwds
        self.aw_args = len(aw_args)
        self.aw_kwds = len(aw_kwds)
        self.aw_call = aw_call

    def iargs(self, aws: Iterator = None):
        if aws is None:
            for val, dep in self.args:
                if dep is _EMPTY:
                    yield val
                else:
                    yield dep()
        else:
            for val, dep in self.args:
                if dep is _EMPTY:
                    yield val
                elif dep.is_async:
                    yield next(aws)
                else:
                    yield dep()

    def ikwds(self, aws: Iterator = None):
        if aws is None:
            for n, dep in self.kwds:
                yield n, dep()
        else:
            for n, dep in self.kwds:
                if dep.is_async:
                    yield n, next(aws)
                else:
                    yield n, dep()
