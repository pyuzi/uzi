# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False


from email.generator import Generator
from email.policy import default
from itertools import starmap
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





   


class ParamResolver:

    __slots__ = (
        "param",
        "name",
        "value",
        "dependency",
        "default",
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
    # _aw_value: 'AwaitValue'
    # _aw_default: 'AwaitValue'

    def __new__(
        cls, name: str, value: t.Any = _EMPTY, default=_EMPTY, annotation=_EMPTY
    ):
        self = object.__new__(cls)
        self.name = name
        self.has_value = self.has_default = self.has_dependency = False
       
        if isinstance(value, InjectionMarker):
            self.dependency = value
            self.has_dependency = True
        elif not value is _EMPTY:
            self.has_value = True
            self.value = value

        if isinstance(default, InjectionMarker):
            if self.has_dependency is False:
                self.dependency = default
                self.has_dependency = True
        elif not default is _EMPTY:
            self.default = default
            self.has_default = True

        if False is self.has_dependency is not is_injectable_annotation(annotation):
            self.dependency = annotation
            self.has_dependency = isinstance(annotation, InjectionMarker)
       
       
        return self

    @property
    def value_factory(self) -> None:
        try:
            return self._value_factory 
        except AttributeError as e:
            if not self.has_value:
                raise AttributeError(f'`value`') from e
            self._value_factory = lambda: self.value
            return self._value_factory

    @property
    def default_factory(self) -> None:
        try:
            return self._default_factory 
        except AttributeError as e:
            if self.has_default is True:
                self._default_factory = lambda: self.default 
            elif self.has_dependency is True:
                self._default_factory = Missing
            else:
                raise AttributeError(f'`default_factory`')
            return self._default_factory





@export
class FactoryResolver:

    __slots__ = (
        "factory",
        "signature",
        "decorators",
        "is_async",
        "injector",
        "has_aws",
        "args",
        "aw_args",
        "aw_kwds",
        "kwds",
        "deps",
        "vals",
    )

    factory: Callable
    injector: 'Injector'
    arguments: dict[str, t.Any]
    signature: Signature
    decorators: list[Callable[[Callable], Callable]]

    aws: frozenset[ParamResolver]
    deps: frozenset[ParamResolver]
    args: tuple[ParamResolver]
    aw_args: orderedset[ParamResolver]
    kwds: tuple[ParamResolver]
    aw_kwds: orderedset[ParamResolver]
    vals: frozendict[str, t.Any]
    is_async: bool

    def __init__(
        self,
        injector: 'Injector',
        factory: Callable,
        signature: Signature = None,
        *,
        is_async: bool = None,
        arguments: Arguments = None,
        decorators: Sequence = (),
    ):
        # self = object.__new__(cls)
        self.factory = factory
        self.injector = injector
        self.is_async = iscoroutinefunction(factory) if is_async is None else is_async
        self.has_aws = None
        self.signature = signature or typed_signature(factory)
        self.decorators = decorators
        # self._post_init()
        self.evaluate(self.parse_arguments(arguments))
        # return self

    # def _post_init(self):
    #     pass

    @property
    def dependencies(self):
        return {d.dependency for d in self.deps}

    def __call__(self) -> Callable:
        if not self.signature.parameters:
            handler = self.make_plain_handler()
        elif not self.args:
            handler = self.make_kwds_handler()
        elif not self.kwds:
            handler = self.make_args_resolver()
        else:
            handler = self.make_args_kwds_resolver()
        
        return handler, self.dependencies

    def parse_arguments(self, arguments: Arguments = None):
        if arguments:
            bound = self.signature.bind_partial(*arguments.args, **arguments.kwargs)
        else:
            bound = self.signature.bind_partial()
        return bound.arguments

    def iter_param_resolvers(self, arguments: dict):
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
        return ParamResolver(param.name, value, param.default, param.annotation)

    def evaluate(self, arguments: dict):
        args = []
        kwds = []
        vals = {}
        deps = set()

        skip_pos = False
        for n, p, r in self.iter_param_resolvers(arguments):
            if p.kind in _POSITIONAL_KINDS:
                if skip_pos is False:
                    if self._check_param_dependency(r):
                        args.append(r)
                        deps.add(r)
                    elif r.has_value:
                        args.append(r)
                    else:
                        skip_pos = True
                continue
            elif r.has_value:
                vals[n] = r.value
            elif self._check_param_dependency(r):
                kwds.append(r)
                deps.add(r)

        self.args = tuple(args)
        self.kwds = tuple(kwds)
        self.vals = frozendict(vals)
        self.deps = frozenset(deps)

    def _check_param_dependency(self, p: ParamResolver):
        if False is p.has_dependency is p.has_value:
            dep = p.dependency
            p.has_dependency = not dep is _EMPTY and self.injector.is_provided(dep)
        return p.has_dependency


    def evaluate_awaitables(self, ctx: "InjectorContext"):
        assert self.has_aws is None
      
        self.aw_args = orderedset(
            d for d in self.args 
                if not d.has_value and d.has_dependency 
                    and _is_aync_provider(ctx[d.dependency])
        )
        self.aw_kwds = orderedset(
            d for d in self.kwds 
                if not d.has_value and d.has_dependency 
                    and _is_aync_provider(ctx[d.dependency])
        )

        self.has_aws = not not (self.aw_kwds or self.aw_args)


    def resolve_args(self, ctx: "InjectorContext"):
        aw_args = self.aw_args
        aws = []
        args = []
        i = 0
        for p in self.args:
            if p.has_value is True:
                args.append(p.value_factory)
            else:
                p in aw_args and aws.append(i)
                args.append(ctx.find(p.dependency, default=p.default_factory))
            i += 1

        return _PositionalDeps(args), tuple(aws)

    def resolve_kwds(self, ctx: "InjectorContext"):
        aw_kwds = self.aw_kwds
        aws = []
        return _KeywordDeps(
            kv for p in self.kwds
                if (kv := (p.name, ctx.find(p.dependency, default=p.default_factory)))
                and (not p in aw_kwds or aws.append(kv))
        ), tuple(aws)
       

    def _decorate(self, func, ctx: "InjectorContext"):
        is_async = self.is_async or self.has_aws
        for fn in self.decorators:
            func = fn(func, ctx, is_async=is_async)
        return func

    def make_plain_handler(self):
        if self.has_aws is None:
            self.has_aws = False

        def provider(ctx: "InjectorContext"):
            return self._decorate(self.plain_wrapper(ctx), ctx)

        return provider

    def make_args_resolver(self):

        def provider(ctx: "InjectorContext"):
            nonlocal self
            self.has_aws is None and self.evaluate_awaitables(ctx)
            return self._decorate(self.arg_wrapper(ctx), ctx)

        return provider

    def make_kwds_handler(self):

        def provider(ctx: "InjectorContext"):
            nonlocal self
            self.has_aws is None and self.evaluate_awaitables(ctx)
            return self._decorate(self.kwd_wrapper(ctx), ctx)

        return provider

    def make_args_kwds_resolver(self):
        
        def provider(ctx: "InjectorContext"):
            nonlocal self
            self.has_aws is None and self.evaluate_awaitables(ctx)
            return self._decorate(self.arg_kwd_wrapper(ctx), ctx)

        return provider

    def plain_wrapper(self, ctx: 'InjectorContext'):
        if self.is_async:
            def make():
                nonlocal self
                return self.factory()
            make.is_async = True
            return make
        else:
            return self.factory

    def arg_wrapper(self: Self, ctx: 'InjectorContext'):
        args, aw_args = self.resolve_args(ctx)
        vals = self.vals
        func = self.factory
        if aw_args: 
            return AwaitFactory(func, vals, args=args, aw_args=aw_args, aw_call=self.is_async)
        else:
            def make():
                nonlocal func, args, vals
                return func(*args, **vals)
            make.is_async = self.is_async
        return make

    def kwd_wrapper(self: Self, ctx: 'InjectorContext'):
        kwds, aw_kwds = self.resolve_kwds(ctx)
        vals = self.vals
        func = self.factory
        if aw_kwds: 
            return AwaitFactory(func, vals, kwds=kwds, aw_kwds=aw_kwds, aw_call=self.is_async)
        else:
            def make():
                nonlocal func, kwds, vals
                return func(**vals, **kwds)
            make.is_async = self.is_async
        return make

    def arg_kwd_wrapper(self: Self, ctx: 'InjectorContext'):
        args, aw_args = self.resolve_args(ctx)
        kwds, aw_kwds = self.resolve_kwds(ctx)
        vals = self.vals
        func = self.factory
        
        if aw_kwds or aw_args:
            return AwaitFactory(func, vals, args=args, kwds=kwds, aw_args=aw_args, aw_kwds=aw_kwds, aw_call=self.is_async)
        else:
            def make():
                nonlocal func, args, kwds, vals
                return func(*args, **vals, **kwds)
            make.is_async = self.is_async
        return make




class CallableFactoryResolver(FactoryResolver):

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

__base_positional_deps = (tuple[Callable[[], _T]], t.Generic[_T]) if t.TYPE_CHECKING else (tuple,)

class _PositionalDeps(*__base_positional_deps):

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
        item = self.get_raw(index)
        if index.__class__ is slice:
            return self.__raw_new__(item)
        else:
            return item()

    def __iter__(self) -> 'Iterator[tuple[_T, bool]]':
        for f in self.iter_raw():
            yield f()
            
    if t.TYPE_CHECKING:
        def get_raw(index: int) -> Callable[[], _T]: ...
        def iter_raw() -> Iterator[Callable[[], _T]]: ...
    else:
        get_raw = tuple.__getitem__
        iter_raw = tuple.__iter__


   
class _KeywordDeps(dict[str, Callable[[], _T]], t.Generic[_T]):

    __slots__ = '_is_async',

    def __reduce__(self):
        return tuple, (tuple(self),) 

    def copy(self):
        return self[:]
    __copy__ = copy

    @property
    def is_async(self):
        try:
            return self._is_async
        except AttributeError:
            self._is_async = None
            return None

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






class AwaitFactory:

    __slots__ = '_loop', '_func', '_args', '_kwds', '_vals', '_aw_args', '_aw_kwds', '_aw_call'

    _func: Callable
    _args: _PositionalDeps
    _kwds: _KeywordDeps
    _vals: Mapping

    is_async: bool = True


    def __new__(cls, func, vals: Mapping=frozendict(), args: _PositionalDeps=emptydict(), kwds: _KeywordDeps=emptydict(), *, aw_args: tuple[int]=emptydict(), aw_kwds: tuple[str]=emptydict(), aw_call: bool=True, loop: asyncio.AbstractEventLoop=None) -> Self:
        self = _object_new(cls)
        self._loop = get_running_loop() if loop is None else loop 
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







class FactoryFuture(Future):

    # __slots__ = '_loop', '_factory', '_aws', '_result', 

    _asyncio_future_blocking = False
    _loop: AbstractEventLoop
    _factory: AwaitFactory
    _aws: tuple[dict[int, Future[_T]], dict[str, Future[_T]]]
    _result: _T

    # def __new__(cls: type[Self], factory, aw_args=emptydict(), aw_kwds=emptydict(), *, loop=None) -> Self:
    #     self = _object_new(cls)
    #     self._loop = get_running_loop() if loop is None else loop
    #     self._factory = factory
    #     self._aws = aw_args, aw_kwds
    #     return self
    
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
