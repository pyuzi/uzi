from functools import lru_cache
from logging import getLogger
from re import S
from threading import Lock
import typing as t


from threading import Lock

from collections.abc import Mapping
from laza.common.collections import Arguments, frozendict

from laza.common.functools import export, Missing
from laza.common.typing import Self



from collections.abc import Callable

from types import FunctionType, GenericAlias



from .exc import InjectorKeyError

from .common import Injectable, T_Injected, T_Injectable

logger = getLogger(__name__)



_T = t.TypeVar("_T")

if t.TYPE_CHECKING:
    from .injectors import Injector








@export()
class ScopeVarDict(dict[T_Injectable, 'ScopeVar']):

    __slots__ = "scope",

    scope: "Scope"

    def __init__(self, scope: "Scope"):
        self.scope = scope

    def __missing__(self, key):
        scope = self.scope
        res = scope.injector.resolvers[key]
        if res is None:
            return self.setdefault(key, scope.parent.vars[key])
        return self.setdefault(key, res(scope))




@export()
class Scope(dict[T_Injectable, 'ScopeVar']):

    __slots__ = (
        "injector",
        "parent",
        "resolvers",
        # "level",
        "_dispatched",
        "__weakref__",
    )

    injector: "Injector"
    parent: "Scope"
    resolvers: dict[T_Injectable, Callable[['Scope'], 'ScopeVar']]

    # level: int

    def __init__(self, injector: "Injector", parent: "Scope" = None) -> None:
        self.injector = injector
        self.parent = NullScope() if parent is None else parent
        # self.level = 0 if parent is None else parent.level + 1
        self.resolvers = None
        self._dispatched = 0
        self[injector] = self

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

    def get(key, default=None):
        try:
            return self[key]
        except InjectorKeyError:
            return default

    def __missing__(self, key):
        res = self.resolvers[key]
        if res is None:
            return self.setdefault(key, self.parent[key])
        return self.setdefault(key, res(self))

    def __contains__(self, x) -> bool:
        return super().__contains__(x) \
            or (self.parent is not None and x in self.parent)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}[{self.level}]({self.name!r})"

    def __repr__(self) -> str:
        return f"<{self!s}, {self.parent!r}>"

    def __enter__(self: "Scope") -> "Scope":
        self.dispatch()
        return self

    def __exit__(self, *exc):
        self.dispose()

    def __eq__(self, x):
        return x is self
    
    def __hash__(self):
        return id(self)
    



@export()
class NullScope(Scope):
    """NullInjector Object"""

    __slots__ = ("name",)

    injector = None
    parent = None

    def __init__(self, name=None):
        self.resolvers = None
        self.name = name or "null"

    def __getitem__(self, k: T_Injectable) -> None:
        raise InjectorKeyError(f"{k}")
    __missing__ = __getitem__

    def get(key, default=None):
        return default

    def dispatch(self, *stack: 'Scope'):
        return False

    def dispose(self, *stack: 'Scope'):
        return False







@export()
class ScopeVar(t.Generic[T_Injected]):
    """Resolver t.Generic[T_InjectedObject"""

    __slots__ = ()

    value: T_Injected = Missing

    def get(self) -> T_Injected:
        ...
        
    def make(self, *a, **kw) -> T_Injected:
        ...
        
    def __new__(cls, *args, **kwds):
        if cls is ScopeVar:
            return _LegacyScopeVar(*args, **kwds)
        else:
            return object.__new__(cls)
        




@export()
class ValueScopeVar(ScopeVar[T_Injected]):
    """Resolver t.Generic[T_InjectedObject"""

    __slots__ = 'value',

    def __new__(cls, value: T_Injected):
        self = object.__new__(cls)
        self.value = value
    
        return self

    def get(self) -> T_Injected:
        return self.value

    def make(self) -> T_Injected:
        return self.value

    def __repr__(self) -> str: 
        value = self.value
        return f'{self.__class__.__name__}({value=!r})'



@export()
class FactoryScopeVar(ScopeVar[T_Injected]):
    """Factory InjectorVar"""

    __slots__ = 'make', 'get',

    def __new__(cls, make: T_Injected):
        self = object.__new__(cls)
        self.get = self.make = make
        return self
    
    def __repr__(self) -> str: 
        make = self.make
        return f'{self.__class__.__name__}({make=!r})'




@export()
class SingletonScopeVar(ScopeVar[T_Injected]):
    """Factory InjectorVar"""

    __slots__ = 'make', 'value', 'lock',

    def __new__(cls, make: T_Injected):
        self = object.__new__(cls)
        self.make = make
        self.value = Missing
        self.lock  = Lock()
        return self

    def get(self) -> T_Injected:
        if self.value is Missing:
            with self.lock:
                if self.value is Missing:
                    self.value = self.make()
        return self.value
        
    def __repr__(self) -> str: 
        make, value = self.make, self.value
        return f'{self.__class__.__name__}({value=!r}, {make=!r})'



@export()
class LruCachedScopeVar(ScopeVar[T_Injected]):
    """Factory InjectorVar"""

    __slots__ = 'make', 'get',

    def __new__(cls, make: T_Injected, *, maxsize: bool=128, typed: bool=False):
        self = object.__new__(cls)
        self.make = self.get = lru_cache(maxsize, typed)(make)
        return self
    
    def __repr__(self) -> str: 
        make = self.make
        return f'{self.__class__.__name__}({make=!r})'




class _LegacyScopeVar(ScopeVar[T_Injected]):
    """Resolver t.Generic[T_InjectedObject"""

    __slots__ = 'value', 'get', 'make',

    value: T_Injected

    def __new__(cls, 
                value: T_Injected = Missing, 
                make: t.Union[Callable[..., T_Injected], None]=None, 
                *, 
                shared: t.Union[bool, None] = None):
        
        self = object.__new__(cls)

        if make is not None:
            self.make = make
            if shared is True:
                def get():
                    nonlocal make, value
                    if value is Missing:
                        value = make()
                    return value
                self.get = get
            else:
                self.get = make
        elif value is Missing:
            raise TypeError(f'{cls.__name__} one of value or call must be provided.')
        else:
            self.make = make
            self.get = lambda: value

        self.value = value
        return self

    def __repr__(self) -> str: 
        make, value = self.make, self.value,
        return f'{self.__class__.__name__}({value=!r}, make={getattr(make, "__func__", make)!r})'



