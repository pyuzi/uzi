from asyncio import ensure_future
from contextlib import AbstractAsyncContextManager, AbstractContextManager
import typing as t
from collections.abc import Callable
from inspect import Parameter, iscoroutinefunction
from logging import getLogger

from laza.common.abc import abstractclass, immutableclass
from laza.common.functools import Missing
from laza.common.typing import Self


if t.TYPE_CHECKING:
    from ..injectors import InjectorContext


logger = getLogger(__name__)



_T = t.TypeVar("_T")

_object_new = object.__new__
_object_setattr = object.__setattr__



@abstractclass
@immutableclass
class ProviderVar(t.Generic[_T]):
    __slots__ = ()

    is_async: bool
    value: t.Union[_T, t.Literal[Missing]] # type: ignore
    is_variable: bool = True

    def get(self) -> _T: 
        return self.value

    def __await__(self):
        if True is self.is_async:
            value = yield from ensure_future(self.get())
            return value
        else:
            return self.get()
    
    # def __call__(self):
    #     return self.get()
        

class ValueProviderVar(ProviderVar[_T]):
    __slots__ = 'value', 'is_async',

    value: _T
    is_variable: bool = False

    def __new__(cls, value: _T, ctx: 'InjectorContext'=None, *, is_async: bool=False):
        self = _object_new(cls)
        _object_setattr(self, 'value', value)
        _object_setattr(self, 'is_async', is_async)
        return self

    def __await__(self):
        if True is self.is_async:
            value = yield from ensure_future(self.value)
            return value
        else:
            return self.value



class FactoryProviderVar(ProviderVar[_T]):
    if t.TYPE_CHECKING:
        def get(self) -> _T: ...
        
    __slots__ = 'get', 'is_async'
    
    value = Missing

    def __new__(cls, func: Callable[[], _T], ctx: 'InjectorContext'=None, *, is_async: bool=False):
        self = _object_new(cls)
        
        _object_setattr(self, 'get', func)
        _object_setattr(self, 'is_async', is_async)
        return self
    



class SingletonProviderVar(ProviderVar[_T]):
    __slots__ = 'value', 'func', 'lock'

    func: Callable[[], _T]
    lock: AbstractContextManager
    is_async: t.ClassVar[bool] = False
    is_variable: bool = False

    _locked_type: t.ClassVar[type[Self]] = None
    _async_type: t.ClassVar[type[Self]] = None
    _async_locked_type: t.ClassVar[type[Self]] = None

    def __init_subclass__(cls, *, locked_type: bool=None, async_type: bool=None, async_locked_type: bool=None) -> None:
        if locked_type:
            SingletonProviderVar._locked_type = cls
        elif async_type:
            SingletonProviderVar._async_type = cls
        elif async_locked_type:
            SingletonProviderVar._async_locked_type = cls

    def __new__(cls, func: Callable[[], _T], ctx: 'InjectorContext'=None, *, is_async: bool=False):
        if True is cls.is_async:
            self = _object_new(cls)
            lock = ctx and ctx.alock()
            None is lock or _object_setattr(self, 'lock', lock)
        elif True is is_async:
            lock = ctx and ctx.alock()
            if None is lock:
                self = _object_new(cls._async_type)
            else:
                self = _object_new(cls._async_locked_type)
                _object_setattr(self, 'lock', lock)
        else:
            lock = ctx and ctx.lock()
            if None is lock:
                self = _object_new(cls)
            else:
                self = _object_new(cls._locked_type)
                _object_setattr(self, 'lock', lock)
            
        _object_setattr(self, 'func', func)
        _object_setattr(self, 'value', Missing)
        return self

    def __await__(self):
        if Missing is self.value:
            if True is self.is_async:
                value = yield from ensure_future(self.get())
                return value
            else:
                return self.get()
        return self.value

    def get(self) -> _T: 
        if self.value is Missing:
            self.value = self.func()            
        return self.value


        

class LockedSingletonProviderVar(SingletonProviderVar[_T], locked_type=True):

    __slots__ = ()

    def get(self) -> _T: 
        if self.value is Missing:
            with self.lock:
                if self.value is Missing:
                    self.value = self.func()  
        return self.value




class AsyncSingletonProviderVar(SingletonProviderVar[_T], async_type=True):
    __slots__ = ()

    lock: AbstractAsyncContextManager
    is_async = True

    async def get(self) -> _T: 
        if self.value is Missing:
            self.value = await self.func()            
        return self.value



class AsyncLockedSingletonProviderVar(AsyncSingletonProviderVar[_T], async_locked_type=True):
    __slots__ = ()

    async def get(self) -> _T: 
        if self.value is Missing:
            async with self.lock:
                 if self.value is Missing:
                    self.value = await self.func()     
        return self.value





class ResourceProviderVar(ProviderVar[_T]):
    __slots__ = 'value', 'func', 'lock', 'ctx', 

    ctx: 'InjectorContext'
    func: Callable[[], _T]
    lock: AbstractContextManager
    is_awaitable: t.ClassVar[bool] = False
    is_async: t.ClassVar[bool] = False
    is_variable: bool = False

    _locked_type: t.ClassVar[type[Self]] = None
    _async_type: t.ClassVar[type[Self]] = None
    _async_locked_type: t.ClassVar[type[Self]] = None

    def __init_subclass__(cls, *, locked_type: bool=None, async_type: bool=None, async_locked_type: bool=None) -> None:
        if locked_type:
            ResourceProviderVar._locked_type = cls
        elif async_type:
            ResourceProviderVar._async_type = cls
        elif async_locked_type:
            ResourceProviderVar._async_locked_type = cls

    def __new__(cls, func: Callable[[], _T], ctx: 'InjectorContext'=None, *, is_async: bool=None, is_awaitable: bool=None):
        if True is (cls.is_async or is_async):
            lock = ctx and ctx.alock()
            if None is lock:
                self = _object_new(cls._async_type)
            else:
                self = _object_new(cls._async_locked_type)
                _object_setattr(self, 'lock', lock)
            _object_setattr(self, 'is_awaitable', iscoroutinefunction(func) if None is is_awaitable else is_awaitable)
        else:
            lock = ctx and ctx.lock()
            if None is lock:
                self = _object_new(cls)
            else:
                self = _object_new(cls._locked_type)
                _object_setattr(self, 'lock', lock)
            
        _object_setattr(self, 'ctx', ctx)
        _object_setattr(self, 'func', func)
        _object_setattr(self, 'value', Missing)
        return self

    def __await__(self):
        if Missing is self.value:
            if True is self.is_async:
                value = yield from ensure_future(self.get())
                return value
            else:
                return self.get()
        return self.value

    def get(self) -> _T: 
        if self.value is Missing:
            self.value = self.ctx.enter(self.func())            
        return self.value


        
class LockedResourceProviderVar(ResourceProviderVar[_T], locked_type=True):

    __slots__ = ()

    def get(self) -> _T: 
        if self.value is Missing:
            with self.lock:
                if self.value is Missing:
                    self.value = self.ctx.enter(self.func())     
        return self.value



class AsyncResourceProviderVar(ResourceProviderVar[_T], async_type=True):
    __slots__ = 'is_awaitable',

    lock: AbstractAsyncContextManager
    is_async = True

    async def get(self) -> _T: 
        if self.value is Missing:
            if True is self.is_awaitable:
                self.value = await self.ctx.enter(await self.func()) 
            else:
                self.value = await self.ctx.enter(self.func()) 

        return self.value



class AsyncLockedResourceProviderVar(AsyncResourceProviderVar[_T], async_locked_type=True):
    __slots__ = ()

    async def get(self) -> _T: 
        if self.value is Missing:
            async with self.lock:
                if self.value is Missing:
                    if True is self.is_awaitable:
                        self.value = await self.ctx.enter(await self.func()) 
                    else:
                        self.value = await self.ctx.enter(self.func()) 
        return self.value





class AwaitableResourceProviderVar(ResourceProviderVar[_T]):
    __slots__ = 'value', 'func', 'lock', 'ctx', 

    ctx: 'InjectorContext'
    func: Callable[[], _T]
    lock: AbstractContextManager
    is_awaitable: t.ClassVar[bool] = True
    is_async: t.ClassVar[bool] = True
    is_variable: bool = False

    _locked_type: t.ClassVar[type[Self]] = None
    _async_type: t.ClassVar[type[Self]] = None
    _async_locked_type: t.ClassVar[type[Self]] = None

    def __init_subclass__(cls, *, locked_type: bool=None) -> None:
        if locked_type:
            AwaitableResourceProviderVar._locked_type = cls

    # def __new__(cls, func: Callable[[], _T], ctx: 'InjectorContext'=None, *, is_async: bool=None):
    #     if True is (cls.is_async or is_async):
    #         lock = ctx and ctx.alock()
    #         if None is lock:
    #             self = _object_new(cls._async_type)
    #         else:
    #             self = _object_new(cls._async_locked_type)
    #             _object_setattr(self, 'lock', lock)
    #         _object_setattr(self, 'is_awaitable', iscoroutinefunction(func) if None is is_awaitable else is_awaitable)
    #     else:
    #         lock = ctx and ctx.lock()
    #         if None is lock:
    #             self = _object_new(cls)
    #         else:
    #             self = _object_new(cls._locked_type)
    #             _object_setattr(self, 'lock', lock)
            
    #     _object_setattr(self, 'ctx', ctx)
    #     _object_setattr(self, 'func', func)
    #     _object_setattr(self, 'value', Missing)
    #     return self

    def __await__(self):
        if Missing is self.value:
            if True is self.is_async:
                value = yield from ensure_future(self.get())
                return value
            else:
                return self.get()
        return self.value

    def get(self) -> _T: 
        if self.value is Missing:
            self.value = self.ctx.enter(self.func())            
        return self.value

