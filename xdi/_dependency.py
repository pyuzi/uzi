


from abc import abstractmethod
from enum import Enum, auto
from threading import Lock
from typing_extensions import Self
import attr
import typing as t 

from collections.abc import Callable

from xdi._common import Missing, private_setattr
from . import _wrappers as wrappers
from ._wrappers import CallShape, FutureFactoryWrapper, FutureResourceWrapper, FutureCallableWrapper
from ._functools import BoundParams, _PositionalArgs, _PositionalDeps, _KeywordDeps, _PARAM_VALUE

from . import T_Injectable, T_Injected


if t.TYPE_CHECKING: # pragma: no cover
    from .providers import Provider
    from .scopes import Scope
    from .injectors import Injector
    from .containers import Container



_T_Use = t.TypeVar('_T_Use')

@attr.s(slots=True, frozen=True, cmp=False)
@private_setattr
class Dependency(t.Generic[_T_Use]):

    """Marks an injectable as a `dependency` to be injected."""
    
    @abstractmethod
    def factory(self, injector: 'Injector') -> t.Union[Callable[..., T_Injected], None]: 
        raise NotImplementedError(f'{self.__class__.__name__}.factory()')  # pragma: no cover

    _v_resolver = attr.ib(init=False, default=Missing, repr=False)

    abstract: T_Injectable = attr.ib()
    scope: "Scope" = attr.ib()
    provider: "Provider" = attr.ib(default=None, repr=lambda p: str(p and id(p)))

    concrete: _T_Use = attr.ib(kw_only=True, default=Missing, repr=True)
    is_async: bool = False

    _ash: int = attr.ib(init=False, repr=False)
    @_ash.default
    def _compute_ash_value(self):
        return hash((self.abstract, self.scope, self.container))

    @property
    def container(self):
        if pro := self.provider or self.scope:
            return pro.container

    def __eq__(self, o: Self) -> bool:
        return o.__class__ is self.__class__ and o._ash == self._ash

    def __hash__(self) -> int:
        return self._ash




# @attr.s(slots=True, frozen=True, cmp=False)
# class SimpleDependency(Dependency[_T_Use]):

#     def _make_resolver(self):
#         return self.concrete



# @attr.s(slots=True, frozen=True, cmp=False)
# class ResolvedDependency(Dependency[_T_Use]):

#     def resolver(self, injector: 'Injector'):
#         return self.concrete




@attr.s(slots=True, frozen=True, cmp=False)
class Value(Dependency[T_Injected]):

    concrete: T_Injected = attr.ib(kw_only=True, default=None)
    is_async: t.Final = False

    def factory(self, injector: 'Injector'):
        return self

    def __call__(self) -> T_Injected:
        return self.concrete





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

    concrete: T_Injected = attr.ib(kw_only=True)
    params: 'BoundParams' = attr.ib(kw_only=True, default=BoundParams.make(()))

    shape: CallShape = attr.ib(kw_only=True, converter=CallShape)
    @shape.default
    def _default_shape(self):
        params = self.params
        return CallShape.make(
            not not params.args, 
            not not params.kwds, 
            params.is_async,
            not not self.async_call,
        )

    wrapper: Callable = attr.ib(kw_only=True, default=None)
    @wrapper.validator
    def _default_wrapper(self, attrib, func):
        func = func or self._wrappers[self.shape]
        if pipes := self._pipes.get(self.shape):
            for pipe in pipes:
                func = pipe(func)
        self.__setattr(wrapper=func)

    @property
    def is_async(self):
        return not not(self.async_call or self.params.is_async)

    def factory(self, injector: 'Injector'):
        return self.wrapper(self.concrete, self.params, injector)
    

    def resolve_args(self, injector: "Injector"):
        if self.args:
            if self._pos_vals > 0 < self._pos_deps:
                return _PositionalArgs(
                    (
                        p.bind_type,
                        p.value
                        if p.bind_type is _PARAM_VALUE
                        else injector.find(p.dependency, default=p.default_factory),
                    )
                    for p in self.args
                )
            elif self._pos_deps > 0:
                return _PositionalDeps(
                    injector.find(p.dependency, default=p.default_factory) for p in self.args
                )
            else:
                return tuple(p.value for p in self.args)
        return ()

    def resolve_kwargs(self, injector: "Injector"):
        return _KeywordDeps(
            (p.key, injector.find(p.dependency, default=p.default_factory))
            for p in self.kwds
        )

    def plain_wrapper(self, ctx: "Injector"):
        return self.concrete

    def args_wrapper(self: Self, ctx: "Injector"):
        args = self.resolve_args(ctx)
        vals = self.params.vals
        func = self.concrete
        return lambda: func(*args, **vals)

    def kwds_wrapper(self: Self, ctx: "Injector"):
        kwds = self.resolve_kwargs(ctx)
        vals = self.params.vals
        func = self.concrete
        return lambda: func(**kwds, **vals)

    def args_kwds_wrapper(self: Self, ctx: "Injector"):
        args = self.resolve_args(ctx)
        kwds = self.resolve_kwargs(ctx)
        vals = self.params.vals
        func = self.concrete
        return lambda: func(*args, **kwds, **vals)







@attr.s(slots=True, frozen=True, cmp=False)
class AsyncFactory(Factory[T_Injected]):

    is_async: bool = True




@attr.s(slots=True, frozen=True, cmp=False)
class AwaitParamsFactory(Factory[T_Injected]):
    
    is_async: bool = True
    async_call: bool = attr.ib(default=False, kw_only=True)
    
    def make_future_wrapper(self: Self, ctx: 'Injector', **kwds):
        kwds.setdefault("aw_call", self.async_call)
        return FutureFactoryWrapper(self.concrete, self.vals, **kwds)

    def resolve_kwargs(self, ctx: "Injector"):
        if self.params.aw_kwds:
            deps = super().resolve_kwargs(ctx)
            return deps, tuple((n, deps.pop(n)) for n in self.params.aw_kwds)
        else:
            return super().resolve_kwargs(ctx), ()

    def resolve_args(self, injector: "Injector"):
        return super().resolve_args(injector), self.params.aw_args

    def args_wrapper(self: Self, ctx: "Injector"):
        args, aw_args = self.resolve_args(ctx)
        return self.make_future_wrapper(ctx, args=args, aw_args=aw_args)

    def kwargs_wrapper(self: Self, ctx: "Injector"):
        kwds, aw_kwds = self.resolve_kwargs(ctx)
        return self.make_future_wrapper(ctx, kwds=kwds, aw_kwds=aw_kwds)

    def args_kwargs_wrapper(self: Self, ctx: "Injector"):
        args, aw_args = self.resolve_args(ctx)
        kwds, aw_kwds = self.resolve_kwargs(ctx)
        return self.make_future_wrapper(
            ctx, args=args, kwds=kwds, aw_args=aw_args, aw_kwds=aw_kwds
        )




@attr.s(slots=True, frozen=True, cmp=False)
class Singleton(Factory[T_Injected]):

    _wrappers = Factory._wrappers | {
        CallShape.plain_async : wrappers.plain_future_wrapper,
        CallShape.args_async : wrappers.aw_args_async_wrapper,
        CallShape.kwargs_async : wrappers.aw_kwargs_async_wrapper,
        CallShape.args_kwargs_async : wrappers.aw_args_kwargs_async_wrapper,
    }
    
    thread_safe: bool = attr.ib(default=False)

    def factory(self, injector: 'Injector'):
        func = self.wrapper(self.concrete, self.params, injector)

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
        CallShape.plain: wrappers.enter_context_pipe,
        CallShape.plain: wrappers.enter_context_pipe,
    }

    aw_enter: bool = attr.ib(kw_only=True)

    # def resolver(self, injector: 'Injector'):
    #     func = self.wrapper(self.concrete, self.params, injector)

    #     value = Missing
    #     lock = Lock() if self.thread_safe else None
        
    #     def make():
    #         nonlocal func, value
    #         if value is Missing:
    #             lock and lock.acquire(blocking=True)
    #             try:
    #                 if value is Missing:
    #                     value = func()
    #             finally:
    #                 lock and lock.release()
    #         return value

    #     return make
