from contextvars import ContextVar
import logging
import typing as t
from types import FunctionType, GenericAlias
from laza.common.collections import frozendict, nonedict
from laza.common.imports import ImportRef


from laza.common.functools import export
from laza.common.typing import Protocol

from laza.common.functools import Missing

from .common import (
    Injectable,
    T_Injectable,
    T_Injected,
)


from .exc import InjectorKeyError
from .injectors import ScopeVar

if t.TYPE_CHECKING:
    from .injectors import Injector
    from .containers import Container


export(Injectable)

logger = logging.getLogger(__name__)


_T = t.TypeVar("_T")



@export()
class ScopeVarDict(dict[T_Injectable, ScopeVar]):

    __slots__ = "scope",

    scope: "Scope"

    def __init__(self, scope: "Scope"):
        self.scope = scope

    def __missing__(self, key):
        scope = self.scope
        res = scope.injector._bindings[key]
        if res is None:
            return self.setdefault(key, scope.parent.vars[key])
        return self.setdefault(key, res(scope))



@export()
class Scope(t.Generic[T_Injectable, T_Injected]):

    __slots__ = (
        "injector",
        "parent",
        "vars",
        "level",
        "_dispatched",
        "__weakref__",
    )

    _vars_class: t.ClassVar[type[ScopeVarDict]] = ScopeVarDict

    injector: "Injector"
    parent: "Scope"
    vars: dict[T_Injectable, ScopeVar]

    level: int

    def __init__(self, scope: "Injector", parent: "Scope" = None) -> None:
        self.injector = scope
        self.parent = NullScope() if parent is None else parent
        self.level = 0 if parent is None else parent.level + 1
        self.vars = None
        self._dispatched = 0

    @property
    def name(self) -> str:
        return self.injector.name

    def dispatch(self, *stack: 'Scope'):
        self._dispatched += 1
        if self._dispatched == 1:
            self.parent.dispatch(self, *stack)
            self.injector.dispatch_scope(self, *stack)
            return True 
        return False

    def dispose(self, *stack: 'Scope'):
        self._dispatched -= 1
        if self._dispatched == 0:
            self.injector.dispose_scope(self, *stack)
            self.parent.dispose(self, *stack)
            return True
        elif self._dispatched < 0:
            raise RuntimeError(f"injector {self} already disposed.")
        return False

    def get(
        self, injectable: T_Injectable, default: _T = None
    ) -> t.Union[T_Injected, _T]:
        try:
            return self[injectable]
        except InjectorKeyError:
            return default

    def __getitem__(self, key: T_Injectable) -> T_Injected:
        # return self.vars[key]
        res = self.vars[key]
        if res is None:
            return self[self.__missing__(key)]
        # elif res.value is Void:
        #     return res.get()
        # return res.value
        return res.get()

    def make(self, key: T_Injectable, /, *args, **kwds) -> T_Injected:
        res = self.vars[key]
        if res is None:
            return self.make(self.__missing__(key), *args, **kwds)
        elif args or kwds:
            return res.make(*args, **kwds)
        # elif res.value is Void:
        #     return res.get()
        # return res.value
        return res.get()

    def __missing__(self, key):
        if isinstance(key, ImportRef):
            concrete = key(None)
            if concrete is not None:
                logger.warning(f"Cannot bind {key!r} Implicit binding is deprecated.")
                # self.ioc.alias(key, concrete, at=self.name, priority=-10)
                # return concrete
        elif isinstance(key, (type, FunctionType)):
            logger.warning(f"Cannot bind {key!r} Implicit binding is deprecated.")
            # self.ioc.injectable(key, use=key, at=self.name)
            # return key

        raise InjectorKeyError(f"{key} in {self!r}")

    def __contains__(self, x) -> bool:
        if self.vars is not None:
            if isinstance(x, Scope):
                x = x.injector
            return x in self.vars or x in self.parent
        return False

    def __bool__(self) -> bool:
        return True

    def __len__(self) -> bool:
        return len(self.vars)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}[{self.level}]({self.name!r})"

    def __repr__(self) -> str:
        return f"<{self!s}, {self.parent!r}>"

    def __enter__(self: "Scope") -> "Scope":
        self.dispatch()
        return self

    def __exit__(self, *exc):
        self.dispose()




class _NullScopeVars(frozendict):
    __slots__ = ()

    def __missing__(self, k):
        if not isinstance(k, Injectable):
            raise TypeError(f"key must be Injectable, not {k.__class__.__name__}")


@export()
class NullScope(Scope):
    """NullInjector Object"""

    __slots__ = ("name",)

    injector = None
    parent = None
    level = -1

    def __init__(self, name=None):
        _none_var = ScopeVar(None)
        self.vars = _NullScopeVars({None: _none_var, type(None): _none_var})
        self.name = name or "null"

    def get(self, k: T_Injectable, default: _T = None) -> _T:
        return default

    def __contains__(self, x) -> bool:
        return False

    # def __bool__(self):
    #     return False

    def __len__(self):
        return 0

    def __missing__(self, k: T_Injectable) -> None:
        raise InjectorKeyError(f"{k} in {self!r}")

    def dispatch(self, *stack: 'Scope'):
        return False

    def dispose(self, *stack: 'Scope'):
        return False
