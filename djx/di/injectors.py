import logging
from functools import partial
from threading import Lock
from collections.abc import Mapping, MutableMapping
from collections import defaultdict, deque
from contextlib import AbstractContextManager as ContextManager, ExitStack, contextmanager, nullcontext
from types import FunctionType
from contextvars import ContextVar
from typing import Any, Callable, ClassVar, Generic, Optional, Sequence, Type, TypeVar, Union
from djx.common.collections import fluentdict


from flex.utils.decorators import export

from djx.common.utils import Void

from .symbols import _ordered_id
from .providers import ValueResolver
from .abc import ( 
    InjectorContext, InjectorKeyError, Resolver, Scope, ScopeAlias, T,
    T_ContextStack, T_Injectable, T_Injected, T_Injector, T_Provider, T_Scope, _T_Providers
)
from . import abc

__all__ = [
    'INJECTOR_TOKEN',    
]


logger = logging.getLogger(__name__)


INJECTOR_TOKEN = f'{__package__}.Injector'


@export()
@abc.InjectorContext[T_Injector].register
class InjectorContext(ExitStack, Generic[T_Injector]):


    injector: T_Injector
    parent: 'InjectorContext'
    _booted: bool = None

    _entry_callbacks: deque
    _exit_callbacks: deque
    _level: int

    def __init__(self, injector: T_Injector=None):
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

    def __enter__(self) -> T_Injector:
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
    




@export()
@abc.Injector[T_Scope, T_Injected, T_Provider, T_Injector].register
class Injector(Generic[T_Scope, T_Injected, T_Provider, T_Injector]):

    __slots__ = (
        'scope', 'parent', 'cache', 'content', 'level', '__ctx',
        '__booted', '__skipself', '__weakref__', '__missing__',
    )

    scope: T_Scope
    parent: T_Injector
    content: _T_Providers[T_Provider]
    
    __ctx: InjectorContext[T_Injector]


    level: int
    __skipself: bool
    __booted: bool

    def __init__(self, scope: T_Scope, parent: T_Injector=None, content: _T_Providers=None) -> None:
        self.scope = scope
        self.parent = NullInjector() if parent is None else parent
        self.level = 0 if parent is None else parent.level + 1 
        self.content = content
        self.__booted = False
        self.__skipself = False
        self.__missing__ = self.parent.__getitem__
        self.__ctx = scope.create_context(self)

    @property
    def final(self):
        return self.parent.final if self.__skipself is True else self

    @property
    def context(self):
        return self.__ctx

    @property
    def booted(self):
        return self.__booted

    def boot(self: T_Injector) -> bool:
        return self._boot()
    
    def shutdown(self) -> bool:
        return self._shutdown()
    
    def _boot(self) -> bool:
        # if self.__booted is False:
            
            # self.scope.bootstrap(self)

            # self.__booted = True
            # self.__skipself = False
            # self.__missing__ =  InjectorKeyError if self.parent is None else self.parent.__getitem__
            # return True
        return False
    
    def _shutdown(self) -> bool:
        # if self.__booted is True:
        #     self.__booted = False
        #     self.scope.dispose(self)
        #     return True
        return False

    def _setup_ctx(self, ctx: T_ContextStack):
        ctx.wrap(self.parent.context)
        ctx.push(self._shutdown)

    @contextmanager
    def _bootmanager(self):
        ind =f'#{self.level}' + '    '*(self.level+1) + '  '
        logger.debug(f'{ind}+++{self} start boot context [{self.booted}]+++')
        booted = self.boot()
        logger.debug(f'{ind}+   {self} booted {booted}   +')
        try:
            yield self
        finally:
            booted and self.shutdown()
            logger.debug(f'{ind}-   {self} destroyed   -')

        logger.debug(f'{ind}---{self} end boot context---')
    
    def get(self, k: T_Injectable, default: T=None) -> Union[T_Injected, T]: 
        try:
            return self[k]
        except InjectorKeyError:
            return default
        
    # def __boot_on_missing__(self, key):
    #     self.__enter__()
    #     return self.__getitem__(key)

    def __contains__(self, x) -> bool:
        if True or self.__booted:
            return self.content.__contains__(x) or \
                (bool(self.parent) and self.parent.__contains__(x))
        else:
            return self.scope.__contains__(x)

    def __bool__(self) -> bool:
        return True

    def __len__(self) -> bool:
        return len(self.content)# if self.__booted else 0

    def __setitem__(self, k: T_Injectable, val: T_Injected):
        self.content[k] = val if isinstance(val, Resolver) else ValueResolver(val)
    
    def __delitem__(self, k: T_Injectable):
        try:
            del self.content[k]
        except KeyError:
            pass
   
    def __getitem__(self, k: T_Injectable) -> T_Injected:
        if self.__skipself:
            return self.__missing__(k)

        rec = self.content.__getitem__(k)
        if rec is not None:
            return rec.__call__() if rec.value is Void else rec.value
        else:
            try:
                self.__skipself = True
                return self.__missing__(k)
            finally:
                self.__skipself = False
                
    def __str__(self) -> str:
        return f'{self.__class__.__name__}[{self.level}]({self.scope.name!r})'

    def __repr__(self) -> str:
        return f'<{self}, {self.parent!r}>'

    def __call__(self: T_Injector) -> T_Injector:
        return self
    
    def __enter__(self: T_Injector) -> T_Injector:
        return self.context.__enter__()

    def __exit__(self, *exc):
        return self.context.__exit__(*exc)





@export()
@abc.Injector.register
class NullInjector(Generic[T_Injector]):
    """NullInjector Object"""

    __slots__ = 'content', '__ctx',

    scope = None
    parent = None
    level = -1
    
    def __init__(self):
        self.__ctx = InjectorContext()
        self.content = fluentdict()

    @property
    def final(self):
        return self
 
    @property
    def context(self):
        return self.__ctx
 
    def get(self, k: T_Injectable, default: T = None) -> T: 
        return default
        
    def __contains__(self, x) -> bool:
        return False

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def __iter__(self) -> None:
        return iter(())
    
    def __getitem__(self, k: T_Injectable) -> None:
        from .di import head
        raise InjectorKeyError(f'{k} in {head()!r}')

    def __missing__(self, k: T_Injectable) -> None:
        from .di import head
        raise InjectorKeyError(f'{k} in {head()!r}')

    def __str__(self) -> str:
        return f'{self.__class__.__name__}'

    def __repr__(self) -> str:
        return f'{self}'

    def __call__(self: T_Injector) -> T_Injector:
        return self

    def __enter__(self: T_Injector) -> T_Injector:
        return self.context.__enter__()

    def __exit__(self, *exc):
        return self.context.__exit__(*exc)

