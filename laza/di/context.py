import logging
import typing as t
from collections.abc import Callable
from contextvars import ContextVar, Token
from typing_extensions import Self

from laza.common.functools import export

from .common import Injectable, T_Injectable, T_Injected

if t.TYPE_CHECKING:
    from .injectors import Injector, BindingsMap


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

    def __init__(self, injector: "Injector", parent: "InjectorContext"):
        self.__injector = injector
        self.__parent = parent
        self.__bindings = injector.bindings
        self.__exitstack = []
        dict.__setitem__(self, injector, lambda: self)

    @property
    def name(self) -> str:
        return self.__injector.name

    @property
    def injector(self):
        return self.__injector

    def _reset(self, to: Self):
        if not to is self:
            self.__bindings = dict.clear(self)
            logger.debug(f'{self}.reset({to=})')
            self.__parent._reset(to)

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
        return dict.setdefault(self, key, res(self))

    def __contains__(self, x) -> bool:
        return dict.__contains__(self, x) or x in self.__parent

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def __repr__(self) -> str:
        return f"<{self!s}, {self.__parent!r}>"

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
    default=NullInjectorContext()
)





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
            self.__context
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
            raise RuntimeError(f'{self.__context} already active.')

    def __exit__(self, *e):
        if not self.__token is None:
            old = self.__token.old_value
            self.__token = self.__var.reset(self.__token)
            self.__context._reset(old)
            del self.__context


