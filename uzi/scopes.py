from contextvars import ContextVar
from logging import getLogger
from threading import Lock, local
import typing as t

from typing_extensions import Self


from ._common import private_setattr

from .exceptions import InvalidStateError, InvalidStateError
from .containers import BaseContainer, Container
from .graph.core import Graph, _null_graph
from .injectors import Injector, NullInjector, _null_injector

logger = getLogger(__name__)


_T_Injector = t.TypeVar("_T_Injector", bound=Injector)
_T_Initial = t.Union[_T_Injector, t.Literal[_null_injector]]  # type: ignore


@private_setattr(frozen="is_active")
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
    )

    graph: Graph
    parent: Self
    current: _T_Injector
    initial: _T_Initial[_T_Injector]

    _injector_class: type[_T_Injector] = Injector

    def __init__(
        self,
        graph: t.Union[Container, Graph],
        parent: Self = None,
        *,
        initial: _T_Initial[_T_Injector] = None,
        **kwargs,
    ) -> None:
        parent = parent or _null_scope

        if isinstance(graph, BaseContainer):
            graph = graph.get_graph(parent.graph)
        elif isinstance(graph, Graph):
            if not graph.parent is parent.graph:
                raise ValueError(f"graph mismatch")
        else:
            raise TypeError(
                f"first argument must be a `Container`, `DepGraph` not `{graph.__class__.__name__}` "
            )

        if initial is None:
            initial = _null_injector

        attrs = (
            self.__default_attrs__()
            | kwargs
            | {"parent": parent, "graph": graph, "initial": initial}
        )

        self.__init_attrs__(attrs)
        self._set_current(initial)

    @property
    def container(self):
        return self.graph.container

    @property
    def name(self):
        return self.container.qualname

    @property
    def active(self):
        return not self.initial is self.current

    def __getitem__(self, key):
        return self.graph[key]

    def __init_attrs__(self, kwds: dict):
        self.__setattr(**kwds)

    def __default_attrs__(self):
        return {}

    def injector(self, *, push=True) -> _T_Injector:
        if inj := self.current:
            return inj
        elif push:
            return self.push()
        else:
            return self._new_injector()

    def _new_injector(self):
        return self._injector_class(self.graph, self.parent.injector())

    def push(self):
        if self.active:
            raise InvalidStateError(f"injector already running: {self}")
        return self._push(force=True)

    def _push(self, *, force: bool = False):
        if force or not self.active:
            inj = self._new_injector()
            self._set_current(inj)
            return inj
        return self.current

    def pop(self):
        if not self.active:
            raise InvalidStateError(f"injector not running: {self}")
        return self._pop(force=True)

    def _pop(self, *, force: bool = False):
        if force or self.active:
            self.current.close()
            self._set_current(self.initial)

    def _set_current(self, injector: _T_Injector):
        self.__setattr("current", injector, injector is self.initial)

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
        return f"{self.__class__.__name__}({self.name!r})"

    def __repr__(self):
        return f'{self.__class__.__name__}({self.name!r}, parent="{self.parent!s}")'

    def __enter__(self):
        return self.injector()

    def __exit__(self, *err):
        self.pop()
        return err and err[0] != None or False


class ThreadSafeScope(Scope[_T_Injector]):
    """A thread safe `Scope` implementation"""

    __slots__ = ("lock",)

    lock: Lock

    def __init_attrs__(self, kwds: dict):
        kwds["lock"] = Lock()
        return super().__init_attrs__(kwds)

    def push(self) -> _T_Injector:
        if self.active:
            raise InvalidStateError(f"injector already running: {self}")

        with self.lock:
            return self._push()

    def pop(self):
        if self.active:
            with self.lock:
                return self._pop()

        raise InvalidStateError(f"injector not running: {self}")


class _ThreadLocalState(local, t.Generic[_T_Injector]):

    __slots__ = ("__initial",)

    injector: _T_Injector

    def __init__(self, injector=_null_injector) -> None:
        self.injector = injector


class ThreadLocalScope(Scope[_T_Injector]):
    """A scope that uses `threading.local` to manage injectors"""

    __slots__ = ("__local",)

    __local: _ThreadLocalState[_T_Injector]

    @property
    def current(self):
        return self.__local.injector

    def __init_attrs__(self, kwds):
        self.__local = _ThreadLocalState(kwds["initial"])
        return super().__init_attrs__(kwds)

    def _set_current(self, injector: _T_Injector) -> _T_Injector:
        self.__local.injector = injector
        return injector


class _NullContextVar:
    __slots__ = ()

    def get(self):
        return _null_injector


_null_context_var = _NullContextVar()


class ContextLocalScope(Scope[_T_Injector]):
    """A scope that uses `contextvars.ContextVar` to manage injectors"""

    __slots__ = ("__var",)

    __var: ContextVar[_T_Injector]

    def __init_attrs__(self, kwds):
        self.__var = _null_context_var
        super().__init_attrs__(kwds)
        self.__var = ContextVar(f"{self.name}.injector", default=self.initial)

    @property
    def current(self):
        return self.__var.get()

    def _set_current(self, injector: _T_Injector) -> _T_Injector:
        self.__var.set(injector)


class NullScope(Scope[NullInjector]):
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
        ...  # pragma: no cover

    def __bool__(self):
        return False

    def __eq__(self, o) -> bool:
        return o.__class__ is self.__class__

    def __ne__(self, o) -> bool:
        return not o.__class__ is self.__class__

    __hash__ = classmethod(hash)

    def injector(self, *, setup=True, create=True):
        return _null_injector


_null_scope = NullScope()
