# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False



from inspect import Parameter
import typing as t
import asyncio


from functools import partial

from asyncio import FIRST_EXCEPTION, AbstractEventLoop, CancelledError, Future, Task, ensure_future, gather as async_gather, get_running_loop

import cython



cdef tuple _no_items = ()


cdef class FutureCall:

    cdef object func
    cdef tuple args
    cdef tuple kwds
    cdef tuple aws
    cdef dict vals
    cdef int aw_args
    cdef int aw_kwds
    cdef bint aw_call





cdef inline object __call_aw_args(object func, tuple args, tuple aws, bint aw_call):
    cdef object loop
    cdef object future
    cdef object task

    loop = get_running_loop()
    future = loop.create_future()

    task = async_gather(*(aw() for aw in aws))




cdef inline object __future_call(FutureCall self):
    cdef object loop
    cdef object future

    if self.aws:
        task = async_gather(*(aw() for aw in self.aws))
        future = Future()
        if self.aw_call:
            task.add_done_callback(partial(__async_future_call_result_callback, self, future, task))
        else:
            task.add_done_callback(partial(__future_call_result_callback, self, future))
        return future
    else:
        return __call(self)
    return future
    




@cython.boundscheck(False)
@cython.wraparound(False)
cdef inline object __call(FutureCall self, list aw=None):
    cdef object args
    cdef object kwds
    cdef object it 

    if aw is None:
        args = self.iargs() if self.args else ()
        kwds = self.ikwds() if self.kwds else ()
    else:
        it = iter(aw)
        args = self.iargs(it) if self.aw_args > 0 else self.iargs() if self.args else () 
        kwds = self.ikwds(it) if self.aw_kwds > 0 else self.ikwds() if self.kwds else ()
    
    if _no_items is args is kwds:
        return self.func(**self.vals)
    elif _no_items is args:
        return self.func(**self.vals, **{ k:v for k, v in kwds})
    elif _no_items is kwds:
        return self.func(*args, **self.vals)
    else:
        return self.func(*args, **self.vals, **{ k:v for k, v in kwds}) 
    



@cython.boundscheck(False)
@cython.wraparound(False)
cdef inline object  __future_result_callback(object future, object src):
    cdef object result
    try:
        result = src.result()
    except Exception as e:
        future.set_exception(e)
    else:
        future.set_result(result)


@cython.boundscheck(False)
@cython.wraparound(False)
cdef inline object __future_call_result_callback(FutureCall self, object future, object src):
    cdef object result
    
    try:
        result = __call(self, src.result())
    except Exception as e:
        future.set_exception(e)
    else:
        future.set_result(result)
    


@cython.boundscheck(False)
@cython.wraparound(False)
cdef inline object __async_future_call_result_callback(FutureCall self, object future, object src):
    cdef object task

    try:
        task = ensure_future(__call(self, src.result())).add_done_callback(partial(__future_result_callback, future))
    except Exception as e:
        future.set_exception(e)
   
   

