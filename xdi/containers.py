from threading import Lock
import typing as t
from logging import getLogger
from collections.abc import Set
from typing_extensions import Self

import attr


from . import Injectable, InjectionMarker
from ._common import private_setattr, frozendict
from .providers import Provider, AbstractProviderRegistry

logger = getLogger(__name__)




@InjectionMarker.register
@attr.s(slots=True, frozen=True, repr=True, cmp=False)
@private_setattr(frozen='_frozen')
class Container(frozendict[Injectable, Provider], AbstractProviderRegistry):

    __id = -2
    __lock = Lock()
    
    _frozen: bool = attr.ib(init=False, repr=False, default=False)
    
    id: int = attr.ib(init=False)
    @id.default
    def _init_id(self):
        with self.__class__.__lock:
            self.__class__.__id += 1
            return self.__class__.__id

    name: str = attr.ib(default='<anonymous>')
    bases: tuple[Self] = attr.ib(default=(), init=True, repr=True and (lambda s: f"[{', '.join(f'{c.name!r}' for c in s)}]")) 
    _pro: tuple[Self] = attr.ib(default=None, init=False, repr=False and (lambda s: f"[{', '.join(f'{c.name!r}' for c in s)}]")) 
    __setitem = dict[Injectable,  Provider].__setitem__

    @property
    def pro(self):
        if pro := self._pro:
            return pro
        self.__setattr(_pro=self._pro_entries())
        return self._pro

    def _pro_entries(self):
        """Get provider resolution order.
        
        Uses C3 linearization https://en.wikipedia.org/wiki/C3_linearization
        """
        bases = [*self.bases]

        if not bases:
            return self,

        res = {self: 0}
        ml = [*([*b.pro] for b in bases), [*bases]]
        
        i, miss = 0, 0
        while ml:
            if i == len(ml):
                if miss >= i:
                    raise TypeError(f'Cannot create a consistent provider resolution {miss=}, {ml=}')
                i = 0
            ls = ml[i]
            h = ls[0]
            if h in res:
                pass
            elif any(l.index(h) > 0 for l in  ml if not l is ls and h in l):
                i += 1
                miss += 1
                continue
            else:
                res[h] = i
            ls.pop(0)
            miss = 0
            if ls:
                i += 1
            else:
                ml.pop(i)

        return *res,

    def extends(self, other: Self):
        return other in self.pro
        
    def extend(self, *bases: "Container") -> Self:
        self.__setattr(bases=tuple(dict.fromkeys(self.bases + bases)))
        return self
    
    def _on_register(self, abstract: Injectable, provider: Provider):
        pass

    def __setitem__(self, abstract: Injectable, provider: Provider) -> Self:
        if pro :=  provider.set_container(self):
            self._on_register(abstract, pro)
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

