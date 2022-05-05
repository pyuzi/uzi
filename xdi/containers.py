import typing as t
from logging import getLogger
from collections import abc
from typing_extensions import Self

from .exceptions import ProError


from . import signals
from .markers import GUARDED, PRIVATE, PROTECTED, PUBLIC, AccessLevel, _PredicateOpsMixin, Injectable, ProPredicate, is_injectable
from ._common import ReadonlyDict, private_setattr, FrozenDict
from .providers import Provider, AbstractProviderRegistry


if t.TYPE_CHECKING: # pragma: no cover
    from .graph import DepGraph, DepKey, DepSrc


logger = getLogger(__name__)

_dict_setdefault = dict['DepGraph', 'DepGraph'].setdefault



@ProPredicate.register
@private_setattr(frozen='_frozen')
class Container(_PredicateOpsMixin, AbstractProviderRegistry, ReadonlyDict[Injectable, Provider]):
    """A mapping of dependencies to their providers. We use them to bind 
    dependencies to their providers. 
   
    Attributes:
        name (str): The container's name
        bases (tuple[Container]): The container's bases
        default_access_level (AccessLevel): The default `access_level` to assign 
        to providers registered in this container
    """
    __slots__ = 'name', 'bases', 'default_access_level', 'g', '_pro',

    name: str
    bases: tuple[Self]
    default_access_level: AccessLevel 
    g: ReadonlyDict['DepGraph', 'DepGraph']
    _pro: FrozenDict[Self, int]
    
    __setitem = dict[Injectable,  Provider].__setitem__
    __contains = dict[Injectable,  Provider].__contains__

    def __init__(self, name: str='<anonymous>', *bases: Self, access_level: AccessLevel=PUBLIC) -> None:
        """Create a container.
        
        Params:
            name (str, optional): Name of the container
            *bases (Container, optional): Base container.
            access_level (AccessLevel, optional): The default `access_level`
                to assign providers
        """
        self.__setattr(
            _pro=None, 
            bases=(),
            name=name, 
            g=ReadonlyDict(),
            default_access_level=AccessLevel(access_level)
        )
        bases and self.extend(*bases)
        signals.on_container_create.send(self.__class__, container=self)

    @property
    def _frozen(self) -> bool:
        return not not self._pro

    @property
    def pro(self):
        """The container's provider resolution order.
        
        Like python's class `__mro__` the `pro` is computed using 
        [C3 linearization](https://en.wikipedia.org/wiki/C3_linearization)

        Returns:
            pro (FrozenDict[Container, int]): 
        """
        if pro := self._pro:
            return pro
        self.__setattr(_pro=self._evaluate_pro())
        return self._pro

    def pro_entries(self, it: abc.Iterable['Container'], bindings: 'DepGraph', src: 'DepSrc') -> abc.Iterable['Container']:
        pro = self.pro
        return tuple(c for c in it if c in pro)
        
    def _evaluate_pro(self):
        bases = [*self.bases]

        if not bases:
            return FrozenDict({ self : 0 })

        ml = [*([*b.pro] for b in bases), [*bases]]
        res = {self: 0}
        
        i, miss = 0, 0
        while ml:
            if i == len(ml):
                if miss >= i:
                    raise ProError(f'Cannot create a consistent provider resolution order {miss=}, {ml=}')
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

        return FrozenDict({c: i for i,c in enumerate(res)})

    def extend(self, *bases: Self) -> Self:
        """Adds containers to extended by this container.
        Args:
            *bases (Container): The base containers to be extended
            
        Returns:
            Self: this container
        """
        self.__setattr(bases=tuple(dict.fromkeys(self.bases + bases)))
        return self

    def extends(self, other: Self) -> bool:
        """Check whether this container extends the given base. 
        
        Params:
            base (Container): The base container to check

        Returns:
            bool:
        """
        return other in self.pro

    def access_level(self, accessor: Self):
        """Get the `AccessLevel` 

        Params:
            accessor (Container): 

        Returns:
            access_level (AccessLevel):
        """
        if accessor is self:
            return PRIVATE
        elif self.extends(accessor):
            return GUARDED
        elif accessor.extends(self):
            return PROTECTED
        else:
            return PUBLIC

    def _on_register(self, abstract: Injectable, provider: Provider):
        pass

    def get_graph(self, base: 'DepGraph'):
        try:
            return self.g[base]
        except KeyError:
            # if parent.container.extends(self):
            #     raise ProError(f'given parent extends self: {parent=}, {self=}')
            return _dict_setdefault(self.g, base, self.create_graph(base))

    def create_graph(self, base: 'DepGraph'):
        return DepGraph(self, base)

    def __contains__(self, x):
        return self.__contains(x) or any(x in b for b in self.bases)

    def __setitem__(self, key: Injectable, provider: Provider) -> Self:
        """Register a dependency provider 
        
            container[_T] = providers.Value('abc')

        Params:
            abstract (Injectable): The dependency to be provided
            provider (Provider): The provider to provide the dependency
        """
        if not is_injectable(key):
            raise TypeError(f'expected `Injectable` not. `{key.__class__.__qualname__}`')

        if prov := provider._setup(self, key):
            self._on_register(key, prov)
            self.__setitem(key, prov)
            signals.on_provider_registered.send(self, abstract=key, provider=provider)

    def __missing__(self, key):
        if isinstance(key, Provider) and (key.container or self) is self:
            return key
            
    def _resolve(self, key: 'DepKey', bindings: 'DepGraph'):
        if prov := self[key.abstract]:
            access = prov.access_level or self.default_access_level
            if access in self.access_level(key.container):
                if prov._can_resolve(key, bindings):
                    return prov,
        return ()

    def __bool__(self):
        return True
    
    def __eq__(self, o) -> bool:
        return o is self or (False if isinstance(o, Container) else NotImplemented)

    def __ne__(self, o) -> bool:
        return not o is self or (True if isinstance(o, Container) else NotImplemented)

    def __hash__(self):
        return hash(id(self))

    def __repr__(self):
        return f'{self.__class__.__name__}({self.name!r})'









from .graph import DepGraph, _null_graph
