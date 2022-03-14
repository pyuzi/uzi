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
from laza.common.collections import Arguments, frozendict, orderedset
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

    # @property
    # def name(self) -> str:
    #     return self.parameter.

    @property
    def value_factory(self) -> None:
        try:
            return self._value_factory 
        except AttributeError as e:
            if not self.has_value:
                raise AttributeError(f'`value`') from e
            self._value_factory = lambda: self.value # AwaitValue(self.value)
            return self._value_factory

    @property
    def default_factory(self) -> None:
        try:
            return self._default_factory 
        except AttributeError as e:
            if self.has_default is True:

                self._default_factory = lambda: self.default # AwaitValue(self.default)
                # self._default_factory.is_async = self.is_async
            elif self.has_dependency is True:
                self._default_factory = Missing
            else:
                raise AttributeError(f'`default_factory`')
            return self._default_factory

    # TODO: Remove tbis method.
    def check_dependency(self, injector: "Injector"):
        if False is self.has_dependency is self.has_value:
            dep = self.dependency
            self.has_dependency = not dep is _EMPTY and injector.is_provided(dep)
        return self.has_dependency

    # def check_is_aync(self, ctx: 'InjectorContext'):


    #     if False is self.has_dependency is self.has_value:
    #         dep = self.dependency
    #         self.has_dependency = not dep is _EMPTY and injector.is_provided(dep)
    #     return self.has_dependency

    def resolve(self, ctx: "InjectorContext", *, as_awaitable: bool = False) -> t.Union[Callable, None]:
        if self.has_value is True:
            return self.value_factory, False
        elif self.has_dependency is True:
            res = ctx.find(self.dependency, default=self.default_factory)
            return res, _is_aync_provider(res) # AwaitCall(res) if as_awaitable is True else res
       
        raise TypeError(f'Param not resolvable')



    # def __repr__(self):
    #     value, annotation, default = (
    #         "..." if x is _EMPTY else x
    #         for x in (self.value, self.annotation, self.default)
    #     )
    #     if isinstance(annotation, type):
    #         annotation = annotation.__name__

    #     return f'<{self.__class__.__name__}: {"Any" if annotation == "..." else annotation} ={default}, value={value}>'




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
        injector = self.injector

        skip_pos = False
        for n, p, r in self.iter_param_resolvers(arguments):
            if p.kind in _POSITIONAL_KINDS:
                if skip_pos is False:
                    if r.check_dependency(injector):
                        args.append(r)
                        deps.add(r)
                    elif r.has_value:
                        args.append(r)
                    else:
                        skip_pos = True
                continue
            elif r.has_value:
                vals[n] = r.value
            elif r.check_dependency(injector):
                kwds.append(r)
                deps.add(r)

        self.args = tuple(args)
        self.kwds = tuple(kwds)
        self.vals = frozendict(vals)
        self.deps = frozenset(deps)

    def evaluate_awaitables(self, ctx: "InjectorContext"):
        assert self.has_aws is None
      
        self.aw_args = orderedset(d for d in self.args if d.resolve(ctx)[1])
        self.aw_kwds = orderedset(d for d in self.kwds if d.resolve(ctx)[1])
        self.has_aws = not not (self.aw_kwds or self.aw_args)

        # assert not hasattr(self, 'aw_args') or hasattr(self, 'aw_args')
        # self.aws = frozenset({dep for dep in self.deps if })

    def resolve_args(self, ctx: "InjectorContext"):
        # aws = self.aws
        args = self.args
        return _PositionalDeps(r.resolve(ctx) for r in args)

        # if aws:
        #     res = _PositionalDeps(r.resolve(ctx, as_awaitable=not r in aws) for r in args)
        # else:
        #     res = _PositionalDeps(r.resolve(ctx) for r in args)
        # return res

    def resolve_kwds(self, ctx: "InjectorContext"):
        return _KeywordDeps(((r.name, r.resolve(ctx)) for r in self.kwds))
        # res = {}
        # aws = self.aws
        # if aws:
        #     res = _KeywordDeps(((r.name, r.resolve(ctx, as_awaitable=not r in aws)) for r in self.kwds))
        # else:
        #     res = _KeywordDeps(((r.name, r.resolve(ctx)) for r in self.kwds))
            
        # return res

    def _decorate(self, func, ctx: "InjectorContext"):
        is_async = self.is_async
        for fn in self.decorators:
            func = fn(func, ctx, is_async=is_async)
        return func

    def make_plain_handler(self):
        if self.has_aws is None:
            self.has_aws = False

        def provider(ctx: "InjectorContext"):
            return self._decorate(self.plain_wrap_func(ctx), ctx)

        return provider

    def make_args_resolver(self):

        def provider(ctx: "InjectorContext"):
            nonlocal self
            self.has_aws is None and self.evaluate_awaitables(ctx)
            return self._decorate(self.arg_wrap_func(ctx), ctx)

        return provider

    def make_kwds_handler(self):

        def provider(ctx: "InjectorContext"):
            nonlocal self
            self.has_aws is None and self.evaluate_awaitables(ctx)
            return self._decorate(self.kwd_wrap_func(ctx), ctx)

        return provider

    def make_args_kwds_resolver(self):
        
        def provider(ctx: "InjectorContext"):
            nonlocal self
            self.has_aws is None and self.evaluate_awaitables(ctx)
            return self._decorate(self.arg_kwd_wrap_func(ctx), ctx)

        return provider

    def plain_wrap_func(self, ctx: 'InjectorContext'):
        if self.is_async is False:
            return self.factory
        else:
            def make():
                nonlocal self
                return self.factory()
            make.is_async = True
            return make

    def arg_wrap_func(self: Self, ctx: 'InjectorContext'):
        args = self.resolve_args(ctx)
        if self.has_aws is True:
            aw_cls = AwaitArgsAsyncFactory if  self.is_async is True else AwaitArgsFactory
            return aw_cls(self.factory, self.vals, args)
        else:
            def make():
                nonlocal self, args
                return self.factory(*args, **self.vals)

            make.is_async = self.is_async
        return make

    def kwd_wrap_func(self: Self, ctx: 'InjectorContext'):
        kwds = self.resolve_kwds(ctx)

        if self.has_aws is True:
            aw_cls = AwaitKwdsAsyncFactory if self.is_async is True else AwaitKwdsFactory
            return aw_cls(self.factory, self.vals, kwds=kwds)
        else:
            def make():
                nonlocal self, kwds
                return self.factory(**self.vals, **kwds)

            make.is_async = self.is_async
        return make

    def arg_kwd_wrap_func(self: Self, ctx: 'InjectorContext'):
        args = self.resolve_args(ctx)
        kwds = self.resolve_kwds(ctx)
        
        if self.has_aws is True:
            aw_cls = AwaitArgsKwdsAsyncFactory if  self.is_async is True else AwaitArgsKwdsFactory
            return aw_cls(self.factory, self.vals, args, kwds)
        else:
            def make():
                nonlocal self, kwds
                return self.factory(*args, **self.vals, **kwds)

            make.is_async = self.is_async
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




class Args(Sequence):
    __slots__ = 'args', 

    def __getiem__(self, index):
        pass


class Kwargs(dict):
    __slots__ = 'args', 

    def __init__(self, ):
        pass

    def __getiem__(self, index):
        pass


_blank_slice = slice(None, None, None)


_tuple_new = tuple.__new__
_tuple_blank = ()

__base_positional_deps = (tuple[tuple[Callable[[], _T], bool]], t.Generic[_T]) if t.TYPE_CHECKING else (tuple,)

class _PositionalDeps(*__base_positional_deps):

    # __slots__ = '_is_async',

    # __blank: '_PositionalDeps[_T]'

    # def __new__(cls, iterable: t.Union[Self, Iterable]=_tuple_blank) -> Self:
    #     if cls is iterable.__class__:
    #         return iterable
    #     elif not iterable and isinstance(iterable, Collection):
    #         return cls.__blank
    #     else:
    #         return cls.__raw_new__(iterable)
    
    __raw_new__ = classmethod(tuple.__new__)

    @property
    def is_async(self):
        try:
            return self._is_async
        except AttributeError:
            self._is_async = None
            return None

    def __reduce__(self):
        return tuple, (tuple(self),) 

    def copy(self):
        return self[:]

    __copy__ = copy

    def future(self, *, loop: asyncio.AbstractEventLoop=None):
        loop = get_running_loop() if loop is None else loop 

        if self.is_async is False:
            return _FuturePositionalDeps(self, loop=loop)

        aws = []
        i = 0
        deps = [
            v 
            for fn, aw in (self.iter_raw())
            if (aw is False and (i := i+1) and ((v := fn()) or True)) 
                or aws.append(i) 
                or ((i := i+1) and (v := ensure_future(fn(), loop=loop)))
        ]
        self._is_async = not not aws
        return _FuturePositionalDeps(deps, aws, loop=loop)

    @t.overload
    def __getitem__(self, index: int) -> tuple[_T, bool]: ...
    @t.overload
    def __getitem__(self, slice: slice) -> Self: ...

    def __getitem__(self, index: t.Union[int, slice]) -> t.Union[tuple[_T, bool], Self]:
        item = self.get(index)
        if index.__class__ is slice:
            return self.__raw_new__(item)
        else:
            return item[0]()

    def __iter__(self) -> 'Iterator[tuple[_T, bool]]':
        i = 0
        x = len(self)
        while x > i:
            yield self[i]
            i += 1
            
    if t.TYPE_CHECKING:
        def get(index: int) -> tuple[Callable[[], _T], bool]: ...
        def iter_raw() -> Iterator[tuple[Callable[[], _T], bool]]: ...
    else:
        get = tuple.__getitem__
        iter_raw = tuple.__iter__


# _PositionalDeps.___PositionalDeps_blank = _tuple_new(_PositionalDeps)





__base_keyword_deps = (dict[str, tuple[Callable[[], _T], bool]], t.Generic[_T]) if t.TYPE_CHECKING else (dict,)
   
   
class _KeywordDeps(*__base_keyword_deps):

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

    def future(self, *, loop: asyncio.AbstractEventLoop=None):
        loop = get_running_loop() if loop is None else loop 
        if self.is_async is False:
            return _FutureKeywordDeps(self, loop=loop)

        aws = []
        deps = { 
            n: v
            for n, (fn, aw) in self.raw_items()
            if (aw is False and ((v := fn()) or True)) 
                or aws.append(n) 
                or (v := ensure_future(fn(), loop=loop))
        }
        self._is_async = not not aws
        return _FutureKeywordDeps(deps, aws, loop=loop)

    def __getitem__(self, name: str):
        return self.get_raw(name)[0]()

    def __iter__(self) -> 'Iterator[_T]':
        yield from self.iter_raw()

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
        def get_raw(name: str) -> tuple[Callable[[], _T], bool]: ...
        def iter_raw() -> Iterator[str]: ...
        raw_items = dict[str, tuple[Callable[[], _T], bool]].items
        raw_values = dict[str, tuple[Callable[[], _T], bool]].values

    
    iter_raw = dict.__iter__
    get_raw = dict.__getitem__
    raw_items = dict.items
    raw_values = dict.values




class _FuturePositionalDeps:
    # __slots__ = 'deps', '_loop', 
    _deps: _PositionalDeps[_T]
    _result = Missing
    _used = False
    _asyncio_future_blocking = False
    
    def __init__(self, deps: list, aws: list=(), *, loop: AbstractEventLoop):
        self._loop = loop 
        self._deps = deps
        self._aws = aws
   
    def __await__(self):
        if self._used is False:
            self._used = True
            result = self._deps
            for k in self._aws:
                result[k] = yield from result[k]
            return result
        else:
            raise RuntimeError(f'cannot reuse already awaited {self.__class__.__name__}')
    
    __iter__ = __await__





class _FutureKeywordDeps:

    _deps: _KeywordDeps[_T]
    # _result = Missing
    _aws = None
    _used = False
    _asyncio_future_blocking = False
    _loop: AbstractEventLoop

    def __init__(self, deps: _KeywordDeps, aws: list=(), *, loop: AbstractEventLoop):
        self._loop = loop
        self._deps = deps
        self._aws = aws

    def __await__(self):
        if self._used is False:
            self._used = True
            result = self._deps
            for k in self._aws:
                result[k] = yield from result[k]
            return result
        else:
            raise RuntimeError(f'cannot reuse already awaited {self.__class__.__name__}')
    
    __iter__ = __await__





class AwaitFactory:

    __slots__ = '_loop', 'func', 'args', 'kwds', 'vals', '_used'

    _used: bool
    func: Callable
    args: _PositionalDeps
    kwds: _KeywordDeps
    vals: Mapping
    _asyncio_future_blocking = False

    is_async: bool = True
    
    def __new__(cls, func, vals: Mapping=frozendict(), args: _PositionalDeps=None, kwds: _KeywordDeps=None, *, loop: asyncio.AbstractEventLoop=None) -> Self:
        self = _object_new(cls)
        self._loop = get_running_loop() if loop is None else loop 
        self._used = False
        self.func = func
        self.vals = vals
        self.args = args
        self.kwds = kwds
        return self

    def __iter__(self):
        return self.__await__()
    
    def __await__(self):
        raise NotImplementedError(f'{self.__class__.__name__}.__await__()')

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}:{self.func.__module__}.{self.func.__qualname__}()'

    def __call__(self):
        return self


class AwaitArgsFactory(AwaitFactory):

    __slots__ = ()

    def __new__(cls, func, vals: Mapping=frozendict(), args: _PositionalDeps=None, *, loop: asyncio.AbstractEventLoop=None) -> Self:
        self = _object_new(cls)
        self._loop = get_running_loop() if loop is None else loop 
        self._used = False
        self.func = func
        self.vals = vals
        self.args = args
        return self

    def __await__(self):
        # if self._used is False:
        #     self._used = True
        fut = self.args.future(loop=self._loop)
        args = yield from fut
        return self.func(*args, **self.vals)
        # else:
        #     raise RuntimeError(f'cannot reuse already awaited {self.__class__.__name__}')





class AwaitArgsAsyncFactory(AwaitArgsFactory):

    __slots__ = ()

    def __await__(self):
        # if self._used is False:
        #     self._used = True
        loop = self._loop
        fut = self.args.future(loop=loop)
        args = yield from fut
        res = yield from ensure_future(self.func(*args, **self.vals), loop=loop)
        return res
        # else:
        #     raise RuntimeError(f'cannot reuse already awaited {self}')



class AwaitKwdsFactory(AwaitFactory):

    __slots__ = ()

    def __new__(cls, func, vals: Mapping=frozendict(), kwds: _KeywordDeps=None, *, loop: asyncio.AbstractEventLoop=None) -> Self:
        self = _object_new(cls)
        self._loop = get_running_loop() if loop is None else loop 
        self._used = False
        self.func = func
        self.vals = vals
        self.kwds = kwds
        return self

    def __await__(self):
        # if self._used is False:
        #     self._used = True
        fut = self.kwds.future(loop=self._loop)
        kwds = yield from fut
        return self.func(**self.vals, **kwds)
        # else:
        #     raise RuntimeError(f'cannot reuse already awaited {self}')





class AwaitKwdsAsyncFactory(AwaitKwdsFactory):

    __slots__ = ()

    def __await__(self):
        # if self._used is False:
        #     self._used = True
        loop = self._loop
        fut = self.kwds.future(loop=loop)
        kwds = yield from fut
        res = yield from ensure_future(self.func(**self.vals, **kwds), loop=loop)
        return res
        # else:
        #     raise RuntimeError(f'cannot reuse already awaited {self}')





class AwaitArgsKwdsFactory(AwaitFactory):
    __slots__ = ()

    def __await__(self):
        # if self._used is False:
            # self._used = True
        loop = self._loop

        fargs = self.args.future(loop=loop)
        fkwds = self.kwds.future(loop=loop)

        args = yield from fargs
        kwds = yield from fkwds
        return self.func(*args, **self.vals, **kwds)
        # else:
        #     raise RuntimeError(f'cannot reuse already awaited {self}')





class AwaitArgsKwdsAsyncFactory(AwaitArgsKwdsFactory):

    __slots__ = ()

    def __await__(self):
        # if self._used is False:
            # self._used = True
        loop = self._loop

        fargs = self.args.future(loop=loop)
        fkwds = self.kwds.future(loop=loop)

        args = yield from fargs
        kwds = yield from fkwds
        res = yield from ensure_future(self.func(*args, **kwds, **self.vals), loop=loop)
        return res
        # else:
            # raise RuntimeError(f'cannot reuse already awaited {self}')




