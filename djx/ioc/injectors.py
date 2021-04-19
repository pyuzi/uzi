
from collections.abc import Mapping, MutableMapping
from collections import defaultdict
from types import FunctionType
from contextvars import ContextVar
from typing import Any, Callable, ClassVar, Generic, Optional, Sequence, Type, TypeVar, Union


from flex.utils.decorators import export


from .symbols import symbol
from . import abc


_T_Scope = abc._T_Scope
_T_Injected = abc._T_Injected
_T_Injector = abc._T_Injector
_T_Provider = abc._T_Provider

_T_Injectable = abc._T_Injectable

_T_Cache = abc._T_Cache
_T_Providers =  abc._T_Providers





@export()
class Injector(abc.Injector[_T_Scope, _T_Injected, _T_Provider, _T_Injector]):

    __slots__ = ('__skipself', '_verb')

    __skipself: bool

    def __init__(self, scope: _T_Scope, parent: _T_Injector):
        super().__init__(scope, parent)
        self.__skipself = False
  
    @property
    def head(self):
        return self.parent.head if self.__skipself else self

    def __getitem__(self, k: _T_Injectable) -> _T_Injected:
        if self.__skipself:
            return self.parent[k]
        elif k in self.providers:
            p = self.providers[k]
            if p.cache and k in self.cache:
                return self.cache[k]

            if isinstance(p, list):
                rv = [_p.provide(self) for _p in p]
            else:
                rv = p.provide(self)
            
            if p.cache:
                self.cache[k] = rv
            return rv
        else:
            try:
                self.__skipself = True
                return self.parent[k]
            finally:
                self.__skipself = False

        # # p = self.providers[k]
        # if k not in self.providers:
        # # if p is None:
        #     try:
        #         self._skipself = True
        #         return self.parent[k]
        #     except KeyError as e:
        #         raise KeyError(f'scope={self.scope.name} {k}') from e
        #     finally:
        #         self._skipself = False
        
        # p = self.providers[k]
        # if p.cache and k in self.cache:
        #     return self.cache[k]

        # if isinstance(p, list):
        #     rv = [_p.provide(self) for _p in p]
        # else:
        #     rv = p.provide(self)
        
        # if p.cache:
        #     self.cache[k] = rv
        # return rv

        # try:
        #     return self.cache[k]
        # except KeyError:
        #     p = self.providers[k]
        #     if p is None:
        #         try:
        #             self._skipself = True
        #             return self.parent[k]
        #         finally:
        #             self._skipself = False
        #     elif isinstance(p, list):
        #         rv = [_p.provide(self) for _p in p]
        #     else:
        #         rv = p.provide(self)
            
        #     if p.cache:
        #         self.cache[k] = rv
        #     return rv
    





@export()
class NullInjector(abc.Injector[None, _T_Injected, None]):
    """NullInjector Object"""

    __slots__ = ()

    def __init__(self):
        super().__init__(None, None)
   
    def __contains__(self, x) -> bool:
        return False

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def __iter__(self) -> None:
        return iter(())
    
    def __getitem__(self, k: _T_Injectable) -> None:
        # return None
        raise KeyError(k)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def __str__(self) -> str:
        lvl = self._lvl
        return f'{self.__class__.__name__}({lvl=})'
