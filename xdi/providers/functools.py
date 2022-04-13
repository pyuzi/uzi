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

import attr

from .._common.collections import frozendict
from .._common import Missing


from .. import (
    Injectable,
    InjectionMarker,
    is_injectable_annotation,
)

if t.TYPE_CHECKING:
    from ..scopes import Scope
    from ..injectors import Injector
    from ..containers import Container
    from .._dependency import Dependency



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
    )

    param: Parameter
    name: str
    annotation: t.Any
    value: _T
    default: t.Any
    injectable: Injectable
    dependency: 'Dependency'
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
        self.dependency = self.injectable = None
        self.has_value = self.has_default = self.has_dependency = False

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
    def is_async(self):
        if dep := self.dependency:
            return dep.is_async

    @property
    def is_injectable(self):
        return not self.injectable is None

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
            elif self.dependency:
                self._default_factory = Missing
            else:
                raise AttributeError(f"`default_factory`")
            return self._default_factory



@attr.s(slots=True, frozen=True)
class BoundParams:

    params: tuple[BoundParam] = attr.ib(converter=tuple)

    args: tuple[BoundParam] = attr.ib(converter=tuple, kw_only=True)
    aw_args: tuple[int] = attr.ib(converter=tuple)
    kwds: tuple[BoundParam] = attr.ib(converter=tuple)
    aw_kwds: tuple[str] = attr.ib(converter=tuple)
    is_async: bool = attr.ib()
    vals: frozendict[str, t.Any] = attr.ib(converter=frozendict)
    _pos_vals: int = attr.ib(converter=int)
    _pos_deps: int = attr.ib(converter=int)
 
    @property
    def dependencies(self) -> set['Dependency']:
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
            is_async=not not(aw_args or aw_kwds)
        )

    @classmethod
    def bind(cls, sig: Signature, scope: 'Scope'=None, container: 'Container'=None, args: tuple=(), kwargs: dict=frozendict()) -> Self:
        return cls.make(cls._iter_bind(sig, scope, container, args, kwargs))        

    @classmethod
    def _iter_bind(cls, sig: Signature, scope: 'Scope'=None, container: 'Container'=None, args=(), kwargs=frozendict()):
        bound = sig.bind_partial(*args, **kwargs).arguments

        for n, p in sig.parameters.items():
            if p.kind is Parameter.VAR_POSITIONAL:
                p = p.replace(annotation=Parameter.empty)
                for v in bound.get(n) or (Parameter.empty,):
                    bp = BoundParam(p, v)
                    if scope and bp.is_injectable:
                        bp.dependency = scope[bp.injectable:container]
                    yield bp
            elif p.kind is Parameter.VAR_KEYWORD:
                p = p.replace(annotation=Parameter.empty)
                for k, v in (bound.get(n) or {n: Parameter.empty}).items():
                    bp = BoundParam(p, v, key=k)
                    if scope and bp.is_injectable:
                        bp.dependency = scope[bp.injectable:container]
                    yield bp
            else:
                bp = BoundParam(p, bound.get(n, Parameter.empty))
                if scope and bp.is_injectable:
                    bp.dependency = scope[bp.injectable:container]
                yield bp

    def __bool__(self): 
        return not not self.params

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

    def resolve_kwargs(self, ctx: "Injector"):
        return _KeywordDeps(
            (p.key, ctx.find(p.dependency, default=p.default_factory))
            for p in self.kwds
        )

    def resolve_aw_kwargs(self, ctx: "Injector"):
        if self.aw_kwds:
            deps = self.resolve_kwargs(ctx)
            return deps, tuple((n, deps.pop(n)) for n in self.aw_kwds)
        else:
            return self.resolve_kwargs(ctx), ()












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





