from contextvars import ContextVar
from logging import getLogger
from threading import Lock, local
import typing as t

import attr
from typing_extensions import Self


from ._common import Missing, ReadonlyDict, private_setattr, FrozenDict
from .markers import (
    AccessLevel,
    Dep,
    DepKey,
    DepSrc,
    ProNoopPredicate,
    ProPredicate,
    is_dependency_marker,
)
from .providers import Provider

from .exceptions import InjectorError
from .containers import Container
from .graph import DepGraph, _null_graph
from .injectors import Injector, NullInjector, _null_injector

logger = getLogger(__name__)


_T_Injector = t.TypeVar("_T_Injector", bound=Injector, covariant=True)
_T_Initial = t.Union[_T_Injector, t.Literal[_null_injector]] # type: ignore

_object_new = object.__new__



@private_setattr
class Scope(t.Generic[_T_Injector]):
    """An isolated dependency resolution `scope` for a given container.

    Scopes assemble the dependency graphs of dependencies registered in their container.

    Attributes:
        container (Container): The container who's scope we are creating
        parent (Scope): The parent scope. Defaults to None

    Args:
        container (Container): The container who's scope we are creating
        parent (Scope, optional): The parent scope. Defaults to NullScope

    """

    __slots__ = (
        "graph",
        "current",
        "initial",
        "parent",
        "_injector_class",
    )

    graph: DepGraph
    parent: Self
    current: _T_Injector
    initial: _T_Initial[_T_Injector]
    _injector_class: type[_T_Injector]

    def __init__(
        self,
        container: Container = None,
        parent: Self = None,
        *,
        graph: DepGraph = None,
        injector_class: type[_T_Injector] = None,
        initial: _T_Initial[_T_Injector] = None,
        **kwargs,
    ) -> None:
        if not graph:
            if not container:
                ValueError(f"one of arguments `container` or `graph` is required.")
            graph = container.new_binding_resolver()
        elif container:
            raise ValueError(
                f"arguments `container` and `graph` are mutually exclusive."
            )

        if initial is None:
            initial = _null_injector

        self.__setattr(
            **self._attrs_init(
                parent=parent or NullGraph(),
                graph=graph,
                initial=initial,
                _injector_class=injector_class or Injector,
                **kwargs,
            )
        )
        graph.setup(self)
        self._set_injector(initial)

    @property
    def container(self):
        return self.graph.container

    @property
    def name(self):
        return self.container.name

    @property
    def is_setup(self):
        return self.initial is self.current

    def __getitem__(self, key):
        return self.graph[key]

    def _attrs_init(self, **kwds):
        return kwds

    def injector(self, *, setup=True):
        if inj := self.current:
            return inj
        elif setup:
            return self.setup()
        else:
            return self.new_injector()

    def new_injector(self):
        return self._injector_class(self, self.parent.injector())

    def setup(self):
        if not self.initial is self.current:
            raise InjectorError(f"injector already setup for: {self!r}")
        return self._set_injector(self.new_injector())

    def reset(self):
        cur, ini = self.current, self.initial
        if cur is ini:
            raise InjectorError(f"injector not setup for: {self!r}")

        cur.close()
        self._set_injector(ini)

    def _set_injector(self, injector: _T_Injector):
        self.__setattr(current=injector)
        return injector

    def __eq__(self, o) -> bool:
        if isinstance(o, Scope):
            return o is self
        return NotImplemented

    def __ne__(self, o) -> bool:
        if isinstance(o, Scope):
            return not o is self
        return NotImplemented

    def __hash__(self):
        return id(self)

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        return f'{self.__class__.__name__}({self.name!r}, parent="{self.parent!s}")'




class SafeScope(Scope[_T_Injector]):

    __slots__ = ("_lock",)

    _lock: Lock

    __setup = Scope.setup
    __reset = Scope.reset

    def _attrs_init(self, **kwds):
        return super()._attrs_init(_lock=Lock(), **kwds)

    def setup(self) -> _T_Injector:
        with self._lock:
            return self.__setup()

    def reset(self):
        with self._lock:
            return self.__reset()


class ContextScope(Scope[_T_Injector]):

    __slots__ = ("__var",)

    __var: ContextVar[_T_Injector]

    def _attrs_init(self, **kwds):
        self.__var = ContextVar(f"{self.name}.injector")
        return super()._attrs_init(**kwds)

    @property
    def current(self):
        return self.__var.get()

    def _set_injector(self, injector: _T_Injector) -> _T_Injector:
        self.__var.set(injector)
        return injector


class _Local(t.Protocol[_T_Injector]):

    injector: _T_Injector


class ThreadScope(Scope[_T_Injector]):

    __slots__ = ("__local",)

    __local: _Local[_T_Injector]

    @property
    def current(self):
        return self.__local.injector

    def _attrs_init(self, **kwds):
        self.__local = local()
        return super()._attrs_init(**kwds)

    def _set_injector(self, injector: _T_Injector) -> _T_Injector:
        self.__local.injector = injector
        return injector


class NullGraph(Scope[NullInjector]):
    """A 'noop' `Scope` used as the parent of root scopes.

    Attributes:
        parent (None): The parent scope
        graph (NullGraph):
    """

    __slots__ = ()
    parent = None
    level = -1
    graph = _null_graph
    name = "<null>"

    def __init__(self) -> None:
        ...

    def __bool__(self):
        return False

    def __eq__(self, o) -> bool:
        return o.__class__ is self.__class__

    def __ne__(self, o) -> bool:
        return not o.__class__ is self.__class__

    __hash__ = classmethod(hash)

    def injector(self, *, setup=True, create=True):
        return _null_injector



