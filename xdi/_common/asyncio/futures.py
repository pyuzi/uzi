

import typing as t
import logging

from asyncio import ensure_future, futures, AbstractEventLoop, InvalidStateError, gather
from asyncio.futures import _PENDING, Future, isfuture
from collections.abc import Callable
from typing_extensions import Self



STACK_DEBUG = logging.DEBUG - 1  # heavy-duty debugging



_T = t.TypeVar('_T')
_T_Src = t.TypeVar('_T_Src')



class Future(futures.Future[_T]):

    """This class is the *same* as `asyncio.futures.Future`.

    The only difference is that it is callable and can be used as a callaback to
    `asyncio.futures.Future.add_done_callback()`.
    """

    # _setup_func: Callable[..., _T] = None
    # _setup_args: tuple = ()
    
    # def __init__(self, __setup_func: Callable[[_T_Src], _T]=None, __setup_args=(), /, *, loop: t.Union[AbstractEventLoop, None] = None) -> None:
    #     super().__init__(loop=loop)
        # if __setup_func:
        #     self._setup_func = __setup_func
        #     self._setup_args = __setup_args

    # def set_result(self, result: _T_Src):
    #     if self._state != _PENDING:
    #         raise InvalidStateError(f'{self._state}: {self!r}')
    #     elif not self._setup_func is None:
    #         try:
    #             val = self._setup_func(*self._setup_args, result)
    #         except Exception as e:
    #             self.set_exception(e)
    #         else:
    #             super().set_result(val)
    #     else:
    #         super().set_result(result)

    def __call__(self, future_result: futures.Future[_T]):
        """Can be used as a callback to `Future.add_done_callback`
        """
        try:
            self.set_result(future_result.result())
        except InvalidStateError:
            raise
        except Exception as e:
            self.set_exception(e)
        # return self

    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            yield self  # This tells Task to wait for completion.
            if not self.done():
                raise RuntimeError("await wasn't used with future")
        return self.result()  # May raise too.

    def __iter__(self):
        return self.__await__()

    # def _new_future_(self):
    #     return 

    # def pipe(self, future: t.Union['Future', Callable]):
    #     if not isfuture(future):
            
    #     Future(loop=self._loop)

    # def then(self, future: 'Future'):
    #     if not isfuture(future):
    #         future = future(se)
    #     Future(loop=self._loop)





class FutureCall(Future[_T]):

    """This class is the *same* as `asyncio.futures.Future`.

    The only difference is that it is callable and can be used as a callaback to
    `asyncio.futures.Future.add_done_callback()`.
    """
    
    _func: Callable[..., _T]
    _args: tuple
    
    def __init__(self, func: Callable[[_T_Src], _T], *args, loop: t.Union[AbstractEventLoop, None] = None) -> None:
        super().__init__(loop=loop)
        self._func = func
        self._args = args

    def set_result(self, result: _T_Src):
        if self._state != _PENDING:
            raise InvalidStateError(f'{self._state}: {self!r}')
        try:
            val = self._func(*self._args, result)
        except Exception as e:
            self.set_exception(e)
        else:
            super().set_result(val)

