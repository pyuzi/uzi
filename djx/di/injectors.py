import logging
from functools import partial
from collections.abc import Mapping, MutableMapping
from collections import defaultdict, deque
from contextlib import AbstractContextManager as ContextManager, ExitStack, contextmanager, nullcontext
from types import FunctionType
from contextvars import ContextVar
from typing import Any, Callable, ClassVar, Generic, Optional, Sequence, Type, TypeVar, Union


from flex.utils.decorators import export

from djx.common.utils import Void

from .symbols import _ordered_id
from .providers import ValueResolver
from .abc import ( 
    InjectorContext, InjectorKeyError, Resolver, Scope, ScopeAlias, T,
    T_ContextStack, T_Injectable, T_Injected, T_Injector, T_Provider, _T_Scope, _T_Cache, _T_Providers
)
from . import abc


logger = logging.getLogger(__name__)


@export()
@abc.InjectorContext[T_Injector].register
class InjectorContext(ExitStack, Generic[T_Injector]):


    injector: T_Injector
    parent: 'InjectorContext'
    _booted: bool = None

    _entry_callbacks: deque
    _exit_callbacks: deque

    def __init__(self, injector: T_Injector=None):
        super().__init__()
        self.injector = injector
        self._entry_callbacks = deque()
    
    def pop_all(self):
        """Preserve the context stack by transferring it to a new instance."""
        rv = super().pop_all()
        rv.injector = self.injector
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
        try:
            while self._entry_callbacks:
              self._entry_callbacks.popleft()()
        except Exception as e:
            raise RuntimeError(f'Entering context: {self.injector!r}') from e
       
        return self.injector

    def __call__(self):
        return self
    




@export()
@abc.Injector[_T_Scope, T_Injected, T_Provider, T_Injector].register
class Injector(Generic[_T_Scope, T_Injected, T_Provider, T_Injector]):

    __slots__ = (
        'scope', 'parent', 'cache', 'content', 'level', '__ctx',
        '__booted', '__skipself', '__weakref__', '__missing__',
    )

    scope: _T_Scope
    parent: T_Injector
    content: _T_Providers[T_Provider]
    
    __ctx: InjectorContext[T_Injector]


    level: int
    __skipself: bool
    __booted: bool
    _context_cls = InjectorContext

    def __init__(self, scope: _T_Scope, parent: T_Injector, content: _T_Providers=None) -> None:
        self.scope = scope
        self.parent = parent
        self.level = parent.level + 1 
        self.content = content
        self.__booted = False
        self.__skipself = True
        self.__missing__ = self.__missing_boot__
        self.__ctx = self._create_ctx()
        self._setup_ctx(self.__ctx)

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
        if self.__booted is False:
            self.scope.bootstrap(self)
            self.__booted = True
            self.__skipself = False
            self.__missing__ =  InjectorKeyError if self.parent is None else self.parent.__getitem__
            return True
        return False
    
    def _shutdown(self) -> bool:
        if self.__booted is True:
            self.__booted = None
            self.scope.dispose(self)
            # self.__skipself = True
            return True
        return False

    def _create_ctx(self) -> T_ContextStack:
        return self._context_cls(self)

    def _setup_ctx(self, ctx: T_ContextStack):
        ctx.wrap(self.parent.context)
        ctx.wrap(self._bootmanager())

    @contextmanager
    def _bootmanager(self):
        ind =f'#{self.level}' + '    '*(self.level+1)
        logger.debug(f'{ind}+++{self} start boot context [{self.booted}]+++')
        booted = self.boot()
        logger.debug(f'{ind}+   {self} booted {booted}   +')
        yield self
        if booted and self.shutdown():
            logger.debug(f'{ind}-   {self} destroyed   -')

        logger.debug(f'{ind}---{self} end boot context---')
        
    def __missing_boot__(self, key):
        self.boot()
        return self.__getitem__(key)

    def __contains__(self, x) -> bool:
        if self.__booted:
            return self.content.__contains__(x) or self.parent.__contains__(x)
        else:
            return self.scope.__contains__(x)

    def __bool__(self) -> bool:
        return self.__booted

    def __len__(self) -> bool:
        return len(self.content) if self.__booted else 0

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
        return f'{self.__class__.__name__}#{self.level}({self.scope.name!r})'

    def __repr__(self) -> str:
        return f'<{self} parent={self.parent!r}>'





@export()
@abc.Injector.register
class RootInjector(Generic[T_Injector]):
    """NullInjector Object"""

    __slots__ = 'content', '__ctx',

    scope = None
    parent = None
    level = -1
    
    def __init__(self):
        self.__ctx = InjectorContext(self)
        self.content = {}

    @property
    def final(self):
        return self
 
    @property
    def context(self):
        return self.__ctx
 
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
        raise abc.InjectorKeyError(f'{k} in {head()!r}')

    def __missing__(self, k: T_Injectable) -> None:
        from .di import head
        raise abc.InjectorKeyError(f'{k} in {head()!r}')

    def __str__(self) -> str:
        return f'{self.__class__.__name__}'

    def __repr__(self) -> str:
        return f'{self}'
