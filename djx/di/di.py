import logging
from types import GenericAlias
import typing as t


from functools import partial, update_wrapper
from contextvars import ContextVar
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from cachetools.keys import hashkey


from djx.common.proxy import Proxy
from djx.common.utils import export


from .injectors import Injector, NullInjector
from .scopes import Scope, MainScope
from .inspect import signature, ordered_id
from .providers import alias, is_provided, provide, injectable, Depends
from . import abc, signals

from .abc import (
    ANY_SCOPE, LOCAL_SCOPE, MAIN_SCOPE, REQUEST_SCOPE, COMMAND_SCOPE,
    Injectable, InjectorKeyError, ScopeAlias, StaticIndentity, 
    T, T_Injected, T_Injector, T_Injectable
)

if not t.TYPE_CHECKING:
    __all__ = [
        'current',
        'injector',
        'Depends',
        'ANY_SCOPE',
        'LOCAL_SCOPE', 
        'MAIN_SCOPE',
        'REQUEST_SCOPE', 
        'COMMAND_SCOPE',
    ]


logger = logging.getLogger(__name__)


_T_Callable = t.TypeVar('_T_Callable', type, Callable, covariant=True)

__real_main_inj = None

def __get_main_inj():
    global __real_main_inj

    rv = MainScope().create()
    __inj_ctxvar.set(rv)

    if __debug__:
        logger.debug(f'start: {rv!r}')

    return rv


__main_inj = Proxy(__get_main_inj, cache=True, callable=False)
__inj_ctxvar: t.Final = ContextVar[Injector]('__inj_ctxvar', default=__main_inj)


current: Callable[[], Injector] = __inj_ctxvar.get
injector: Injector = Proxy(current, callable=False)



@export()
def proxy(abstract: Injectable[T_Injected], *, callable: bool=None) -> T_Injected: # -> Proxy[T_Injected]:
    def resolve() -> T_Injected:
        return current()[abstract]
    
    return Proxy(resolve, callable=callable)





# @export()
# def after(*what: t.Any, run=None):

#     def resolve():
#         return current()[abstract]
    
#     return Proxy(resolve, callable=callable)




# @export()
# def before(abstract: T_Injectable, *, callable: bool=None) -> T_Injectable: # -> Proxy[T_Injected]:
#     def resolve():
#         return current()[abstract]
    
#     return Proxy(resolve, callable=callable)





@export()
def at(*scopes: t.Union[str, ScopeAlias, type[Scope]], default=...):
    """Get the first available Injector for given scope(s).
    """
    return current().at(*scopes, default=default)



@export()
def make(key, *args, **kwds):
    return current().make(key, *args, **kwds)


@export()
def get(abstract: T_Injectable, default: T = None, /, *args, **kwds):
    return current().get(abstract, default, *args, **kwds)



@export()
def scope(name: t.Union[str, ScopeAlias] = Scope.MAIN) -> T_Injector:
    inj = current()()
    scope = Scope[name]
    if scope not in inj:
        inj = scope().create(inj)
        inj.context.wrap(using(inj))
    return inj



@export()
@contextmanager
def using(inj: t.Union[str, ScopeAlias, T_Injector] = Scope.MAIN) -> AbstractContextManager[T_Injector]:
    cur: Injector[Scope] = current()()

    scope = Scope[inj]
    token = None
    
    if scope not in cur:
        if isinstance(inj, Injector):
            if cur is not inj[cur.scope]:
                raise RuntimeError(f'{inj!r} must be a descendant of {cur!r}.')
            cur = inj
        else:
            cur = scope().create(cur)
        token = __inj_ctxvar.set(cur)
        if __debug__:
            logger.debug(f'set current: {cur!r}')

    try:
        yield current()
    finally:
        if __debug__ and token:
            logger.debug(f'reset current: {token.old_value!r} {id(token.old_value)!r}')
        token is None or __inj_ctxvar.reset(token)



@t.overload
def wrap(cls: type[T], /, *, scope: str=None, priority=-1, **kwds) -> type[T]:
    ...
@t.overload
def wrap(func: Callable[..., T], /, *, scope: str=None, priority=-1, **kwds) -> Callable[..., T]:
    ...
@t.overload
def wrap(*, scope: str=None, priority=-1, **kwds) -> Callable[[_T_Callable], _T_Callable]:
    ...
@export()
def wrap(func: _T_Callable =..., /, *, scope: str=None, **kwds) -> _T_Callable:
    
    scope = scope or ANY_SCOPE

    def decorate(fn):
        aka = WrappedAlias(fn, (scope, ordered_id()))
        provide(aka, scope=scope, factory=fn, **kwds)
        return aka
    
    if func is ...:
        return decorate
    else:
        return decorate(func)






# @export()
# def wrapped(*args, **kwds):
#     def decorate(fn):
#         return wrap(fn, args, kwds)
#     return decorate




@export()
def call(func: Callable[..., T], /, *args: tuple, **kwargs) -> T:
    # inj = __inj_ctxvar.get()
    # params = signature(func).bind_partial(*args, **kwargs)
    return current().make(func, *args, **kwargs)
    # func(*params.inject_args(inj), **params.inject_kwargs(inj))





# class Dependency(t.NamedTuple('_Dependency', dict(depends=T_Injected, scope=t.Any).items())):
class Dependency(t.NamedTuple):

    depends: Injectable[T_Injected] = None
    scope: str = Scope.ANY




@export()
class InjectedProperty(t.Generic[T_Injected]):
    
    __slots__ = '_dep', 'finj', 'cache', '__name__', '_default', '__weakref__'

    _dep: Dependency[T_Injected]
    __name__: str
    cache: bool

    def __init__(self, dep: Injectable[T_Injected]=None, default: T_Injected=..., *, name=None, cache: bool=None, scope=None) -> T_Injected:
        self._default = default
        self.cache = bool(cache)
        self._dep = Dependency(dep, *(scope and (str(scope),) or ()))
        self.__name__ = name
        self.finj = current
        self._register()

    @property
    def depends(self):
        return self._dep.depends

    @property
    def scope(self):
        return self._dep.scope

    def __set_name__(self, owner, name):
        self.__name__ = name

        if self.depends is None:
            dep = t.get_type_hints(owner).get(name)
            if dep is None:
                raise TypeError(
                    f'Injectable not set for {owner.__class__.__name__}.{name}'
                )
            self._dep = self._dep._replace(depends=dep)
        self._register()

    def _register(self):   
        dep = self._dep
        if dep.depends is not None:
            is_provided(dep) or alias(dep, dep.depends, scope=dep.scope)
            # if dep.scope in {ANY_SCOPE, None}:
            #     self.finj = current
            # else:
            #     self.finj = partial(at, dep.scope)

    def __get__(self, obj, typ=None) -> T_Injected:
        if obj is None:
            return self
        try:
            if not self.cache:
                return self.finj().make(self._dep)

            try:
                return obj.__dict__[self.__name__]
            except KeyError:
                val = self.finj().make(self._dep)

        except InjectorKeyError as e:
            if self._default is ...:
                raise AttributeError(self) from e
            return self._default
        else:
            return obj.__dict__.setdefault(self.__name__, val)

    def __str__(self) -> T_Injected:
        return f'{self.__class__.__name__}({self._dep!r})'

    def __repr__(self) -> T_Injected:
        return f'<{self.__name__} = {self}>'



injected_property = export(InjectedProperty, name='injected_property')




@export()
class InjectedClassVar(InjectedProperty[T_Injected]):

    def __get__(self, obj, typ=...) -> T_Injected:
        return super().__get__(typ, typ)


if t.TYPE_CHECKING:
    InjectedClassVar = t.ClassVar[T_Injected]


injected_class_property = export(InjectedClassVar, name='injected_class_property')



@abc.Injectable.register
class WrappedAlias(GenericAlias):

    __slots__ = ()

    # def __new__(cls, orig, *args, **kwds):
    #     if cls is WrappedAlias:
    #         if isinstance(orig, (type, GenericAlias)):
    #             cls = WrappedTypeAlias
    #         else:
    #             cls = WrappedCallableAlias
        
    #     return super().__new__(cls, orig, *args, **kwds)

    def __call__(self, *args, **kwds):
        return current().make(self, *args, **kwds)



# class WrappedTypeAlias(WrappedAlias):

#     __slots__ = ()


# class WrappedCallableAlias(WrappedAlias):

#     __slots__ = ()

