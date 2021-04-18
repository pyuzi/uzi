
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
class Injector(abc.Injector[_T_Scope, _T_Injected, _T_Provider]):

    __slots__ = ('_skipself',)

    _skipself: bool

    def __init__(self, scope: abc.Scope, parent: abc.Injector):
        super().__init__(scope, parent)
        self._skipself = False
        
    @property
    def isroot(self):
        return not bool(self.parent)

    @property
    def root(self):
        return self if self.isroot else self.parent.root

    def __getitem__(self, k: _T_Injectable) -> _T_Injected:
        if self._skipself:
            return self.parent[k]

        try:
            return self.cache[k]
        except KeyError:
            p = self.providers[k]
            if p is None:
                try:
                    self._skipself = True
                    return self.parent[k]
                finally:
                    self._skipself = False
            elif isinstance(p, list):
                rv = [_p.provide(self) for _p in p]
            else:
                rv = p.provide(self)
            
            if p.cache:
                self.cache[k] = rv
            return rv
    





@export()
class NullInjector(abc.Injector[None, _T_Injected, None]):
    """NullInjector Object"""

    def __init__(self):
        super().__init__(None, None)
        
    def __len__(self):
        return 0

    def __iter__(self) -> None:
        return iter(())
    
    def __getitem__(self, k: _T_Injectable) -> None:
        raise KeyError(k)

    def __enter__(self):
        return self

    def __enter__(self, *exc):
        pass