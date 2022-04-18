from threading import Lock
import typing as t
from logging import getLogger

from typing_extensions import Self

import attr


from . import Injectable, InjectionMarker
from ._common import private_setattr, frozendict
from .providers import Provider, AbstractProviderRegistry

logger = getLogger(__name__)




@InjectionMarker.register
@private_setattr
@attr.s(slots=True, frozen=True, repr=True, cmp=False)
class Container(frozendict[Injectable, Provider], AbstractProviderRegistry):

    __id = 0
    __lock = Lock()

    id: int = attr.ib(init=False)
    @id.default
    def _init_id(self):
        with self.__class__.__lock:
            self.__class__.__id += 1
            return self.__class__.__id

    name: str = attr.ib(default='<anonymous>')
    _included: frozendict[Self, Self] = attr.ib(factory=frozendict, init=False, repr=False) 
    __setdefault: t.Callable[..., Provider] = dict[Injectable, Provider].setdefault
    __setitem = dict[Injectable,  Provider].__setitem__

    @property
    
    def included(self):
        return self._included.keys()

    def includes(self, other: Self):
        return other is self \
            or other in self._included \
            or any(c.includes(other) for c in self._included)

    def include(self, *containers: "Container") -> Self:
        self.__setattr(_included=self._included | dict.fromkeys(containers))
        return self
    
    def _dro_entries_(self):
        yield self
        for inc in reversed(self._included):
            yield from inc._dro_entries_()

    def __setitem__(self, abstract: Injectable, provider: Provider) -> Self:
        if pro :=  provider.set_container(self):
            self.__setitem(abstract, pro)

    def __missing__(self, abstract):
        if isinstance(abstract, Provider) and (abstract.container or self) is self:
            return abstract

    def __bool__(self):
        return True
    
    def __eq__(self, o) -> bool:
        return o is self or (False if isinstance(o, Container) else NotImplemented)

    def __ne__(self, o) -> bool:
        return not o is self or (True if isinstance(o, Container) else NotImplemented)

    def __hash__(self):
        return hash(self.name)

