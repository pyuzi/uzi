from abc import ABC, abstractmethod
import logging
from threading import Lock
from typing_extensions import Self
import attr
import typing as t

from collections.abc import Callable

from .._common import Missing, private_setattr
from .._functools import (
    BoundParams,
    _PositionalArgs,
    _PositionalDeps,
    _KeywordDeps,
    FutureFactoryWrapper,
    FutureResourceWrapper,
    FutureCallableWrapper,
)

from ..markers import T_Injectable, T_Injected
from ..exceptions import InjectorLookupError

if t.TYPE_CHECKING:  # pragma: no cover
    from ..providers import Provider
    from ..injectors import Injector
    from ..containers import Container
    from . import Graph


_object_new = object.__new__


_T_Concrete = t.TypeVar("_T_Concrete")
"""Provided `concrete` `TypeVar`"""


@attr.s(slots=True, frozen=True, cmp=False)
@private_setattr
class Node(ABC, t.Generic[_T_Concrete]):
    """A dependency graph node."""

    @abstractmethod
    def bind(self, injector: "Injector") -> t.Union[Callable[..., T_Injected], None]:
        raise NotImplementedError(
            f"{self.__class__.__name__}.bind()"
        )  # pragma: no cover

    abstract: T_Injectable = attr.ib()
    graph: "Graph" = attr.ib()
    provider: "Provider" = attr.ib(default=None, repr=lambda p: str(p and id(p)))

    concrete: _T_Concrete = attr.ib(kw_only=True, default=Missing, repr=True)

    is_async: bool = False
    dependencies = frozenset[Self]()

    _v_ident: tuple = attr.ib(init=False, repr=False)

    @_v_ident.default
    def _init_v_ident(self):
        return self.abstract, self.graph, self.container

    _ash: tuple = attr.ib(init=False, repr=False)

    @_ash.default
    def _init_ash(self):
        return hash(self._v_ident)

    @property
    def container(self):
        if pro := self.provider or self.graph:
            return pro.container

    def __eq__(self, o: Self) -> bool:
        if o.__class__ is self.__class__:
            return o._v_ident == self._v_ident
        elif isinstance(o, Node):
            return False
        return NotImplemented

    def __ne__(self, o: Self) -> bool:
        if o.__class__ is self.__class__:
            return o._v_ident != self._v_ident
        elif isinstance(o, Node):
            return True
        return NotImplemented

    def __hash__(self) -> int:
        return self._ash


_T_Node = t.TypeVar("_T_Node", bound=Node, covariant=True)
"""Node `TypeVar`"""


@private_setattr
class MissingNode:

    __slots__ = (
        "abstract",
        "graph",
    )

    graph: "Graph"
    container = None
    is_async: bool = False
    dependencies = frozenset[Self]()

    def __new__(
        cls: type[Self],
        abstract=None,
        graph: "Graph" = None,
        provider=None,
        concrete=None,
    ) -> Self:
        self = _object_new(cls)
        self.__setattr(abstract=abstract, graph=graph)
        return self

    def __bool__(self):
        return False

    def __reduce__(self):
        return self.__class__, (self.abstract, self.graph)

    def __eq__(self, o):
        return self.abstract == o

    def __ne__(self, o):
        return not self == o

    def __hash__(self) -> int:
        return hash(self.abstract)

    def bind(self, injector: "Injector"):
        raise InjectorLookupError(self.abstract, self.graph or injector.graph)


@attr.s(slots=True, frozen=True, cmp=False)
class SimpleNode(Node[_T_Concrete]):
    def bind(self, injector: "Injector"):
        return self.concrete(injector)


@attr.s(slots=True, frozen=True, cmp=False)
class Value(Node[T_Injected]):
    """Value node"""

    concrete: T_Injected = attr.ib(kw_only=True, default=None)
    is_async: t.Final = False

    def bind(self, injector: "Injector"):
        return self

    def __call__(self) -> T_Injected:
        return self.concrete


_T_ValueNode = t.TypeVar("_T_ValueNode", bound=Value, covariant=True)
"""Value node `TypeVar`"""


@attr.s(slots=True, frozen=True, cmp=False)
class Factory(Node[T_Injected]):
    """Factory node"""

    concrete: T_Injected = attr.ib(kw_only=True)
    params: "BoundParams" = attr.ib(kw_only=True, default=BoundParams.make(()))
    thread_safe: bool = attr.ib(kw_only=True, default=False)

    @property
    def dependencies(self):
        return self.params.dependencies

    def bind(self: Self, injector: "Injector"):
        if self.params:
            args = self.resolve_args(injector)
            kwargs = self.resolve_kwargs(injector)
            vals = self.params.vals
            func = self.concrete

            def factory():
                nonlocal func, args, kwargs, vals
                return func(*args, **kwargs, **vals)

            return factory
        else:
            return self.concrete

    def resolve_args(self, injector: "Injector"):
        params = self.params
        if params.args:
            if params._pos_vals > 0 < params._pos_deps:
                return _PositionalArgs(
                    (p.value, None) if p.has_value else (None, injector[p.dependency])
                    for p in params.args
                )
            elif params._pos_deps > 0:
                return _PositionalDeps(injector[p.dependency] for p in params.args)
            else:
                return tuple(p.value for p in params.args)
        return ()

    def resolve_kwargs(self, injector: "Injector"):
        return _KeywordDeps((p.key, injector[p.dependency]) for p in self.params.kwds)


_T_FactoryNode = t.TypeVar("_T_FactoryNode", bound=Factory, covariant=True)
"""Factory node `TypeVar`"""


@attr.s(slots=True, frozen=True, cmp=False)
class AsyncFactory(Factory[T_Injected]):
    """AsyncFactory node"""

    is_async: bool = True
    async_call: bool = True


@attr.s(slots=True, frozen=True, cmp=False)
class AwaitParamsFactory(Factory[T_Injected]):
    """AwaitParamsFactory node"""

    is_async: bool = True
    async_call: bool = False

    def bind(self: Self, injector: "Injector"):
        args, aw_args = self.resolve_args(injector)
        kwargs, aw_kwargs = self.resolve_kwargs(injector)
        return FutureFactoryWrapper(
            self.concrete,
            self.params.vals,
            args=args,
            kwargs=kwargs,
            aw_args=aw_args,
            aw_kwargs=aw_kwargs,
            aw_call=self.async_call,
        )

    def resolve_kwargs(self, injector: "Injector"):
        if self.params.aw_kwds:
            deps = super().resolve_kwargs(injector)
            return deps, tuple((n, deps.pop(n)) for n in self.params.aw_kwds)
        else:
            return super().resolve_kwargs(injector), ()

    def resolve_args(self, injector: "Injector"):
        return super().resolve_args(injector), self.params.aw_args


@attr.s(slots=True, frozen=True, cmp=False)
class AwaitParamsAsyncFactory(AwaitParamsFactory[T_Injected]):
    """AwaitParamsAsyncFactory node"""

    async_call: bool = True


@attr.s(slots=True, frozen=True, cmp=False)
class Singleton(Factory[T_Injected]):
    """Singleton node"""

    # aw_enter: bool = attr.ib(kw_only=True, default=False)

    def factory(self, injector: "Injector"):
        if self.params:
            args = self.resolve_args(injector)
            kwargs = self.resolve_kwargs(injector)
            vals = self.params.vals
            func = self.concrete
            return lambda: func(*args, **kwargs, **vals)
        else:
            return self.concrete

    def bind(self, injector: "Injector"):
        func = self.factory(injector)
        value = Missing
        lock = Lock() if self.thread_safe else None

        def factory():
            nonlocal func, value
            if not value is Missing:
                return value

            lock and lock.acquire(blocking=True)
            try:
                if value is Missing:
                    value = func()
            finally:
                lock and lock.release()
            return value

        return factory


_T_SingletonNode = t.TypeVar("_T_SingletonNode", bound=Singleton, covariant=True)
"""Singleton node `TypeVar`"""


@attr.s(slots=True, frozen=True, cmp=False)
class AsyncSingleton(Singleton[T_Injected]):
    """AsyncSingleton node"""

    is_async: bool = True
    async_call: bool = True

    def factory(self, injector: "Injector"):
        if params := self.params:
            args, kwargs = self.resolve_args(injector), self.resolve_kwargs(injector)
            return FutureFactoryWrapper(
                self.concrete,
                params.vals,
                args=args,
                kwargs=kwargs,
                aw_call=self.async_call,
            )
        else:
            return FutureFactoryWrapper(
                self.concrete, self.params.vals, aw_call=self.async_call
            )


@attr.s(slots=True, frozen=True, cmp=False)
class AwaitParamsSingleton(Singleton[T_Injected], AwaitParamsFactory[T_Injected]):
    """AwaitParamsSingleton node"""

    is_async: bool = True
    async_call: bool = False

    def factory(self, injector: "Injector"):
        (args, aw_args), (kwargs, aw_kwargs) = self.resolve_args(
            injector
        ), self.resolve_kwargs(injector)
        return FutureFactoryWrapper(
            self.concrete,
            self.params.vals,
            args=args,
            kwargs=kwargs,
            aw_args=aw_args,
            aw_kwargs=aw_kwargs,
            aw_call=self.async_call,
        )


@attr.s(slots=True, frozen=True, cmp=False)
class AwaitParamsAsyncSingleton(AwaitParamsSingleton[T_Injected]):
    """AwaitParamsAsyncSingleton node"""

    async_call: bool = True


@attr.s(slots=True, frozen=True, cmp=False)
class Resource(Singleton[T_Injected]):
    """Binds resources."""


_T_ResourceNode = t.TypeVar("_T_ResourceNode", bound=Resource, covariant=True)
"""Resource node `TypeVar`"""


@attr.s(slots=True, frozen=True, cmp=False)
class Partial(Factory[T_Injected]):
    """Partial node"""

    def factory(self: Self, injector: "Injector"):
        args = self.resolve_args(injector)
        kwargs = self.resolve_kwargs(injector)
        vals = self.params.vals
        func = self.concrete

        def make(*a, **kw):
            nonlocal func, args, kwargs, vals
            return func(*args, *a, **(vals | kw), **kwargs.skip(kw))

        return make

    def bind(self: Self, injector: "Injector"):
        return self.factory(injector)


_T_PartialNode = t.TypeVar("_T_PartialNode", bound=Partial, covariant=True)
"""Partial node `TypeVar`"""


@attr.s(slots=True, frozen=True, cmp=False)
class AsyncPartial(Partial[T_Injected]):
    """AsyncPartial node"""

    async_call: bool = True
    is_async: bool = True


@attr.s(slots=True, frozen=True, cmp=False)
class AwaitParamsPartial(Partial[T_Injected], AwaitParamsFactory[T_Injected]):
    """AwaitParamsPartial node"""

    async_call: bool = False
    is_async: bool = True

    def factory(self: Self, injector: "Injector"):
        (args, aw_args), (kwargs, aw_kwargs) = self.resolve_args(
            injector
        ), self.resolve_kwargs(injector)
        return FutureCallableWrapper(
            self.concrete,
            self.params.vals,
            args=args,
            kwargs=kwargs,
            aw_args=aw_args,
            aw_kwargs=aw_kwargs,
            aw_call=self.async_call,
        )


@attr.s(slots=True, frozen=True, cmp=False)
class AwaitParamsAsyncPartial(AwaitParamsPartial[T_Injected]):
    """AwaitParamsAsyncPartial node"""

    async_call: bool = True


@attr.s(slots=True, frozen=True, cmp=False)
class Callable(Partial[T_Injected]):
    """Callable node"""

    def bind(self: Self, injector: "Injector"):
        func = self.factory(injector)
        return lambda: func


_T_CallableNode = t.TypeVar("_T_CallableNode", bound=Callable, covariant=True)
"""Callable node `TypeVar`"""


@attr.s(slots=True, frozen=True, cmp=False)
class AsyncCallable(Callable[T_Injected], AsyncPartial[T_Injected]):
    """AsyncCallable node"""

    is_async: bool = True


@attr.s(slots=True, frozen=True, cmp=False)
class AwaitParamsCallable(Callable[T_Injected], AwaitParamsPartial[T_Injected]):
    """AwaitParamsCallable node"""

    is_async: bool = True


@attr.s(slots=True, frozen=True, cmp=False)
class AwaitParamsAsyncCallable(
    Callable[T_Injected], AwaitParamsAsyncPartial[T_Injected]
):
    """AwaitParamsAsyncCallable node"""

    async_call: bool = True
