from abc import ABC, ABCMeta, abstractmethod
from collections import defaultdict
from functools import reduce
from itertools import repeat, zip_longest
from logging import getLogger
from os import stat
from threading import Lock
from types import FunctionType, LambdaType, MethodType
import typing as t

from collections.abc import Callable
from typing_extensions import Self

from xdi._common.enum import BitSetFlag, auto
from xdi._common.functools import class_only_property, cache, class_only_method


from xdi._common.collections import frozendict

from xdi._common.collections import fallbackdict


logger = getLogger(__name__)

_T_Val = t.TypeVar('_T_Val')
_T_Default = t.TypeVar('_T_Default')
_T_Ret = t.TypeVar('_T_Ret')
_T_Reason = t.TypeVar('_T_Reason')
_T_Error = t.TypeVar('_T_Error', bound=Exception)

_T_Pipe = t.Union[Callable[[_T_Val], t.Union[_T_Ret, 'Promise[_T_Ret, _T_Reason]']], 'Promise[_T_Ret, _T_Reason]', _T_Ret]
_T_StackKey = tuple[t.Union[Callable[[t.Union[_T_Val, _T_Reason]], _T_Ret], None], t.Union['Promise', None]]

_NoneType = type(None)

_empty = object()

_TRUE_CALLABLES = frozenset([FunctionType, MethodType, LambdaType])
_T_TrueCallable = t.Union[FunctionType, MethodType, LambdaType]


_FuncTypes = FunctionType, MethodType
_FuncTypeSet = frozenset([FunctionType, MethodType, LambdaType])
_T_FuncTypes = t.Union[FunctionType, MethodType]
# _T_ResolveFunc = Callable[[Callable[[_T_Val], t.NoReturn], Callable[[_T_Reason], t.NoReturn], Callable[[_T_Error], t.NoReturn]], t.NoReturn]
_T_ResolveFunc = Callable[['Promise'], t.NoReturn]

_T_Bind = t.Union[_T_FuncTypes, 'Promise']



class State(BitSetFlag):


    pending: 'State'     = auto()
    """The initial state, neither fulfilled nor rejected.
    """
    
    cancelled: 'State'    = auto()
    """The operation has been cancelled.
    """

    failed: 'State'         = auto()
    """The operation failed.
    """

    fulfilled: 'State'   = auto()
    """The operation was completed successfully.
    """

    rejected: 'State'
    """The operation was either `cancelled` or `failed`.
    """

    settled: 'State'
    """The operation was either `fulfilled`, `cancelled` or `failed`.
    """
    
    @class_only_property
    @cache
    def rejected(cls):
        """The operation was either `cancelled` or `failed`.
        """
        return cls.cancelled | cls.failed

    @class_only_property
    @cache
    def settled(cls):
        """The operation was either `fulfilled`, `cancelled` or `failed`.
        """
        return cls.fulfilled | cls.rejected
    


NO_STATE = State(0)
PENDING = State.pending
CANCELLED = State.cancelled
FAILED = State.failed
FULFILLED = State.fulfilled
REJECTED = State.rejected
SETTLED = State.settled






class InvalidStateError(ValueError):
    """Invalid internal state of `Promise`"""


class SettledError(Exception, t.Generic[_T_Reason]):
    msg = '{error_name}: reason={reason}'
    error_name = 'error'
    reason: _T_Reason  
    context: dict = frozendict()
    source: 'SettledError'
  
    def __init__(self, reason: _T_Reason=None, source: 'SettledError'=None) -> None:
        if source is None and isinstance(reason, SettledError):
            source = reason
            reason = source.reason

        self.source = source
        self.reason = reason
    
    def __str__(self) -> str:
        return self.msg.format(status=self.error_name, reason=self.reason, **self.context)



class CancelledError(SettledError[_T_Reason]):
    error_name = 'cancelled'
  
  

    
class FailedError(SettledError[t.Union[Exception, str]]):
    """Failed `Promise` error,"""
    error_name = 'failed'

    def __init__(self, reason: _T_Reason=None, source: 'SettledError'=None) -> None:
        if source is None:
            if isinstance(reason, SettledError):
                self.reason = reason.reason
                self.source = reason
            elif isinstance(reason, Exception):
                self.reason = reason
                self.source = reason
            else:
                self.reason = reason
                self.source = ValueError(reason)
        else:
            self.reason = reason
            self.source = source
    

        

@t.overload
def _project(obj: _T_FuncTypes) -> _T_FuncTypes: ...
@t.overload
def _project(obj: _T_Val) -> Callable[..., _T_Val]: ...
@t.overload
def _project(obj: _T_Val, *, empty: _T_Val, default: _T_Default) -> Callable[..., _T_Default]: ...
def _project(obj: t.Union[_T_FuncTypes, _T_Val], *, empty: _T_Default=_empty, default: _T_Default=_empty):
    if obj is empty:
        return _default_identities[default]
    elif obj.__class__ in _FuncTypeSet:
        return obj
    else:
        lambda *a: obj


_noop_none = lambda *a: None
_noop_arg = lambda v=None: v

_default_identities = fallbackdict(lambda k: (lambda v=k: v))  
_default_identities.update({
    _empty: _noop_arg,
    None: _noop_none
})

# _default_states = fallbackdict(lambda k: k[1])
# _default_states[_empty, FULFILLED] = FULFILLED
# _default_states[_empty, CANCELLED] \
#     = _default_states[_empty, FAILED] \
#     = _default_states[_empty, REJECTED] \
#         = NO_STATE


class _CallStack(dict[State, dict[_T_StackKey, tuple]]):
    
    __slots__ = ()

    def __missing__(self, key):
        return self.setdefault(key, {})




class BasePromise(t.Generic[_T_Val, _T_Reason, _T_Error], metaclass=ABCMeta):

    __slots__ = ()

    @property
    @abstractmethod
    def state(self) -> State: ...

    @abstractmethod
    def done(self) -> bool: ...

    @abstractmethod
    def result(self) -> _T_Val: ...
    
    def catch(self, 
            reject: _T_Pipe=_empty, 
            *, 
            cancel: _T_Pipe=_empty, 
            fail: _T_Pipe=_empty) -> Self: ...
            
    @abstractmethod
    def finaly(self, callback: _T_FuncTypes) -> Self: 
        ...

    @abstractmethod
    def pipe(self, 
            fulfil: _T_Pipe=_empty, 
            reject: _T_Pipe=_empty, 
            *, 
            cancel: _T_Pipe=_empty, 
            fail: _T_Pipe=_empty) -> Self:
        ...

    @t.overload
    def then(self, settle: Self) -> Self: ...
    @t.overload
    def then(self, 
            fulfil: _T_FuncTypes=_empty, 
            reject: _T_FuncTypes=_empty, 
            *, 
            cancel: _T_FuncTypes=_empty, 
            fail: _T_FuncTypes=_empty) -> Self: ...
    @abstractmethod
    def then(self, 
            fulfil: t.Union[_T_FuncTypes, Self] =_empty, 
            reject: _T_FuncTypes=_empty, 
            *, 
            cancel: _T_FuncTypes=_empty, 
            fail: _T_FuncTypes=_empty) -> Self:
        ...

    def __clsss_getitem__(cls, params):
        if not isinstance(params, tuple):
            params = params,
        return super().__class_getitem__(cls, params + cls.__parameters__[len(params):])

    def __repr__(self) -> str:
        try:
            result = self.result()
        except InvalidStateError as e:
            return f'{self.__class__.__name__}({self.state!r})'
        except CancelledError as e:
            return f'{self.__class__.__name__}({self.state!r}, reason={e.reason!r})'    
        except FailedError as e:
            return f'{self.__class__.__name__}({self.state!r}, error={e.reason!r})'   
        else:
            return f'{self.__class__.__name__}({self.state!r}, {result=!r})'   





class Promise(BasePromise[_T_Val, _T_Reason, _T_Error]):

    __slots__ = (
        '__state', '__result', '__stack', # '__lock', 
        
    )

    if t.TYPE_CHECKING:
        class State(State): ...

    __state: State
    __result: t.Union[_T_Val, CancelledError[_T_Reason], Exception]


    __stack: _CallStack

    State: t.Final = State

    def __new__(cls: type[Self], source: Self=None) -> Self:
        return cls.__make(source=source)
        
    @classmethod
    def __make(cls, state: State=PENDING, result: t.Union[_T_Val, _T_Reason]=None, *, source: 'Promise'=None):
        self = object.__new__(cls)
        if source is None:
            if state is PENDING:
                self.__state = PENDING
                # self.__lock = Lock()
                self.__stack = _CallStack()
            elif state in SETTLED:
                self.__state = state
                self.__result = result
            else:
                raise InvalidStateError(f'invalid push state: {state!r} allowed: {SETTLED!r}')
        elif not source.__state is PENDING:
            self.__state = source.__state
            self.__result = source.__result
        else:
            self.__state = PENDING
            # self.__lock = _NoopLock()
            self.__stack = _CallStack()
            source.then(self)

        return self

    @classmethod
    def cast(cls: type[Self], value: t.Union[_T_Val, 'Promise']) -> Self:
        if isinstance(value, cls):
            return value
        else:
            return cls.__make(FULFILLED, value)
   
    @class_only_method
    def cancelled(cls, reason: _T_Reason=None):
        return cls.__make(CANCELLED, reason)

    @class_only_method
    def failed(cls, error: _T_Error=None):
       return cls.__make(FAILED, error)

    @class_only_method
    def fulfilled(cls, result: _T_Val=None):
        return cls.__make(FULFILLED, result)

    @property
    def state(self) -> State:
        return self.__state

    def done(self) -> bool:
        return not self.state is PENDING

    def result(self) -> _T_Val:
        state = self.__state
        if state is PENDING:
            raise InvalidStateError(f'Promise is not settled')
        elif state is FULFILLED:
            return self.__result
        else:
            if state is CANCELLED:
                ex = CancelledError(self.__result)
            else:
                ex = FailedError(self.__result)
            raise ex from ex.source

    def catch(self, reject: _T_Pipe=_empty, *, cancel: _T_Pipe=_empty, fail: _T_Pipe=_empty):
        if _empty is reject is cancel is fail:
            reject = None
        return self.pipe(reject=reject, cancel=cancel, fail=fail)
            
    def pipe(self, fulfil: _T_Pipe=_empty, reject: _T_Pipe=_empty, *, cancel: _T_Pipe=_empty, fail: _T_Pipe=_empty):
    
        stack = [(fulfil, FULFILLED),]

        if reject is _empty:
            cancel is _empty or stack.append((cancel, CANCELLED))  
            fail is _empty or stack.append((fail, FAILED))  
        elif cancel is _empty is fail:
            stack.append((reject, REJECTED))
        else:
            raise ValueError(
                f'argument `reject` is mutually exclusive to `cancel` and `fail`'
            )

        return self.__push(*stack)        

    @t.overload
    def then(self, fulfil: _T_FuncTypes=_empty, reject: _T_FuncTypes=_empty, *, cancel: _T_FuncTypes=_empty, fail: _T_FuncTypes=_empty) -> Self: ...
    @t.overload
    def then(self, bind: 'Promise') -> Self: ...
    def then(self, fulfil: t.Union[_T_FuncTypes, 'Promise'] =_empty, reject: _T_FuncTypes=_empty, *, cancel: _T_FuncTypes=_empty, fail: _T_FuncTypes=_empty):
        if _empty is reject is cancel is fail:
            
            fulcls = fulfil.__class__

            if fulcls is Promise:
                self.__push_callbacks((fulfil, SETTLED))
            elif fulcls in _FuncTypeSet:
                self.__push_callbacks((fulfil, FULFILLED))
            elif fulfil is _empty:
                raise TypeError(
                    f'`{self.__class__.__name__}.then()` '
                    f'requires atleast one `handler`.'
                )
            else:
                raise ValueError(
                    f'fulfil` must be '
                    f'{"`, `".join(f"{c.__name__}" for c in _FuncTypeSet) } '
                    f'or `Promise`. Got: `{fulfil.__class__.__name__}`'
                )
        elif reject is _empty:
            fulfil is _empty or self.__push_callbacks((fulfil, FULFILLED))
            cancel is _empty or self.__push_callbacks((cancel, CANCELLED))
            fail   is _empty or self.__push_callbacks((fail, FAILED))
        elif cancel is _empty is fail:
            fulfil is _empty or self.__push_callbacks((fulfil, FULFILLED))
            reject is _empty or self.__push_callbacks((reject, REJECTED))
        else:
            raise ValueError(
                f'argument `reject` is mutually exclusive to `cancel` and `fail`'
            )
        
        return self

    def finaly(self, callback: _T_FuncTypes):
        self.__push_callbacks((callback, SETTLED, ()))
        return self

    def __push(self, *funcs: t.Union[tuple[_T_Bind, State], _T_Bind], state: State=NO_STATE, args=True):
        fill = _noop_arg, state, args
        state = self.__state

        items = (a + fill[len(a):] if isinstance(a, tuple) else (a, *fill[1:]) for a in funcs)
        
        target = self.__make()

        if state is PENDING:
            settled = NO_STATE

            stack = self.__stack
            for cb, ss, v in items:
                fn = _project(cb)
                settled = settled | ss
                for s in ss:
                    stack[s][target, cb] = fn, v, target

            # _val = lambda: target.__state is PENDING and target.__settle(self), (self,), None
            _val = None, (), target
            for s in ~settled:
                stack[s].setdefault(target, _val)

            self.__flush()
        else:
            settled = False
            res = () if self.__result is None else (self.__result,)
            for cb, ss, a in items:
                if state in ss:
                    self.__run(_project(cb), res if a is True else a, target)
                    settled = True

            settled or target.__settle(self)

        return target

    def __push_callbacks(self, *funcs: t.Union[tuple[_T_FuncTypes, State, t.Union[bool, tuple]], _T_FuncTypes], state: State=None, args=True):
        fill = state, args
        state = self.__state

        items = (o + fill[len(o)-1:] if isinstance(o, tuple) else (o, *fill) for o in funcs)
        
        if state is PENDING:
            stack = self.__stack
            for cb, ss, a in items:
                if isinstance(k := cb, Promise): 
                    # v = lambda: k.__state is PENDING and k.settle(self), (), None
                    v = None, (), k
                else:
                    v = k, a, None
                v = k, a, None
                for s in ss:
                    stack[s].setdefault(k, v)

            self.__flush()
        else:
            res = () if self.__result is None else (self.__result,)
            for cb, ss, a in items:
                if state in ss:
                    out = None
                    if isinstance(k := cb, Promise): # and a is args: 
                        out, cb = cb, None
                        # args =  lambda: k.__state is PENDING and k.settle(self), (),
                    self.__run(cb, res if a is True else a, out)

    def _unbind(self, callback: _T_FuncTypes, state: State=SETTLED):
        n = 0
        for k in state:
            n += not self.__stack[k].pop(callback, ...) is ...
        return n

    def fulfil(self, result: _T_Val=None) -> Self:
        if not self.__settle(result, FULFILLED):
            raise InvalidStateError(f'Promise already settled: {self}')
        return self
    
    def cancel(self, reason: _T_Reason=None) -> Self:
        if not self.__settle(reason, CANCELLED):
            raise InvalidStateError(f'Promise already settled: {self}')
        return self
    
    def fail(self, error: _T_Error=None) -> Self:
        if not self.__settle(error, FAILED):
            raise InvalidStateError(f'Promise already settled: {self}')
        return self

    @t.overload
    def settle(self, result: Self) -> Self: ...
    @t.overload
    def settle(self, result: _T_Val, state: FULFILLED) -> Self: ...
    @t.overload
    def settle(self, result: _T_Reason, state: CANCELLED) -> Self: ...
    @t.overload
    def settle(self, result: _T_Error, state: FAILED) -> Self: ...
    def settle(self, result: t.Union[Self, _T_Val, _T_Reason, _T_Error, None]=None, state: State=None) -> Self:
        self.__settle(result, state or FULFILLED)
        return self

    @t.overload
    def __settle(self, result: Self) -> bool: ...
    @t.overload
    def __settle(self, result: _T_Val, state: FULFILLED) -> bool: ...
    @t.overload
    def __settle(self, result: _T_Reason, state: CANCELLED) -> bool: ...
    @t.overload
    def __settle(self, result: _T_Error, state: FAILED) -> bool: ...
    def __settle(self, result: t.Union[Self, _T_Val, _T_Reason, _T_Error, None]=None, state: State=None) -> bool:
        if self.__state is PENDING:
            # with self.__lock:
            if state is None and result.__class__ is Promise:
                if result.__state is PENDING: 
                    result.then(self)
                else:
                    self.__result = result.__result
                    self.__state =  result.__state 
            elif state in SETTLED:
                self.__state = state
                self.__result = result
            else:
                raise InvalidStateError(f'invalid push state: {state!r} allowed: {SETTLED!r}')
            self.__flush()
            return True
        return False

    def __flush(self):
        state = self.__state
        if not state is PENDING:
            stack = self.__stack
            args = () if self.__result is None else (self.__result,)
            while stack:
                s, dct = stack.popitem()
                if s is state:
                    for cb, v, out in dct.values():
                        self.__run(cb, args if v is True else v, out)
    
    def __run(self, cb: t.Union[_T_FuncTypes, None], args: t.Union[bool, tuple]=True, dest:Self=None):
        if cb is None:
            dest.__settle(self)
        else:
            try:
                r = cb(*args)
            except Exception as e:
                if dest is None:
                    raise e
                elif isinstance(e, CancelledError):
                    dest.cancel(e)
                else:
                    dest.fail(e)
            else:
                dest is None \
                    or (r.then(dest) if isinstance(r, Promise) else dest.fulfil(r))

    def __eq__(self, o) -> bool:
        return o is self

    def __hash__(self) -> int:
        return id(self)




