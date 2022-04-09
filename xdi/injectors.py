import logging
import sys
import typing as t
from collections.abc import Callable
from types import MethodType

import attr
from typing_extensions import Self

from . import Injectable, T_Default, T_Injectable, T_Injected
from ._common import Missing
from ._dependency import Dependency

if t.TYPE_CHECKING:
    from .scopes import Scope

logger = logging.getLogger(__name__)

_T = t.TypeVar('_T')


TContextBinding = Callable[
    ["Injector", t.Optional[Injectable]], Callable[..., T_Injected]
]


class InjectorLookupError(LookupError):

    key: Injectable
    injector: "Injector"

    def __init__(self, key=None, injector: "Injector" = None) -> None:
        self.key = key
        self.injector = injector

    def __str__(self) -> str:
        key, injector = self.key, self.injector
        return (
            ""
            if key is None is injector
            else f"{key!r}"
            if injector is None
            else f"at {injector!r}"
            if key is None
            else f"{key!r} at {injector!r}"
        )


@attr.s(slots=True, frozen=True, cmp=False)
class Injector(dict[T_Injectable, Callable[[], T_Injected]]):

    parent: Self = attr.field()
    scope: "Scope" = attr.field()

    is_async: bool = attr.field(default=False, kw_only=True)
    exitstack: '_InjectorExitStack' = attr.field(factory=lambda: _InjectorExitStack())

    @property
    def name(self) -> str:
        return self.scope.name

    @t.overload
    def find(
        self, dep: T_Injectable, *fallbacks: T_Injectable
    ) -> Callable[[], T_Injected]:
        ...

    @t.overload
    def find(
        self, dep: T_Injectable, *fallbacks: T_Injectable, default: T_Default
    ) -> t.Union[Callable[[], T_Injected], T_Default]:
        ...

    def find(self, *keys, default=Missing):
        for key in keys:
            rv = self[key]
            if rv is None:
                continue
            return rv

        if default is Missing:
            raise InjectorLookupError(key, self)

        return default

    def make(
        self, key: T_Injectable, *fallbacks: T_Injectable, default=Missing
    ) -> T_Injected:
        if fallbacks:
            func = self.find(key, *fallbacks, default=None)
        else:
            func = self[key]

        if not func is None:
            return func()
        elif default is Missing:
            raise InjectorLookupError(key, self)
        return default

    def call(self, func: Callable[..., T_Injected], *args, **kwds) -> T_Injected:
        if isinstance(func, MethodType):
            args = (func.__self__,) + args
            func = func.__func__

        return self.make(func)(*args, **kwds)

    def __bool__(self):
        return True
        
    def __contains__(self, x) -> bool:
        return dict.__contains__(self, x) or x in self.parent

    def __missing__(self, dep: Dependency):
        try:
            if dep.scope is self.scope:
                return self.__setdefault(dep, dep.resolver(self))
        except AttributeError:
            dep = self.scope[dep]
            return dep and self[dep]
        else:
            return self.__setdefault(dep, self.parent[dep])
        
    __setdefault = dict.setdefault

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
        raise TypeError(f"immutable type: {self} ")

    __delitem__ = __setitem__ = setdefault = not_mutable
    pop = popitem = update = clear = not_mutable
    copy = __copy__ = __reduce__ = __deepcopy__ = not_mutable
    del not_mutable




class NullInjectorContext(Injector):
    """NullInjector Object"""

    __slots__ = ()

    name: t.Final = None
    injector = parent = None

    def noop(slef, *a, **kw):
        ...

    __init__ = __getitem__ = __missing__ = __contains__ = _reset = noop
    del noop

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}()'


    

_T = t.TypeVar("_T")
_T_Fn = t.TypeVar("_T_Fn", bound=Callable)


class _InjectorExitStack(list[tuple[bool, _T_Fn]]):
    """Async context manager for dynamic management of a stack of exit
    callbacks.

    For example:
        async with AsyncExitStack() as stack:
            connections = [await stack.enter_async_context(get_connection())
                for i in range(5)]
            # All opened connections will automatically be released at the
            # end of the async with statement, even if attempts to open a
            # connection later in the list raise an exception.
    """
    __slots__ = ()

    @staticmethod
    def _create_exit_wrapper(cm, cm_exit):
        return MethodType(cm_exit, cm)

    @staticmethod
    def _create_cb_wrapper(callback, /, *args, **kwds):
        def _exit_wrapper(exc_type, exc, tb):
            callback(*args, **kwds)
        return _exit_wrapper

    @staticmethod
    def _create_async_exit_wrapper(cm, cm_exit):
        return MethodType(cm_exit, cm)

    @staticmethod
    def _create_async_cb_wrapper(callback, /, *args, **kwds):
        async def _exit_wrapper(exc_type, exc, tb):
            await callback(*args, **kwds)

        return _exit_wrapper

    def _push_exit_callback(self, k, cb, is_sync=True):
        self.append((is_sync, cb))

    def push(self, exit: _T) -> _T:
        """Registers a callback with the standard __exit__ method signature.

        Can suppress exceptions the same way __exit__ method can.
        Also accepts any object with an __exit__ method (registering a call
        to the method instead of the object itself).
        """
        # We use an unbound method rather than a bound method to follow
        # the standard lookup behaviour for special methods.
        _cb_type = exit.__class__

        try:
            exit_method = _cb_type.__exit__
        except AttributeError:
            # Not a context manager, so assume it's a callable.
            self._push_exit_callback(exit, exit)
        else:
            self._push_exit_callback(exit, self._create_exit_wrapper(exit, exit_method))
        return exit  # Allow use as a decorator.

    def enter(self, cm):
        """Enters the supplied context manager.

        If successful, also pushes its __exit__ method as a callback and
        returns the result of the __enter__ method.
        """
        # We look up the special methods on the type to match the with
        # statement.
        _cm_type = cm.__class__
        _exit = _cm_type.__exit__
        result = _cm_type.__enter__(cm)
        self._push_exit_callback(cm, self._create_exit_wrapper(cm, _exit))
        return result

    def callback(self, callback: _T_Fn, /, *args, **kwds) -> _T_Fn:
        """Registers an arbitrary callback and arguments.

        Cannot suppress exceptions.
        """
        _exit_wrapper = self._create_cb_wrapper(callback, *args, **kwds)

        # We changed the signature, so using @wraps is not appropriate, but
        # setting __wrapped__ may still help with introspection.
        _exit_wrapper.__wrapped__ = callback
        self._push_exit_callback((callback, args, kwds), _exit_wrapper)
        return callback  # Allow use as a decorator

    def close(self):
        """Immediately unwind the context stack."""
        self.__exit__(None, None, None)

    def __enter__(self):
        return self

    def __exit__(self, *exc_details):
        received_exc = exc_details[0] is not None

        # We manipulate the exception state so it behaves as though
        # we were actually nesting multiple with statements

        # Callbacks are invoked in LIFO order to match the behaviour of
        # nested context managers
        suppressed_exc = pending_raise = False

        if self:
            frame_exc = sys.exc_info()[1]

            while self:
                is_sync, cb = self.pop()
                assert is_sync
                try:
                    if cb(*exc_details):
                        suppressed_exc = True
                        pending_raise = False
                        exc_details = (None, None, None)
                except:
                    new_exc_details = sys.exc_info()
                    # simulate the stack of exceptions by setting the context
                    _fix_exception_context(
                        new_exc_details[1], exc_details[1], frame_exc
                    )
                    pending_raise = True
                    exc_details = new_exc_details

            if pending_raise:
                try:
                    # bare "raise exc_details[1]" replaces our carefully
                    # set-up context
                    fixed_ctx = exc_details[1].__context__
                    raise exc_details[1]
                except BaseException:
                    exc_details[1].__context__ = fixed_ctx
                    raise
        return received_exc and suppressed_exc

    async def enter_async(self, cm):
        """Enters the supplied async context manager.

        If successful, also pushes its __aexit__ method as a callback and
        returns the result of the __aenter__ method.
        """
        _cm_type = cm.__class__
        _exit = _cm_type.__aexit__
        result = await _cm_type.__aenter__(cm)
        self._push_async_cm_exit(cm, _exit)
        return result

    def push_async_exit(self, exit):
        """Registers a coroutine function with the standard __aexit__ method
        signature.

        Can suppress exceptions the same way __aexit__ method can.
        Also accepts any object with an __aexit__ method (registering a call
        to the method instead of the object itself).
        """
        _cb_type = type(exit)
        try:
            exit_method = _cb_type.__aexit__
        except AttributeError:
            # Not an async context manager, so assume it's a coroutine function
            self._push_exit_callback(exit, exit, False)
        else:
            self._push_async_cm_exit(exit, exit_method)
        return exit  # Allow use as a decorator

    def callback_async(self, callback, /, *args, **kwds):
        """Registers an arbitrary coroutine function and arguments.

        Cannot suppress exceptions.
        """
        _exit_wrapper = self._create_async_cb_wrapper(callback, *args, **kwds)

        # We changed the signature, so using @wraps is not appropriate, but
        # setting __wrapped__ may still help with introspection.
        _exit_wrapper.__wrapped__ = callback
        self._push_exit_callback(callback, _exit_wrapper, False)
        return callback  # Allow use as a decorator

    async def aclose(self):
        """Immediately unwind the context stack."""
        await self.__aexit__(None, None, None)

    def _push_async_cm_exit(self, cm, cm_exit):
        """Helper to correctly register coroutine function to __aexit__
        method."""
        _exit_wrapper = self._create_async_exit_wrapper(cm, cm_exit)
        self._push_exit_callback(cm, _exit_wrapper, False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_details):
        # exc_details = = (None, None, None)
        received_exc = exc_details[0] is not None

        # We manipulate the exception state so it behaves as though
        # we were actually nesting multiple with statements

        # Callbacks are invoked in LIFO order to match the behaviour of
        # nested context managers
        suppressed_exc = pending_raise = False

        if self:
            frame_exc = sys.exc_info()[1]

            while self:
                is_sync, cb = self.pop()
                try:
                    if is_sync:
                        cb_suppress = cb(*exc_details)
                    else:
                        cb_suppress = await cb(*exc_details)

                    if cb_suppress:
                        suppressed_exc = True
                        pending_raise = False
                        exc_details = (None, None, None)
                except:
                    new_exc_details = sys.exc_info()
                    # simulate the stack of exceptions by setting the context
                    _fix_exception_context(
                        new_exc_details[1], exc_details[1], frame_exc
                    )
                    pending_raise = True
                    exc_details = new_exc_details

            if pending_raise:
                try:
                    # bare "raise exc_details[1]" replaces our carefully
                    # set-up context
                    fixed_ctx = exc_details[1].__context__
                    raise exc_details[1]
                except BaseException:
                    exc_details[1].__context__ = fixed_ctx
                    raise
        return received_exc and suppressed_exc




def _fix_exception_context(new_exc, old_exc, frame_exc):
    # Context may not be correct, so find the end of the chain
    while 1:
        exc_context = new_exc.__context__
        if exc_context is None or exc_context is old_exc:
            # Context is already set correctly (see issue 20317)
            return
        if exc_context is frame_exc:
            break
        new_exc = exc_context
    # Change the end of the chain to point to the exception
    # we expect it to reference
    new_exc.__context__ = old_exc
