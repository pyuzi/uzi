from abc import ABC, ABCMeta, abstractmethod
from itertools import groupby
import re
import sys
from types import MappingProxyType
import typing as t
from logging import getLogger
from collections import abc, defaultdict
from typing_extensions import Self
from weakref import WeakKeyDictionary, WeakSet, WeakValueDictionary, ref
from importlib import import_module
from .exceptions import ProError


from . import signals
from .markers import GUARDED, PRIVATE, PROTECTED, PUBLIC, AccessLevel, _PredicateOpsMixin, Injectable, ProInvertPredicate, ProPredicate, is_injectable
from ._common import ReadonlyDict, ordered_set, private_setattr, FrozenDict
from .providers import Provider, ProviderRegistryMixin


if t.TYPE_CHECKING: # pragma: no cover
    from .graph import DepGraph, DepKey, DepSrc


logger = getLogger(__name__)

_dict_setdefault = dict.setdefault
_dict_setitem = dict.__setitem__
_object_new = object.__new__


def _calling_module(depth=2) -> t.Optional[str]:
    """Get the globals() or locals() scope of the calling scope"""
    name = sys._getframe(depth).f_globals.get('__name__')
    try:
        name and import_module(name) 
    except Exception:
        return
    else:
        return name



class _ContainerRegistry(ReadonlyDict[t.Union[tuple[str], str], t.Union[abc.Set['Container'], Self]]):
    __slots__ = ()

    __getitem = dict[str, abc.MutableSet['Container']].__getitem__

    _placeholders = {
        '**': '[^{placeholders}]*',
        '*': '[^{placeholders}.]*',
        '++': '[^{placeholders}]+',
        '+': '[^{placeholders}.]+',
    }
    
    _pattern_split_re = re.compile(f"({'|'.join(map(re.escape, _placeholders))})")
    pfmt = { 'placeholders': re.escape(''.join({*''.join(_placeholders)})) }
    for k in _placeholders:
        _placeholders[k] = _placeholders[k].format_map(pfmt)
    del k, pfmt

    def put(self, inst: 'Container') -> 'Container':
        self.__getitem(inst.qualname).add(inst)
        return inst
    
    @classmethod
    def complie_pattern(cls, pattern: t.Union[str, re.Pattern]):
        if isinstance(pattern, re.Pattern):
            return pattern
        parts = cls._pattern_split_re.split(pattern)
        pattern = ''.join(cls._placeholders.get(x, re.escape(x)) for x in parts)
        return re.compile(f'^{pattern}$')

    def find(self, *patterns: t.Union[str, re.Pattern], module: str=None, name: str=None, group: bool=False):
        if module or name:

            patterns = (f'{module or "**"}:{name or "**"}',) + patterns
        
        seen = set()
        for pattern in patterns:
            cp = self.complie_pattern(pattern)
            for k, v in self.items():
                if not (k in seen or not cp.search(k) or seen.add(k)):
                    if group:
                        yield tuple(v)
                    else:
                        yield from tuple(v)

    @t.overload                        
    def first(self, *patterns: t.Union[str, re.Pattern], module: str=None, name: str=None, group: bool=True): ...
    def first(self, *a, **kw):
        for v in self.find(*a, **kw):
            return v

    def __getitem__(self, k: str) -> list['Container']:
        return tuple(self.__getitem(k))

    def __missing__(self, key: t.Union[tuple[str], str]):
        return _dict_setdefault(self, key, WeakSet())

    def __repr__(self):
        return f'{self.__class__.__name__}({({k: self[k] for k in self})})'



class ProGroup(FrozenDict['Container', None]):
    
    __slots__ = ()

    __contains = dict.__contains__
    __getitem = dict.__getitem__

    @classmethod
    def atomic(cls, it: abc.Iterable['Container']=()):
        return cls((o, o) for e in it for o in e.origin)

    def _eval_hashable(self):
        return tuple(self)

    def __contains__(self, k) -> bool:
        return self.__contains(k) or any(k in c for c in self)

    # def __len__(self, o: Self) -> bool:
    #     return sum(len(c) for c in self)

    def __eq__(self, o: Self) -> bool:
        if o.__class__ is self.__class__:
            return self.keys() == o.keys()
        return NotImplemented

    def __ne__(self, o: Self) -> bool:
        if o.__class__ is self.__class__:
            return self.keys() != o.keys()
        return NotImplemented

    def __getitem__(self, k: Injectable) -> t.Optional[Provider]:
        for c in self:
            if ret := c[k]:
                return ret
  


class ContainerMeta(ABCMeta):

    _registry: t.ClassVar[_ContainerRegistry] = _ContainerRegistry()
    register: t.Final = ABCMeta.register

    def __call__(self, *args, **kwds):
        if not 'module' in kwds:
            kwds['module'] = _calling_module()
        res: Container = super().__call__(*args, **kwds)
        return self._registry.put(res)



@ProPredicate.register
@private_setattr(frozen='_pro')
class BaseContainer(_PredicateOpsMixin, metaclass=ContainerMeta):
    
    __slots__ = ()
    is_leaf: bool = True
    bases: ProGroup = ProGroup()
    
    _origin_abc: type[Self] = None
    _collection_class: type['Group'] = None

    def __init_subclass__(cls, **kwds) -> None:
        # cls._origin_abc = kwds.get('abc', cls._origin_abc)
        if cls._origin_abc is True:
            cls._origin_abc = cls

        if cls._collection_class is Self:
            cls._collect = cls
        elif cls._collection_class:
            cls._collect = cls._collection_class
            
        return super().__init_subclass__()

    @t.final
    def _collect(self, *a, **kw) -> 'Group':
        return Group(*a, **kw)

    @property
    def origin(self) -> abc.Set[Self]:
        """`ProEnty`(s) 
        """
        return {self}

    @property
    @abstractmethod
    def _pro(self) -> t.Optional[FrozenDict[Self, int]]:
        """The container's provider resolution order."""
        
    @property
    def pro(self) -> FrozenDict[Self, int]:
        """The container's provider resolution order.
        
        Like python's class `__mro__` the `pro` is computed using 
        [C3 linearization](https://en.wikipedia.org/wiki/C3_linearization)

        Returns:
            pro (FrozenDict[Container, int]): 
        """
        if not None is (pro := self._pro):
            return pro
        self.__setattr(_pro=self._evaluate_pro())
        return self._pro     
 
    @property
    def qualname(self) -> str:
        return f'{self.module}:{self.name}'

    @property
    @abstractmethod
    def g(self) -> ReadonlyDict['DepGraph', 'DepGraph']: ...

    @property
    @abstractmethod
    def module(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    def extends(self, other: Self) -> bool:
        """Check whether this container extends the given base. 
        
        Params:
            base (Container): The base container to check

        Returns:
            bool:
        """
        return other in self.pro

    def get_graph(self, base: 'DepGraph'):
        try:
            return self.g[base]
        except KeyError:
            return _dict_setdefault(self.g, base, self.create_graph(base))

    def create_graph(self, base: 'DepGraph'):
        return DepGraph(self, base)


    def pro_entries(self, it: abc.Iterable['Container'], bindings: 'DepGraph', src: 'DepSrc') -> abc.Iterable['Container']:
        pro = self.pro
        return tuple(c for c in it if c in pro)
        
    def _evaluate_pro(self):
        if self.is_leaf:
            res, bases = {self:0}, [*self.bases]
        else:
            res, bases = {}, [*self.origin]

        if bases:
            i, miss = 0, 0
            ml = [*([*b.pro] for b in bases), [*bases]]
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

    def __eq__(self, o) -> bool:
        if True: # self.is_leaf:
            return self is o
        elif isinstance(o, BaseContainer):
            return (self.origin, self._origin_abc) == (o, o._origin_abc)
        return NotImplemented

    def __ne__(self, o) -> bool:
        if True: # self.is_leaf:
            return not self is o
        elif isinstance(o, BaseContainer):
            return (self.origin, self._origin_abc) != (o, o._origin_abc)
        return NotImplemented

    def __hash__(self) -> int:
        if True: # self.is_leaf:
            return id(self)
        else:
            return hash(self.origin)

    def __or__(self, o):
        if isinstance(o, BaseContainer):
            return self._collect((self, o))
        else:
            return super().__or__(o)
    
    __ior__ = __or__

    def __ror__(self, o):
        if isinstance(o, BaseContainer):
            return self._collect((o, self))
        else:
            return super().__ror__(o)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.qualname!r})"




class Container(BaseContainer, ProviderRegistryMixin): #, ReadonlyDict[Injectable, Provider]):
    """A mapping of dependencies to their providers. We use them to bind 
    dependencies to their providers. 
   
    Attributes:
        name (str): The container's name
        bases (tuple[Container]): The container's bases
        default_access_level (AccessLevel): The default `access_level` to assign 
        to providers registered in this container
    """
    __slots__ = 'module', 'name', 'providers', 'bases', 'default_access_level', 'g', '_pro', '__weakref__',
    
    _origin_abc = True

    name: str
    bases: ProGroup
    default_access_level: AccessLevel 
    g: ReadonlyDict['DepGraph', 'DepGraph']
    providers: ReadonlyDict[Injectable, Provider]
    _pro: FrozenDict[Self, int]
    is_leaf: t.Final = True
    
    __setitem = dict[Injectable,  Provider].__setitem__
    __contains = dict[Injectable,  Provider].__contains__

    def __init__(self, name: str=None, *bases: Self, module: str, access_level: AccessLevel=PUBLIC) -> None:
        """Create a container.
        
        Params:
            name (str, optional): Name of the container
            *bases (Container, optional): Base container.
            access_level (AccessLevel, optional): The default `access_level`
                to assign providers
        """
        if name and not name.isidentifier():
            raise ValueError(f'name must be a valid identifier not {name!r}')
        
        self.__setattr(
            _pro=None, 
            bases=ProGroup(),
            name=name or f'', 
            providers=ReadonlyDict(),
            module=module, 
            g=ReadonlyDict(),
            default_access_level=AccessLevel(access_level)
        )
        
        bases and self.extend(*bases)
        signals.on_container_create.send(self.__class__, container=self)

    def extend(self, *bases: Self) -> Self:
        """Adds containers to extended by this container.
        Args:
            *bases (Container): The base containers to be extended
            
        Returns:
            Self: this container
        """
        self.__setattr(bases=self.bases | ProGroup.atomic(bases))
        return self

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


    def __contains__(self, x):
        return x in self.providers or x in self.bases

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
            _dict_setitem(self.providers, key, prov)
            # self.__setitem(key, prov)
            signals.on_provider_registered.send(self, abstract=key, provider=provider)

    def __getitem__(self, k):
        try:
            return self.providers[k]    
        except KeyError:
            if isinstance(k, Provider) and (k.container or self) is self:
                return k
        
    def _resolve(self, key: 'DepKey', bindings: 'DepGraph'):
        if prov := self[key.abstract]:
            access = prov.access_level or self.default_access_level

            if access in self.access_level(key.container):
                if prov._can_resolve(key, bindings):
                    return prov,
        return ()

    def __bool__(self):
        return True
        


class Group(BaseContainer):
    """A `Container` group.
    """
    __slots__ = 'g', 'origin', 'name', 'module', '_pro', '__weakref__',
    _origin_abc = True

    origin: ProGroup
    _pro: FrozenDict[Self, int]
    
    @t.overload
    def __new__(cls: type[Self], it: t.Union[abc.Iterable[Container], Self]=(), *, name: str=None, module: str=None) -> Self: ...
    def __new__(cls: type[Self], it: t.Union[abc.Iterable[Container], Self]=(), *, module: str, **kwds) -> Self:
        self = _object_new(cls)
        typ: type[it] = it.__class__
        if issubclass(typ, cls):
            if not kwds and module == it.module:
                return it
            else:
                kwds['origin'], kwds['_pro'] = it.origin, it._pro
        elif typ is ProGroup:
            kwds['origin'], kwds['_pro'] = it, None
        else:
            kwds['origin'] = it = ProGroup.atomic(it)
            kwds['_pro'] = None

        kwds['name'] = kwds.get('name') or '|'.join(ordered_set(c.qualname for c in it))
        self.__setattr(module=module, g=ReadonlyDict(), **kwds)
        return self

    @property
    def providers(self):
        return MappingProxyType(self.origin)


    def __sub__(self, o):
        if isinstance(o, BaseContainer):
            check = o.origin
            return self._collect(x for x in self.origin if not x in check)
        return NotImplemented
        
    def __rsub__(self, o):
        if isinstance(o, Group):
            check = self.origin
            return self._collect(x for x in o.origin if not x in check)
        return NotImplemented
    
    def __bool__(self):
        return not not self.origin

    def __iter__(self):
        yield from self.origin

    def __contains__(self, k):
        return k in self.origin

    def __getitem__(self, k):
        return self.origin[k]
    
    def _resolve(self, key: 'DepKey', bindings: 'DepGraph'):
        return ()
    

ContainerMeta.register = None



from .graph import DepGraph, _null_graph
