from abc import abstractmethod
from contextlib import AbstractAsyncContextManager, AbstractContextManager
import logging
import sys
from types import MethodType
import typing as t
from collections.abc import Callable
from typing_extensions import Self

from laza.common.abc import abstractclass



logger = logging.getLogger(__name__)


_T = t.TypeVar('_T')
_T_Fn = t.TypeVar('_T_Fn', bound=Callable)

_object_new =object.__new__


class AwaitValue(t.Generic[_T]):
    __slots__ = '__value',

    def __new__(cls, value: _T):
        self = _object_new(cls)
        self.__value = value
        return self

    def __await__(self):
        yield 
        return self.__value


  

@abstractclass
class ContextLock(AbstractContextManager):
    __slots__ = ()


@abstractclass
class AsyncContextLock(AbstractAsyncContextManager):
    __slots__ = ()




@abstractclass
class AbstractExitStack:

    __slots__ = ()

    @staticmethod
    def _create_exit_wrapper(cm, cm_exit):
        return MethodType(cm_exit, cm)

    @staticmethod
    def _create_cb_wrapper(callback, /, *args, **kwds):
        def _exit_wrapper(exc_type, exc, tb):
            callback(*args, **kwds)
        return _exit_wrapper

    @abstractmethod
    def push(self, k, cb):
        raise NotImplementedError(f'{self.__class__.__name__}.push()')

    @abstractmethod
    def pop(self, *args, **kw):
        raise NotImplementedError(f'{self.__class__.__name__}.pop()')
    
    def exit(self, exit: _T) -> _T:
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
            self.push(exit, exit)
        else:
            self.push(exit, self._create_exit_wrapper(exit, exit_method))
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
        self.push(cm, self._create_exit_wrapper(cm, _exit))
        return result

    def callback(self, callback: _T_Fn, /, *args, **kwds) -> _T_Fn:
        """Registers an arbitrary callback and arguments.

        Cannot suppress exceptions.
        """
        _exit_wrapper = self._create_cb_wrapper(callback, *args, **kwds)

        # We changed the signature, so using @wraps is not appropriate, but
        # setting __wrapped__ may still help with introspection.
        _exit_wrapper.__wrapped__ = callback
        self.push((callback, args, kwds), _exit_wrapper)
        return callback  # Allow use as a decorator

    def flush(self, exc_details: tuple[t.Any, t.Any, t.Any]=(None, None, None)):
        received_exc = exc_details[0] is not None

        # We manipulate the exception state so it behaves as though
        # we were actually nesting multiple with statements

        # Callbacks are invoked in LIFO order to match the behaviour of
        # nested context managers
        suppressed_exc = pending_raise = False

        if self:
            frame_exc = sys.exc_info()[1]

            while self:
                cb = self.pop()
                try:
                    if cb(*exc_details):
                        suppressed_exc = True
                        pending_raise = False
                        exc_details = (None, None, None)
                except:
                    new_exc_details = sys.exc_info()
                    # simulate the stack of exceptions by setting the context
                    _fix_exception_context(new_exc_details[1], exc_details[1], frame_exc)
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

    def close(self, result: _T=None) -> _T:
        self.flush()
        return result

    def __enter__(self):
        return self

    def __exit__(self, *excinfo):
        return self.flush(excinfo)




class ExitStack(list[Callable], AbstractExitStack):

    __slots__ = ()

    def push(self, k, cb):
        self.append(cb)





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