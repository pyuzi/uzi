import logging
import typing as t
from functools import partial
from threading import Lock
from collections import deque
from contextlib import AbstractContextManager as ContextManager, ExitStack, nullcontext
from types import FunctionType
from jani.common.collections import  frozendict, nonedict
from jani.common.imports import ImportRef


from jani.common.functools import export

from jani.common.functools import Void

from .common import ( 
    Injectable, InjectorVar,
    T_Injectable, T_Injected,
)


from .exc import InjectorKeyError


if t.TYPE_CHECKING:
    from .scopes import Scope


export(Injectable)

logger = logging.getLogger(__name__)


T = t.TypeVar('T')


@export()
class InjectorContext(ExitStack):


    injector: 'Injector'
    parent: 'InjectorContext'
    _booted: bool = None

    _entry_callbacks: deque
    _exit_callbacks: deque
    _level: int

    def __init__(self, injector: 'Injector'=None):
        super().__init__()
        self.injector = injector
        self._lock = Lock()
        self._level = 0
        self._entry_callbacks = deque()

    @property
    def parent(self):
        return self.injector.parent if self.injector and self.injector.parent else nullcontext()
    
    def pop_all(self):
        """Preserve the context stack by transferring it to a new instance."""
        rv = super().pop_all()
        rv._level = self._level
        rv.injector = self.injector
        rv._entry_callbacks = self._entry_callbacks
        self._level = 0
        self._entry_callbacks = deque()
        return rv

    def onentry(self, cb, /, *args, **kwds):
        """Registers an arbitrary callback and arguments to be called when the 
        context is entered.
        """
        self._push_entry_callback(partial(cb, *args, **kwds))
        return cb  # Allow use as a decorator

    onexit = ExitStack.callback

    def wrap(self, cm, exit=None):
        entry = cm.__enter__ if isinstance(cm, ContextManager) else cm

        callable(entry) and self._push_entry_callback(entry)

        exit = exit if entry is cm else cm
        return cm if exit is None else self.push(exit)

    def _push_entry_callback(self, cb):
        self._entry_callbacks.append(cb)

    def __enter__(self) -> 'Injector':
        with self._lock:

            if self.injector is not None and self._level == 0:
                self.parent.__enter__()
                self.injector.boot()

            try:
                while self._entry_callbacks:
                    self._entry_callbacks.popleft()()
            except Exception as e:
                raise RuntimeError(f'Entering context: {self.injector!r}') from e
            finally:
                self._level += 1

            return self.injector

    def __exit__(self, *exc):
        with self._lock:
            self._level -= 1
            if self._level == 0:
                rv = super().__exit__(*exc)
                if self.injector is not None:
                    self.injector.shutdown()
                    self.parent.__exit__(*exc)
                return rv 

    def __call__(self):
        return self
    


_pklock = Lock()
_last_pk = 0
def _new_pk() -> None:
    global _last_pk
    with _pklock:
        _last_pk += 1
        return _last_pk



@export()
class Injector(t.Generic[T_Injectable, T_Injected]):

    __slots__ = (
        'scope', 'parent', 'vars', 'level', '_ctx',
        '__booted', '__weakref__',
    )

    scope: 'Scope'
    parent: 'Injector'
    vars: dict[T_Injectable, InjectorVar]
    
    _ctx: InjectorContext['Injector']


    level: int
    __booted: bool

    def __init__(self, scope: 'Scope', parent: 'Injector'=None, vars: dict[T_Injectable, InjectorVar]=None) -> None:
        self.scope = scope
        self.parent = NullInjector() if parent is None else parent
        self.level = 0 if parent is None else parent.level + 1 
        self.vars = vars
        self.__booted = False

        self._ctx = scope.create_context(self)

    @property
    def root(self) -> 'Injector':
        if self.level > 0:
            return self.parent.root
        else:
            return self

    @property
    def ioc(self):
        return self.scope.ioc

    @property
    def context(self):
        return self._ctx

    @property
    def booted(self):
        return self.__booted

    @property
    def name(self) -> str:
        return self.scope.name

    def boot(self: 'Injector') -> bool:
        return self._boot()
    
    def shutdown(self) -> bool:
        return self._shutdown()
    
    def at(self, *scopes, default=...) -> 'Injector':
        Scope = self.ioc.Scope
        for s in scopes:
            scope = Scope[s]
            if scope in self:
                return self[scope]

        if default is ...:
            raise InjectorKeyError(', '.join(repr(Scope[s]) for s in scopes))

        return default
    
    def _boot(self) -> bool:
        return False
    
    def _shutdown(self) -> bool:
        return False

    def _setup_ctx(self, ctx: InjectorContext):
        ctx.wrap(self.parent.context)
        ctx.push(self._shutdown)
    
    # def get(self, injectable: T_Injectable, default: T=None, /, *args, **kwds) -> t.Union[T_Injected, T]: 
    def get(self, injectable: T_Injectable, default: T=None) -> t.Union[T_Injected, T]: 
        try:
            return self[injectable]
        except InjectorKeyError:
            return default
    
    def __getitem__(self, key: T_Injectable) -> T_Injected:
        res = self.vars[key]
        if res is None:
            return self[self.__missing__(key)]
        elif res.value is Void:
            return res.get()
        return res.value
        
    def make(self, key: T_Injectable, /, *args, **kwds) -> T_Injected:
        res = self.vars[key]
        if res is None:
            return self.make(self.__missing__(key), *args, **kwds)
        elif (args or kwds):
            # logger.warning(
            #     f'calling {self.__class__.__name__}.make() with args or kwds. {key} got {args=}, {kwds=}'
            # )
            return res.make(*args, **kwds)
        elif res.value is Void:
            return res.get()
        return res.value
    
    # def call(self, key: T_Injectable, /, *args, **kwds) -> T_Injected:
    #     res = self.vars[key]
    #     if res is None:
    #         return self.call(self.__missing__(key), *args, **kwds)
    #     else:
    #         return res.make(*args, **kwds)

    def __missing__(self, key):
        if isinstance(key, ImportRef):
            concrete = key(None)
            if concrete is not None:
                self.ioc.alias(key, concrete, at=self.name, priority=-10)
                return concrete
        elif isinstance(key, (type, FunctionType)):
            self.ioc.injectable(key, use=key, at=self.name, priority=-10)
            return key
        
        raise InjectorKeyError(f'{key} in {self!r}')
    
    def set(self, k: T_Injectable, val: T_Injected):
        if not isinstance(k, Injectable):
            raise TypeError(f'injector tag must be Injectable not {k.__class__.__name__}: {k}')
            
        if not isinstance(val, InjectorVar):
            val = InjectorVar(self, val)
        self.vars[k] = val
    
    def remove(self, k: T_Injectable):
        try:
            del self.vars[k]
        except KeyError:
            return False
        else:
            return True
    
    def pop(self, k: T_Injectable, default=...):
        val = self.vars.pop(k, default)
        if val is ... is default:
            raise InjectorKeyError(k)
        return val
    
    def __call__(self, key: T_Injectable=None, /, *args, **kwds) -> T_Injected:
        if key is None:
            assert not (args or kwds)
            return self
        else:
            return self.make(key, *args, **kwds)

    def __contains__(self, x) -> bool:
        if isinstance(x, Injector): 
            x = x.scope
        return x in self.vars or x in self.parent

    def __bool__(self) -> bool:
        return True

    def __len__(self) -> bool:
        return len(self.vars) 

    def __str__(self) -> str:
        return f'{self.__class__.__name__}[{self.level}]({self.name!r})'

    def __repr__(self) -> str:
        return f'<{self}, {self.parent!r}>'

    def __enter__(self: 'Injector') -> 'Injector':
        return self.context.__enter__()

    def __exit__(self, *exc):
        return self.context.__exit__(*exc)

    __setitem__ = set
    __delitem__ = remove
    


class _NullInjectorVars(frozendict):
    __slots__ = ()

    def __missing__(self, k):
        if not isinstance(k, Injectable):
            raise TypeError(f'key must be Injectable, not {k.__class__.__name__}')




@export()
class NullInjector(Injector):
    """NullInjector Object"""

    __slots__ = 'name',

    scope = None
    parent = None
    level = -1
    
    def __init__(self, name=None):
        self._ctx = InjectorContext()
        _none_var = InjectorVar(self, value=None)
        self.vars = _NullInjectorVars({ None: _none_var, type(None): _none_var })
        self.name = name or 'null'

    def get(self, k: T_Injectable, default: T = None) -> T: 
        return default
        
    def __contains__(self, x) -> bool:
        return False

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def __missing__(self, k: T_Injectable, args=None, kwds=None) -> None:
        raise InjectorKeyError(f'{k} in {self!r}')
