from abc import ABCMeta, abstractmethod
from collections import deque
from contextvars import ContextVar, Token
from threading import Lock
import typing as t 
import logging
from collections.abc import Callable



from laza.common.functools import export, calling_frame
from laza.common.collections import orderedset



from .common import (
    Injectable, 
    T_Injectable,
    T_Injected,
)


if t.TYPE_CHECKING:
    from .injectors import Injector


logger = logging.getLogger(__name__)



TContextBinding =  Callable[['InjectorContext', t.Optional[Injectable]], Callable[..., T_Injected]]



def current_context(default):
    pass



class BindingsDict(dict[Injectable, TContextBinding]):

    __slots__ = 'injector',

    injector: 'Injector'

    def __init__(self, injector: 'Injector'):
        self.injector = injector

    def __missing__(self, key):
        inj = self.injector
        provider = inj.get_provider(key)
        if not provider is None:
            return self.setdefault(key, provider.bind(inj, key))
        



@export()
class InjectorContext(dict[T_Injectable, Callable[..., T_Injected]]):

    __slots__ = (
        "injector",
        "parent",
        "_bindings",
        "_dispatched",
        "__weakref__",
    )

    injector: "Injector"
    parent: "InjectorContext"
    _bindings: BindingsDict[T_Injected]
    # manager: 'ContextManager'

    def __init__(self, injector: "Injector", parent: "InjectorContext" = None) -> None:
        self.injector = injector
        self.parent = NullInjectorContext() if parent is None else parent
        # self.bindings = None
        self._dispatched = 0
        self[injector] = lambda: self

    @property
    def name(self) -> str:
        return self.injector.name

    def _dispatch(self, head: 'InjectorContext'=None):
        self._dispatched += 1
        if self._dispatched == 1:
            self.parent._dispatch(head or self)
            self.injector._push(self, head)

            self._bindings = self.injector._bindings
            return True 
        elif head is None:
            raise RuntimeError(f'{self} already dispatched.')
        return False

    def _dispose(self, head: 'InjectorContext'=None):
        self._dispatched -= 1
        if self._dispatched == 0:
            self.parent._dispose(head or self)
            self.injector._pop(self)
            del self._bindings
            return True
        elif self._dispatched < 0:
            raise RuntimeError(f"{self} already disposed.")
        elif head is None:
            raise RuntimeError(f"{self} has {self._dispatched} pending nested dispatches.")
        return False

    def get(self, key, default=None):
        rv = self[key]
        if rv is None:
            return default
        return rv

    def __missing__(self, key):
        res = self._bindings[key]
        if res is None:
            return self.setdefault(key, self.parent[key])
        return self.setdefault(key, res(self, key))

    def __contains__(self, x) -> bool:
        return super().__contains__(x) or x in (self.parent or ())

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def __repr__(self) -> str:
        return f"<{self!s}, {self.parent!r}>"

    def __enter__(self: "InjectorContext") -> "InjectorContext":
        self._dispatch()
        return self

    def __exit__(self, *exc):
        self._dispose()

    def __eq__(self, x):
        return x is self
    
    def __ne__(self, x):
        return not self.__eq__(x)
    
    def __hash__(self):
        return id(self)
    



@export()
class NullInjectorContext(InjectorContext):
    """NullInjector Object"""

    __slots__ = ("name",)

    injector = None
    parent = None

    def __init__(self, name=None):
        self._bindings = None
        self.name = name or "null"

    def __getitem__(self, k: T_Injectable) -> None:
        return None

    def __contains__(self, x) -> bool: 
        return False

    __missing__ = __getitem__

    def get(key, default=None):
        return default

    def _dispatch(self, head: 'InjectorContext'):
        return False

    def _dispose(self, head: 'InjectorContext'):
        return False





_T_Ctx = t.TypeVar('_T_Ctx', bound=InjectorContext, covariant=True)
_T_Src = t.TypeVar('_T_Src', bound=ContextVar[InjectorContext])


class ContextManager(t.Generic[_T_Ctx, _T_Src], metaclass=ABCMeta):

    __slots__ = '__name__', '_index',

    __stack: t.Final[deque['ContextManager[_T_Ctx, _T_Src]']] = deque([None])
    __lock: t.Final = Lock()
    

    def __new__(cls, *a, **kw):
        self = object.__new__(cls)
        self.__name__ = f"{calling_frame(globals=True)['__package__']}"
        return self
           
    def __init__(self, name=None) -> None:
        if not name is None:
            self.__name__ = name
    
    @property
    @abstractmethod
    def src(self) -> _T_Src:
        ...

    @abstractmethod
    def __call__(self) -> _T_Ctx:
        ...

    @abstractmethod
    def get(self, *default) -> _T_Ctx:
        ...

    @abstractmethod
    def set(self, obj: _T_Ctx) -> Token[_T_Ctx]:
        ...

    @abstractmethod
    def reset(self, obj: Token[_T_Ctx]):
        ...

    # def push(self, injector: 'Injector'):
    #     src = self._src
    #     ctx = src.get()
    #     if  injector in ctx:
    #         return 
        
    #     return

    # def pop(self):
    #     return
        
    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(src={self.src!r})'





class ContextVarManager(ContextManager[_T_Ctx, ContextVar[_T_Ctx]]):

    __slots__ = 'src', '__call__',

    src: ContextVar[_T_Ctx]

    def __init__(self, name=None, *, default=NullInjectorContext()) -> None:
        super().__init__(name)
        self.src = src = ContextVar(f'{self.__name__}.InjectorContext', default=default)
        self.__call__ = lambda: src.get()

    def get(self, *default):
        return self.src.get(*default)

    def set(self, obj: _T_Ctx):
        return self.src.set(obj)

    def reset(self, obj: Token[_T_Ctx]):
        return self.src.reset(obj)



if t.TYPE_CHECKING:
    def context_manager() -> _T_Ctx:
        ...


context_manager: t.Final = ContextVarManager(f'{__package__}.__main__')

