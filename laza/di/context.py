from contextlib import AbstractContextManager
import logging
from threading import Lock
import typing as t
from collections.abc import Callable
from contextvars import ContextVar, Token
from typing_extensions import Self

from laza.common.functools import export

from .common import Injectable, T_Injectable, T_Injected
from .util import ExitStack



if t.TYPE_CHECKING:
    from .injectors import Injector, BindingsMap


_T = t.TypeVar('_T')

logger = logging.getLogger(__name__)



TContextBinding = Callable[
    ["InjectorContext", t.Optional[Injectable]], Callable[..., T_Injected]
]




def context_partial(provider: Injectable):

    def wrapper(*a, **kw):
        nonlocal provider
        return  __ctxvar.get()[provider](*a, **kw)
    
    wrapper.__dependency__ = provider

    return wrapper
    

def run_forever(injector: 'Injector'):
    wire(injector).__enter__()
  

def run(injector: 'Injector', func, /, *args, **kwargs):
    with wire(injector) as ctx:
        return ctx[func](*args, **kwargs)
  

def wire(injector: 'Injector'):
    return ContextManager(injector, __ctxvar)
  
  
  



@export()
class InjectorContext(dict[T_Injectable, Callable[..., T_Injected]]):

    __slots__ = (
        '__injector',
        '__parent',
        '__exitstack',
        '__bindings',
    )

    __injector: "Injector"
    __parent: Self
    __bindings: "BindingsMap"
    __exitstack: ExitStack

    if not t.TYPE_CHECKING:
        _lock_class = Lock

    def __init__(self, parent: "InjectorContext", injector: "Injector", bindings: 'BindingsMap'):
        self.__parent = parent
        self.__injector = injector
        self.__bindings = bindings
        self.__exitstack = ExitStack()
        # dict.__setitem__(self, injector, lambda: self)

    @property
    def name(self) -> str:
        return self.__injector.name

    @property
    def base(self) -> str:
        return self

    @property
    def injector(self):
        return self.__injector
        
    @property
    def parent(self):
        return self.__parent
      
    def lock(self) -> t.Union[AbstractContextManager, None]:
        if cls := self._lock_class():
            return cls()

    def exit(self, exit):
        """Registers a callback with the standard __exit__ method signature.

        Can suppress exceptions the same way __exit__ method can.
        Also accepts any object with an __exit__ method (registering a call
        to the method instead of the object itself).
        """
        # We use an unbound method rather than a bound method to follow
        # the standard lookup behaviour for special methods.
        return self.__exitstack.exit(exit)
        
    def enter(self, cm):
        """Enters the supplied context manager.

        If successful, also pushes its __exit__ method as a callback and
        returns the result of the __enter__ method.
        """
        # We look up the special methods on the type to match the with
        # statement.
        return self.__exitstack.enter(cm)

    def callback(self, callback, /, *args, **kwds):
        """Registers an arbitrary callback and arguments.

        Cannot suppress exceptions.
        """
        return self.__exitstack.callback(callback, *args, **kwds)

    def __exit__(self, *er):
        return self.__exitstack.flush(er)

    def get(self, key, default=None):
        rv = self[key]
        if rv is None:
            return default
        return rv

    def first(self, *keys):
        for key in keys:
            rv = self[key]
            if not rv is None:
                return rv

    def __missing__(self, key):
        res = self.__bindings[key]
        if res is None:
            return dict.setdefault(self, key, self.__parent[key])
        return dict.setdefault(self, key, res(self) or self.__parent[key])

    def __contains__(self, x) -> bool:
        return dict.__contains__(self, x) or x in self.__parent

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def __repr__(self) -> str:
        return f"<{self!s}, {self.parent!r}>"

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
    __init__ = __getitem__ = __missing__ = __contains__ = _reset = noop
    del noop
    



__ctxvar: ContextVar['InjectorContext'] = ContextVar(
    f'{__package__}.InjectorContext',
)


__ctxvar.set(NullInjectorContext())


class ContextManager:

    __slots__ = '__injector', '__token', '__context', '__var'

    __injector: 'Injector'
    __token: Token
    __context: InjectorContext
    __var: ContextVar[InjectorContext]

    def __new__(cls, injector: 'Injector', var: ContextVar[InjectorContext]):
        self = object.__new__(cls)
        self.__var = var
        self.__injector = injector
        return self

    def __enter__(self):
        try:
            self.__token
        except AttributeError:
            cur = self.__var.get()
            if self.__injector in cur:
                self.__context = cur
                self.__token = None
            else:
                self.__context = self.__injector.create_context(cur)
                self.__token = self.__var.set(self.__context)
            return self.__context
        else:
            raise RuntimeError(f'context already active: {self.__context}')

    def __exit__(self, *e):
        if not self.__token is None:
            old = self.__token.old_value
            self.__token = self.__var.reset(self.__token)
            ctx = self.__context
            while not ctx is old:
                ctx.__exit__(*e)
                ctx = ctx.parent

            del self.__context
            



