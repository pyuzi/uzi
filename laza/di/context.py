from functools import wraps
import logging
import typing as t
from abc import ABCMeta, abstractmethod
from collections import deque
from collections.abc import Callable
from contextvars import ContextVar, Token
from threading import Lock
from typing_extensions import Self

from laza.common.collections import orderedset, frozendict
from laza.common.functools import calling_frame, export

from .common import Injectable, T_Injectable, T_Injected

if t.TYPE_CHECKING:
    from .injectors import Injector, BindingsDict
    from .providers import Provider


logger = logging.getLogger(__name__)



TContextBinding = Callable[
    ["InjectorContext", t.Optional[Injectable]], Callable[..., T_Injected]
]




def context_partial(provider: Injectable):

    def wrapper(*a, **kw):
        nonlocal provider
        return  __ctxvar.get()[provider](*a, **kw)
        
    return wrapper
    


def _InjectorContext__set(context: 'InjectorContext'):
    return __ctxvar.set(context)


def _InjectorContext__reset(token):
    __ctxvar.reset(token)



def _InjectorContext__get() -> 'InjectorContext':
    return __ctxvar.get()


def _current_context() -> 'InjectorContext':
    return __ctxvar.get()


def run_forever(injector: 'Injector'):
    injector.create_context(__ctxvar.get()).__enter__()
  

def run(injector: 'Injector', func, /, *args, **kwargs):
    with InjectorContext(injector, __ctxvar.get()) as ctx:
        return ctx[func](*args, **kwargs)
  

@export()
class InjectorContext(dict[T_Injectable, Callable[..., T_Injected]]):

    __slots__ = (
        '__injector',
        '__parent',
        '__token',
        '__bindings',
        '__depth',
    )

    __token: Token
    __injector: "Injector"
    __parent: Self
    __bindings: "BindingsDict"
    __depth: int

    def __init__(self, injector: "Injector", parent: "InjectorContext"):
        self.__injector = injector
        self.__parent = parent
        self.__depth = 0

    @property
    def name(self) -> str:
        return self.__injector.name

    @property
    def injector(self):
        return self.__injector

    def __enter__(self, top: Self=None):
        if self.__depth == 0:
            self.__depth += 1

            # parent: Self
            # pinjector: 'Injector'
            # injector: 'Injector' = self.__injector
            # if pinjector := injector.parent:
            #     parent = __get() # type: ignore
            #     if not parent.injector is pinjector:
            #         pass
            #     parent: Self = token.old_value 
            #     if parent.injector is injector:
            #         self = parent
            #     elif pinjector := injector.parent:
            #             if not pinjector is parent.injector:
            #                 parent = self.__class__(pinjector)

            #                 p = pinjector.create_context(parent)

                
            token = __set(self) if top is None else None # type: ignore
            
            self.__token = token
            self.__parent.__enter__(top or self)
            self.__bindings = self.__injector._bindings
        elif top is None:
            raise RuntimeError(f"{self} already dispatched.")
        else:
            self.__depth += 1
        return self

    def __exit__(self, *err):
        if self.__depth == 1:
            self.__depth -= 1
            self.__token = self.__token and __reset(self.__token) # type: ignore
            self.__bindings = dict.clear(self)
            self.__parent.__exit__(err)
        elif self.__depth < 0:
            raise RuntimeError(f"{self} already disposed.")
        elif top is None:
            raise RuntimeError(
                f"{self} has {self.__depth} pending nested dispatches."
            )
        else:
            self.__depth -= 1

    def get(self, key, default=None):
        rv = self[key]
        if rv is None:
            return default
        return rv

    def __missing__(self, key):
        res = self.__bindings[key]
        if res is None:
            return dict.setdefault(self, key, self.__parent[key])
        return dict.setdefault(self, key, res(self, key))

    def __contains__(self, x) -> bool:
        return dict.__contains__(self, x) or x in self.__parent

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def __repr__(self) -> str:
        return f"<{self!s}, {self.__parent!r}>"

    # def __enter__(self: "InjectorContext") -> "InjectorContext":
    #     return self.__enter__()

    # def __exit__(self, *exc):
    #     self.__exit__()

    def __eq__(self, x):
        return x is self

    def __ne__(self, x):
        return not self.__eq__(x)

    def __hash__(self):
        return id(self)
    
    def not_mutable(self, *a, **kw):
        raise TypeError(f'immutable type: {self} ')

    __delitem__ = __setitem__ = setdefault = \
        pop = popitem = update = clear = \
        copy = __copy__ = __reduce__ = __deepcopy__ = not_mutable
    del not_mutable
   

@export()
class NullInjectorContext(InjectorContext):
    """NullInjector Object"""

    __slots__ = ()

    name: t.Final = None
    injector = parent = None

    def noop(slef, *a, **kw): 
        ...
    __init__ = __getitem__ = __missing__ = __contains__ = __enter__ = __exit__ = noop
    del noop
    



__ctxvar: ContextVar['InjectorContext'] = ContextVar(
    f'{__package__}.InjectorContext', 
    default=NullInjectorContext()
)

