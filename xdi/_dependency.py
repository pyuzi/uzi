


from enum import Enum, auto
from threading import Lock
from typing_extensions import Self
import attr
import typing as t 

from collections.abc import Callable

from xdi._common import Missing
from . import _wrappers as wrappers
from ._wrappers import CallShape

from . import T_Injectable, T_Injected


if t.TYPE_CHECKING: # pragma: no cover
    from .providers.functools import BoundParams
    from .providers import Provider
    from .scopes import Scope
    from .injectors import Injector
    from .containers import Container



_T_Use = t.TypeVar('_T_Use')

@attr.s(slots=True, frozen=True, cmp=False)
class Dependency(t.Generic[_T_Use]):

    """Marks an injectable as a `dependency` to be injected."""
    
    if t.TYPE_CHECKING: # pragma: no cover
        def resolver(self, injector: 'Injector') -> t.Union[Callable[..., T_Injected], None]:
            return self.resolver(injector)

    _v_resolver = attr.ib(init=False, default=Missing, repr=False)

    provides: T_Injectable = attr.ib()
    scope: "Scope" = attr.ib()
    provider: "Provider" = attr.ib(default=None, repr=lambda p: str(p and id(p)))

    use: _T_Use = attr.ib(kw_only=True, default=Missing, repr=True)

    container: 'Container' = attr.ib(init=False, repr=False)
    @container.default
    def _default_container(self):
        return self.provider and self.provider.container or self.scope.container

    _ash: int = attr.ib(init=False, repr=False)
    @_ash.default
    def _compute_ash_value(self):
        return hash((self.provides, self.scope, self.container))

    @property
    def container(self):
        if pro := self.provider:
            return pro.container

    @property
    def is_async(self):
        return getattr(self.resolver, 'is_async', False)

    @property
    def resolver(self):
        if rv := self._v_resolver:
            return rv
        self.__set_attr(_v_resolver=self._make_resolver())
        return self._v_resolver

    def __init_subclass__(cls, *args, **kwargs):
        if not hasattr(cls, fn := f'_{cls.__name__}__set_attr'):
            setattr(cls, fn, getattr(Dependency, '_Dependency__set_attr'))

    def __eq__(self, o: Self) -> bool:
        return o.__class__ is self.__class__ and o._ash == self._ash

    def __hash__(self) -> int:
        return self._ash

    def _make_resolver(self):
        return self.provider.bind(self.scope, self.provides)

    def __set_attr(self, name=None, value=None, /, **kw):
        name and kw.setdefault(name. value)
        for k,v in kw.items():
            object.__setattr__(self, k, v)




@attr.s(slots=True, frozen=True, cmp=False)
class SimpleDependency(Dependency[_T_Use]):

    def _make_resolver(self):
        return self.use



@attr.s(slots=True, frozen=True, cmp=False)
class ResolvedDependency(Dependency[_T_Use]):

    def resolver(self, injector: 'Injector'):
        return self.use




@attr.s(slots=True, frozen=True, cmp=False)
class Value(Dependency[T_Injected]):

    use: T_Injected = attr.ib(kw_only=True)
    is_async: t.Final = False

    def resolver(self, injector: 'Injector'):
        return self

    def __call__(self) -> T_Injected:
        return self.use





@attr.s(slots=True, frozen=True, cmp=False)
class Factory(Dependency[T_Injected]):

    _wrappers = {
        CallShape.plain : wrappers.plain_wrapper,
        CallShape.plain_async : wrappers.plain_async_wrapper,

        CallShape.args : wrappers.args_wrapper,
        CallShape.aw_args : wrappers.aw_args_wrapper,
        CallShape.args_async : wrappers.args_async_wrapper,
        CallShape.aw_args_async : wrappers.aw_args_async_wrapper,

        CallShape.kwargs : wrappers.kwargs_wrapper,
        CallShape.aw_kwargs : wrappers.aw_kwargs_wrapper,
        CallShape.kwargs_async : wrappers.kwargs_async_wrapper,
        CallShape.aw_kwargs_async : wrappers.aw_kwargs_async_wrapper,

        CallShape.args_kwargs : wrappers.args_kwargs_wrapper,
        CallShape.aw_args_kwargs : wrappers.aw_args_kwargs_wrapper,
        CallShape.args_kwargs_async : wrappers.args_kwargs_async_wrapper,
        CallShape.aw_args_kwargs_async : wrappers.aw_args_kwargs_async_wrapper,
    }
    
    _pipes = {

    }

    use: T_Injected = attr.ib(kw_only=True)
    async_call: bool = attr.ib(default=False, kw_only=True)
    params: 'BoundParams' = attr.ib(kw_only=True)

    shape: CallShape = attr.ib(kw_only=True, converter=CallShape)
    @shape.default
    def _default_shape(self):
        params = self.params
        return CallShape((
            not not params.args, 
            not not params.kwds, 
            params.is_async,
            self.async_call,
        ))

    wrapper: Callable = attr.ib(kw_only=True, default=None)
    @wrapper.validator
    def _default_wrapper(self, attrib, func):
        func = self._wrappers[self.shape]
        if pipes := self._pipes.get(self.shape):
            for pipe in pipes:
                func = pipe(func)
        self.__set_attr(wrapper=func)

    @property
    def is_async(self):
        return self.async_call or self.params.is_async

    def resolver(self, injector: 'Injector'):
        return self.wrapper(self.use, self.params, injector)






@attr.s(slots=True, frozen=True, cmp=False)
class Singleton(Factory[T_Injected]):

    _wrappers = Factory._wrappers | {
        CallShape.plain_async : wrappers.plain_future_wrapper,
        CallShape.args_async : wrappers.aw_args_async_wrapper,
        CallShape.kwargs_async : wrappers.aw_kwargs_async_wrapper,
        CallShape.args_kwargs_async : wrappers.aw_args_kwargs_async_wrapper,
    }
    
    thread_safe: bool = attr.ib(default=False)

    def resolver(self, injector: 'Injector'):
        func = self.wrapper(self.use, self.params, injector)

        value = Missing
        lock = Lock() if self.thread_safe else None
        
        def make():
            nonlocal func, value
            if value is Missing:
                lock and lock.acquire(blocking=True)
                try:
                    if value is Missing:
                        value = func()
                finally:
                    lock and lock.release()
            return value

        return make





@attr.s(slots=True, frozen=True, cmp=False)
class Resource(Singleton[T_Injected]):

   
    _wrappers = Singleton._wrappers | {
        CallShape.plain : wrappers.enter_context_pipe(wrappers.plain_wrapper),
        CallShape.plain_async : wrappers.plain_async_wrapper,

        CallShape.args : wrappers.args_wrapper,
        CallShape.aw_args : wrappers.aw_args_wrapper,
        CallShape.args_async : wrappers.args_async_wrapper,
        CallShape.aw_args_async : wrappers.aw_args_async_wrapper,

        CallShape.kwargs : wrappers.kwargs_wrapper,
        CallShape.aw_kwargs : wrappers.aw_kwargs_wrapper,
        CallShape.kwargs_async : wrappers.kwargs_async_wrapper,
        CallShape.aw_kwargs_async : wrappers.aw_kwargs_async_wrapper,

        CallShape.args_kwargs : wrappers.args_kwargs_wrapper,
        CallShape.aw_args_kwargs : wrappers.aw_args_kwargs_wrapper,
        CallShape.args_kwargs_async : wrappers.args_kwargs_async_wrapper,
        CallShape.aw_args_kwargs_async : wrappers.aw_args_kwargs_async_wrapper,
    }

    _pipes = {

    }

    aw_enter: bool = attr.ib(kw_only=True)

    def resolver(self, injector: 'Injector'):
        func = self.wrapper(self.use, self.params, injector)

        value = Missing
        lock = Lock() if self.thread_safe else None
        
        def make():
            nonlocal func, value
            if value is Missing:
                lock and lock.acquire(blocking=True)
                try:
                    if value is Missing:
                        value = func()
                finally:
                    lock and lock.release()
            return value

        return make
