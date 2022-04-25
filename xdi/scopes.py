from itertools import chain
from logging import getLogger
import typing as t

import attr
from typing_extensions import Self
from collections.abc import Set

from xdi._common import Missing, private_setattr
from xdi._common import frozendict
from xdi.providers import Provider

from . import Injectable, is_injectable
from ._dependency import Dependency, LookupErrorDependency

from .containers import Container
from ._builtin import __builtin_container__

logger = getLogger(__name__)

class EmptyScopeError(RuntimeError):
    ...



@attr.s(slots=True, frozen=True, cmp=False)
@private_setattr
class Scope(frozendict[tuple, t.Union[Dependency, None]]):
    """An isolated dependency resolution `scope` for a given container. 

    Scopes assemble the dependency graphs of dependencies registered in their container.

    Attributes:
        container (Container): The container who's scope we are creating
        parent (Scope): The parent scope. Defaults to None

    Args:
        container (Container): The container who's scope we are creating
        parent (Scope, optional): The parent scope. Defaults to NullScope

    """

    container: 'Container' = attr.ib(repr=True)
    parent: Self = attr.ib(converter=lambda s=None: s or NullScope(), default=None)

    path: tuple = attr.ib(init=False, repr=True)
    @path.default
    def _init_path(self):
        return  self.container, *self.parent.path,

    _v_hash: int = attr.ib(init=False, repr=False)
    @_v_hash.default
    def _init_v_hash(self):
        return hash(self.path)

    _builtins: tuple['Container'] = attr.ib(kw_only=True, repr=False)
    @_builtins.default
    def _init_builtins(self):
        return __builtin_container__,

    # _injector_class: type[Injector] = attr.ib(kw_only=True, default=Injector, repr=False)
    
    maps: Set[Container] = attr.ib(init=False, repr=False)
    @maps.default
    def _init_maps(self):
        container, parent, builtin = self.container, self.parent, self._builtins
        if dro := [c for c in container.pro if c not in parent]:
            dro_builtin = (c.pro for c in builtin)
            dct = {c: i for i, c in enumerate(chain(dro, *dro_builtin))}
            return t.cast(Set[Container], dct.keys())
        raise EmptyScopeError(f'{self}')

    __contains = dict.__contains__
    __setdefault = dict.setdefault

    @property
    def name(self) -> str:
        """The name of the scope. Usually returns the scope's `container.name` 
        """
        return self.container.name

    @property
    def level(self) -> int:
        return self.parent.level + 1

    def parents(self):
        """Returns a generetor that iterates over the scope's ancestor starting 
        from the current `parent` to the root scope.

        Yields:
            ancestor (Scope): an ancestor.
        """
        parent = self.parent
        while parent:
            yield parent
            parent = parent.parent
 
    def find_local(self, abstract: Injectable):
        res = self.get(abstract, Missing)
        if res is Missing:
            res = self.__missing__(abstract, recursive=False)
        
        if res and self is res.scope:
            return res

    def find_remote(self, abstract: Injectable):
        return self.parent[abstract]

    def resolve_providers(self, abstract: Injectable, source: Container=None):
        rv = [p for c in self.maps if (p := c[abstract])]
        rv and rv.sort(key=lambda p: int(not not p.is_default))
        if origin := t.get_origin(abstract):
            rv.extend(self.resolve_providers(origin, source))
        return rv
    
    def __bool__(self):
        return True
    
    def __contains__(self, o) -> bool:
        return self.__contains(o) or o in self.maps or o in self.parent

    def __missing__(self, abstract: Injectable, *, recursive=True) -> t.Union[Dependency, None]:
        if implicit := getattr(abstract, '__xdi_provider__', None):
            return self[implicit]
        elif is_injectable(abstract):
            for pro in self.resolve_providers(abstract):
                if dep := pro.resolve(abstract, self):
                    return self.__setdefault(abstract, dep)
            if dep := recursive and self.parent[abstract]:
                return self.__setdefault(abstract, dep)
            else:
                return LookupErrorDependency(abstract, self)
        raise TypeError(f'Scope key must be an `Injectable` not `{abstract.__class__.__qualname__}`')

    def __eq__(self, o) -> bool:
        if isinstance(o, Scope):
            return o.path == self.path 
        return NotImplemented

    def __ne__(self, o) -> bool:
        if isinstance(o, Scope):
            return o.path != self.path 
        return NotImplemented

    def __hash__(self):
        return self._v_hash





class NullScope(Scope):
    """A 'noop' `Scope` used as the parent of root scopes.  

    Attributes:
        container (frozendict): 
        parent (None): The parent scope

    Params:
        None

    """

    __slots__ = ()
    parent = None
    container = frozendict()
    maps = frozenset()
    level = -1
    path = ()
    _v_hash = hash(path)
    
    name = '<null>'

    def __init__(self) -> None: ...

    def __bool__(self): 
        return False
    def __repr__(self): 
        return f'{self.__class__.__name__}()'
    def __contains__(self, key): 
        return False
    def __getitem__(self, abstract): 
        if is_injectable(abstract):
            return LookupErrorDependency(abstract, self)
        else:
            raise TypeError(f'Scope keys must be `Injectable` not `{abstract.__class__.__qualname__}`')
        