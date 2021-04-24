
from collections.abc import Mapping, MutableMapping
from collections import defaultdict
from contextlib import ExitStack, nullcontext
from types import FunctionType
from contextvars import ContextVar
from typing import Any, Callable, ClassVar, Generic, Optional, Sequence, Type, TypeVar, Union


from flex.utils.decorators import export


from .symbols import _ordered_id
from .abc import ( 
    InjectedContextManager, InjectorContext, Scope, T_Injectable, T_Injected, T_Injector, T_Provider, _T_Scope, _T_Cache, _T_Providers
)
from . import abc


@export()
@abc.Injector[_T_Scope, T_Injected, T_Provider, T_Injector].register
class Injector(Generic[_T_Scope, T_Injected, T_Provider, T_Injector]):

    __slots__ = (
        'scope', 'parent', 'cache', 'providers', 'level', 
        'exitstack', '_issetup', '__skipself', '__weakref__'
    )

    scope: _T_Scope
    parent: T_Injector
    cache: _T_Cache[T_Injected]
    providers: _T_Providers[T_Provider]
    
    context: InjectorContext[T_Injector]

    exitstack: ExitStack

    level: int
    __skipself: bool

    def __init__(self, scope: _T_Scope, parent: T_Injector, providers: _T_Providers=None, cache: _T_Cache=None) -> None:
        self.scope = scope
        self.parent = parent
        self.level = 0 if parent is None else parent.level + 1 
        self.providers = providers
        self.cache = cache
        self._issetup = False
        self.__skipself = False

    @property
    def final(self):
        return self.parent.final if self.__skipself is True else self

    def context(self):
        return self.scope.create_context(self)

    def setup(self: T_Injector) -> bool:
        if not self._issetup:
            self._setup_exitstack()
            self.scope.setup(self)
            self._issetup = True
            return True
        return False
    
    def close(self):
        if self._issetup:
            self.scope.teardown(self)
            self._issetup = False
            self.exitstack.close()
            return True
        return False

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
        self.exitstack.callback(self.close)

    def __contains__(self, x) -> bool:
        if self._issetup:
            return x in self.providers.__contains__(x) or x in self.parent.__contains__(x)
        else:
            return False

    def __bool__(self) -> bool:
        return self._issetup

    def __len__(self) -> bool:
        return len(self.providers) if self._issetup else 0

    # def __iter__(self) -> bool:
    #     return iter(self.providers)
        
    def __setitem__(self, k: T_Injectable, val: T_Injected):
        self.cache[k] = val
    
    def __delitem__(self, k: T_Injectable):
        try:
            del self.cache[k]
        except KeyError:
            pass
   
    def __getitem__(self, k: T_Injectable) -> T_Injected:
        if self.__skipself:
            return self.parent.__getitem__(k)
        elif (p := self.providers[k]) is not None:
            if p.cache and k in self.cache:
                return self.cache[k]

            if isinstance(p, list):
                rv = [_p(self) for _p in p]
            else:
                rv = p(self)
            
            if p.cache:
                self.cache[k] = rv
            return rv
        elif k is self.__class__:
            return self
        else:
            return self.__missing__(k)
            
    def __missing__(self, k: T_Injectable) -> T_Injected:
        try:
            self.__skipself = True
            return self.parent.__getitem__(k)
        finally:
            self.__skipself = False

    def __str__(self) -> str:
        return f'{self.__class__.__name__}#{self.level}({self.scope.name!r})'

    def __repr__(self) -> str:
        return f'<{self} parent={self.parent!r}>'



@export()
@abc.Injector.register
class NullInjector:
    """NullInjector Object"""

    __slots__ = ()

    scope = None
    parent = None
    level = -1
    

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
