import logging
import sys
import typing as t
from collections.abc import Callable
from types import MethodType

from typing_extensions import Self


from . import providers
from .markers import Injectable, T_Injectable, T_Injected
from .exceptions import InjectorLookupError
from ._common import ReadonlyDict, private_setattr
from .graph.nodes import Node


if t.TYPE_CHECKING:  # pragma: no cover
    from .graph.core import Graph, NullGraph
    from .scopes import Scope


logger = logging.getLogger(__name__)

_T = t.TypeVar("_T")
_object_new = object.__new__


TContextNode = Callable[["Injector", t.Optional[Injectable]], Callable[..., T_Injected]]


@private_setattr
class Injector(ReadonlyDict[T_Injectable, Callable[[], T_Injected]]):
    """An isolated dependency injection context for a given `Scope`.

    Attributes:
        graph (DepGraph): the dependency graph for this injector
        parent (Injector): a parent injector to provide missing dependencies.

    Params:
        graph (DepGraph): the dependency graph for this injector
        parent (Injector): a parent injector to provide missing dependencies.

    """

    __slots__ = (
        "graph",
        "parent",
        "__weakref__",
    )

    graph: "Graph"
    parent: Self

    def __init__(self, graph: "Graph", parent: Self):
        self.__setattr(graph=graph, parent=parent)

    @property
    def name(self) -> str:
        """The name of the scope. Usually returns the injector's `scope.name`"""
        return self.graph.name

    def bound(self, abstract: T_Injectable) -> T_Injected:
        return self[self.graph[abstract]]

    def make(self, abstract: T_Injectable, /, *args, **kwds) -> T_Injected:
        graph = self.graph
        if dep := graph[abstract]:
            return self[dep](*args, **kwds)
        elif callable(abstract):
            if prov := getattr(abstract, "__uzi_provider__", None):
                if dep := graph[prov]:
                    return self[dep](*args, **kwds)
            else:
                prov = providers.Partial(abstract)
                setattr(abstract, "__uzi_provider__", prov)
                return self[graph[prov]](*args, **kwds)
        else:
            return self[abstract](*args, **kwds)

    def __bool__(self):
        return not not self.graph

    def __contains__(self, x) -> bool:
        return self.__contains(x) or x in self.parent

    def __missing__(self, dep: Node):
        try:
            return self.__setdefault(
                dep, (dep.graph is self.graph and dep.bind(self)) or self.parent[dep]
            )
        except AttributeError as e:
            raise TypeError(
                f"Injector key must be a `Dependency` not `{dep.__class__.__qualname__}`"
            )

    __setdefault = dict.setdefault
    __contains = dict.__contains__

    def close(self):
        ...  # pragma: no cover

    def copy(self):
        return self

    __copy__ = copy

    def __reduce__(self):
        raise TypeError(f"cannot copy `{self.__class__.__name__}`")

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def __repr__(self) -> str:
        return f"<{self!s}, {self.parent!r}>"

    def __hash__(self):
        return id(self)

    def __eq__(self, x):
        return x is self if isinstance(x, Injector) else NotImplemented

    def __ne__(self, x):
        return not x is self if isinstance(x, Injector) else NotImplemented


class NullInjector(Injector):
    """A 'noop' `Injector` used as the parent of root injectors.

    Attributes:
        scope (NullScope): the scope
        parent (None): The parent injector

    Params:
        None
    """

    __slots__ = ()

    parent: t.Final = None
    _scope: "NullGraph" = None

    @property
    def scope(self):
        if not (scp := self._scope) is None:
            return scp
        else:
            from uzi.scopes import _null_scope

            scp = self.__class__._scope = _null_scope
            return scp

    @property
    def graph(self):
        return self.scope.graph

    def __init__(self, *a, **kw) -> None:
        ...  # pragma: no cover

    def __reduce__(self):
        return self.__class__, ()

    def __getitem__(self, dep: Node):
        try:
            dep.bind(self)
        except (AttributeError, TypeError) as e:
            raise InjectorLookupError(dep) from e
        else:
            raise InjectorLookupError(dep)

    def __bool__(self, *a, **kw):
        return False

    __contains__ = __bool__

    def __eq__(self, o) -> bool:
        return o.__class__ is self.__class__

    def __ne__(self, o) -> bool:
        return not o.__class__ is self.__class__

    __hash__ = classmethod(hash)


_null_injector = NullInjector()


_T = t.TypeVar("_T")
_T_Fn = t.TypeVar("_T_Fn", bound=Callable)


class _InjectorExitStack(list[tuple[bool, _T_Fn]]):  # pragma: no cover
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


def _fix_exception_context(new_exc, old_exc, frame_exc):  # pragma: no cover
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
