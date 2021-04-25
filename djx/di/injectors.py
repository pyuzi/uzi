
from collections.abc import Mapping, MutableMapping
from collections import defaultdict
from contextlib import AbstractContextManager, ExitStack, contextmanager, nullcontext
from types import FunctionType
from contextvars import ContextVar
from typing import Any, Callable, ClassVar, Generic, Optional, Sequence, Type, TypeVar, Union


from flex.utils.decorators import export

from djx.common.utils import Void

from .symbols import _ordered_id
from .abc import ( 
    InjectedContextManager, InjectorContext, InjectorKeyError, Scope, ScopeAlias, T_Injectable, T_Injected, T_Injector, T_Provider, _T_Scope, _T_Cache, _T_Providers
)
from . import abc


@export()
@abc.Injector[_T_Scope, T_Injected, T_Provider, T_Injector].register
class Injector(Generic[_T_Scope, T_Injected, T_Provider, T_Injector]):

    __slots__ = (
        'scope', 'parent', 'cache', 'providers', 'level', '__missing__',
        'exitstack', '__hasbooted', '__skipself', '__weakref__',
    )

    scope: _T_Scope
    parent: T_Injector
    cache: _T_Cache[T_Injected]
    providers: _T_Providers[T_Provider]
    
    context: InjectorContext[T_Injector]

    exitstack: ExitStack

    level: int
    __skipself: bool
    __hasbooted: bool

    def __init__(self, scope: _T_Scope, parent: T_Injector, providers: _T_Providers=None, cache: _T_Cache=None) -> None:
        self.scope = scope
        self.parent = parent
        self.level = 0 if parent is None else parent.level + 1 
        self.providers = providers
        self.cache = cache
        self.__hasbooted = False
        self.__skipself = True
        self.__missing__ = self.__missing_boot__

    @property
    def final(self):
        return self.parent.final if self.__skipself is True else self

    def context(self):
        return self.scope.create_context(self)

    def boot(self: T_Injector) -> bool:
        return self.__boot__()
    
    def destroy(self) -> bool:
        return self.__destroy__()

    def enter(self, cm: InjectedContextManager[T_Injected]) -> T_Injected:
        """Enters the supplied context manager.

        If successful, also pushes its __exit__ method as an exit callback and
        returns the result of the __enter__ method. 
        
        See also: `Injector.onexit()`
        """
        return self.exitstack.enter_context(cm)

    def onexit(self, cb: Union[InjectedContextManager, Callable]):
        """Registers an exit callback. Exit callbacks are called when the 
        injector closes.

        Callback can be a context manager or callable with the standard 
        `ContextManager's` `__exit__` method signature.
        """
        return self.exitstack.push(cb)

    def _setup_exitstack(self):
        self.exitstack = self.scope.create_exitstack(self) 
        self.exitstack.enter_context(self.parent.context())
        self.exitstack.callback(self.destroy)

    def __boot__(self) -> bool:
        if self.__hasbooted is False:
            self._setup_exitstack()
            self.scope.setup(self)
            self.__hasbooted = True

            self.__skipself = False
            self.__missing__ =  InjectorKeyError if self.parent is None else self.parent.__getitem__

            return True
        return False
    
    def __destroy__(self) -> bool:
        if self.__hasbooted:
            self.scope.teardown(self)
            self.__hasbooted = None
            self.exitstack.close()
            return True
        return False

    def __missing_boot__(self, key):
        self.boot()
        return self.__getitem__(key)

    def __contains__(self, x) -> bool:
        if self.__hasbooted:
            return x in self.providers.__contains__(x) or x in self.parent.__contains__(x)
        else:
            return self.scope.__contains__(x)

    def __bool__(self) -> bool:
        return self.__hasbooted

    def __len__(self) -> bool:
        return len(self.providers) if self.__hasbooted else 0

    def __setitem__(self, k: T_Injectable, val: T_Injected):
        self.providers[k] = val
    
    def __delitem__(self, k: T_Injectable):
        try:
            del self.providers[k]
        except KeyError:
            pass
   
    def __getitem__(self, k: T_Injectable) -> T_Injected:
        if self.__skipself:
            return self.__missing__(k)

        rec = self.providers.__getitem__(k)
        if rec is not None:
            return rec(self) if rec.value is Void else rec.value
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

    def __enter__(self, scope: Union[str, ScopeAlias] = None):
        self.boot()
        return self

    def __exit__(self, *exc):
        self.destroy()
   
    @contextmanager
    def __call__(self, name: Union[str, ScopeAlias] = None) -> AbstractContextManager[T_Injector]:
        global _inj_ctxvar
        if name is None:
            return self
        
        cur = _inj_ctxvar.get()
        if name is not None:
            scope = Scope[name]

            if scope is None or scope in cur:
                reset = None

            elif scope not in cur:
                cur = scope().create(cur)
                reset = _inj_ctxvar.set(cur)

        try:
            yield cur
        finally:
            if reset is not None:
                cur.destroy()
                _inj_ctxvar.reset(reset)

_inj_ctxvar = ContextVar[T_Injector]('__inj_ctxvar')



@export()
@abc.Injector.register
class RootInjector(Generic[T_Injector]):
    """NullInjector Object"""

    __slots__ = ()

    scope = None
    parent = None
    level = -1
    
    def __init__(self) -> None:
        global _inj_ctxvar
        _inj_ctxvar.set(self)

    @property
    def final(self):
        return self
 
    def context(self):
        return nullcontext(self)
 
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

    @contextmanager
    def __call__(self, name: Union[str, ScopeAlias] = None) -> AbstractContextManager[T_Injector]:
        global _inj_ctxvar

        cur = _inj_ctxvar.get()

        scope = Scope[name] if name else Scope[Scope.MAIN] if cur is self else None

        if scope is None or scope in cur:
            reset = None

        elif scope not in cur:
            cur = scope().create(cur)
            reset = _inj_ctxvar.set(cur)

        try:
            yield cur
        finally:
            if reset is not None:
                cur.destroy()
                _inj_ctxvar.reset(reset)