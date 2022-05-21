from abc import ABCMeta, abstractmethod
import re
import sys
import typing as t
from logging import getLogger
from collections import ChainMap, abc
from typing_extensions import Self
from weakref import WeakKeyDictionary
from importlib import import_module
from .exceptions import ProError


from . import signals
from .markers import (
    GUARDED,
    PRIVATE,
    PROTECTED,
    PUBLIC,
    AccessModifier,
    _PredicateOpsMixin,
    Injectable,
    ProPredicate,
    is_injectable,
)
from ._common import ReadonlyDict, ordered_set, private_setattr, FrozenDict
from .providers import Provider, ProviderRegistryMixin

from .graph.core import Graph, DepKey, DepSrc


logger = getLogger(__name__)

_dict_setdefault = dict.setdefault
_dict_setitem = dict.__setitem__
_object_new = object.__new__


def _calling_module(depth=2) -> t.Optional[str]:
    """Get the globals() or locals() scope of the calling scope"""
    name = sys._getframe(depth).f_globals.get("__name__")
    try:
        name and import_module(name)
    except Exception:  # pragma: no cover
        return
    else:
        if name == __name__:
            name = _calling_module(depth + 2)
        return name


class _ContainerRegistry(ReadonlyDict[str, dict["BaseContainer", None]]):
    __slots__ = ()

    __getitem = dict[str, dict["BaseContainer", None]].__getitem__
    __get = dict[str, dict["BaseContainer", None]].get
    __contains = dict[str, dict["BaseContainer", None]].__contains__

    _placeholders = {
        "**": r".*",  # '[^{placeholders}]*',
        "*": r"[^.|:]*",  #'[^{placeholders}.]*',
        "++": r".+",  # '[^{placeholders}]+',
        "+": r"[^.|:]+",  # '[^{placeholders}.]+',
    }

    _pattern_split_re = re.compile(f"({'|'.join(map(re.escape, _placeholders))})")
    pfmt = {"placeholders": re.escape("".join({*"".join(_placeholders)}))}
    for k in _placeholders:
        _placeholders[k] = _placeholders[k].format_map(pfmt)
    del k, pfmt

    @classmethod
    def _complie_pattern(cls, pattern: t.Union[str, re.Pattern]):
        if isinstance(pattern, re.Pattern):
            return pattern
        parts = cls._pattern_split_re.split(pattern)
        pattern = "".join(cls._placeholders.get(x, re.escape(x)) for x in parts)
        return re.compile(f"^{pattern}$")

    def add(self, *instances: "BaseContainer"):
        for inst in instances:
            inst._is_anonymous or self.__getitem(inst.qualname).setdefault(inst)

    def get(self, key: str, default=None):
        ret = self.__get(key)
        return default if ret is None else tuple(ret)

    @t.overload
    def all(
        self,
        *patterns: t.Union[str, re.Pattern],
        module: t.Union[str, list[str], tuple[str]] = None,
        name: t.Union[str, list[str], tuple[str]] = None,
        group: t.Literal[False] = False,
    ) -> abc.Generator["BaseContainer", None, None]:
        ...  # pragma: no cover

    @t.overload
    def all(
        self,
        *patterns: t.Union[str, re.Pattern],
        module: t.Union[str, list[str], tuple[str]] = None,
        name: t.Union[str, list[str], tuple[str]] = None,
        group: t.Literal[True] = True,
    ) -> abc.Generator[tuple["BaseContainer"], None, None]:
        ...  # pragma: no cover

    def all(
        self,
        *patterns: t.Union[str, re.Pattern],
        module: t.Union[str, list[str], tuple[str]] = None,
        name: t.Union[str, list[str], tuple[str]] = None,
        group: bool = False,
    ):

        if module or name:
            if not isinstance(module, (list, tuple)):
                module = (f'{module or "**"}',)
            if not isinstance(name, (list, tuple)):
                name = (f'{name or "**"}',)

            lm, ln = len(module), len(name)
            if lm == ln:
                it = zip(module, name)
            elif lm == 1:
                it = zip(module * ln, name)
            elif ln == 1:
                it = zip(module, name * lm)
            else:
                raise ValueError(
                    f"`module` and `name` lists can either be of equal lengths "
                    f"or one of them must contain a single item."
                )
            patterns = tuple(":".join(mn) for mn in it) + patterns
        elif not patterns:
            patterns = ("**",)

        seen = set()
        for pattern in (self._complie_pattern(p) for p in patterns):
            for k, v in self.items():
                if not (k in seen or not pattern.search(k) or seen.add(k)):
                    if group:
                        yield tuple(v)
                    else:
                        yield from v

    @t.overload
    def find(
        self,
        *patterns: t.Union[str, re.Pattern],
        module: str = None,
        name: str = None,
        group: bool = True,
    ):
        ...  # pragma: no cover

    def find(self, *a, **kw):
        for v in self.all(*a, **kw):
            return v

    def __contains__(self, k: t.Union[str, "BaseContainer"]):
        if isinstance(k, BaseContainer):
            return k in self.__get(k.qualname, ())
        return self.__contains(k)

    def __getitem__(self, k: str) -> tuple["BaseContainer"]:
        return tuple(self.__getitem(k))

    def __missing__(self, key: str):
        return _dict_setdefault(self, key, WeakKeyDictionary())

    def __repr__(self):
        return f"{self.__class__.__name__}({({k: self[k] for k in self})})"


class ProEntrySet(FrozenDict["BaseContainer", None]):

    __slots__ = ()

    __contains = dict.__contains__
    is_atomic: bool = False

    @classmethod
    def make(cls, it: abc.Iterable["BaseContainer"] = ()):
        return it if isinstance(it, cls) else cls((v, None) for v in it)

    fromkeys = make

    def atomic(self):
        return AtomicProEntrySet.make(self)

    def _eval_hashable(self):
        return tuple(self.atomic())

    __hash__ = FrozenDict.__hash__

    def __contains__(self, k: "BaseContainer") -> bool:
        if self.__contains(k):
            return True
        elif getattr(k, "is_atomic", True):
            return not self.is_atomic and any(k in c for c in self if not c.is_atomic)
        else:
            return all(a in self for a in k.atomic)

    def __eq__(self, o: Self) -> bool:
        if isinstance(o, ProEntrySet):
            return self._eval_hashable() == o._eval_hashable()
        elif isinstance(o, abc.Mapping):
            return False
        return NotImplemented

    def __ne__(self, o: Self) -> bool:
        if isinstance(o, ProEntrySet):
            return self._eval_hashable() != o._eval_hashable()
        elif isinstance(o, abc.Mapping):
            return True
        return NotImplemented


class AtomicProEntrySet(ProEntrySet):

    __slots__ = ()

    is_atomic: bool = True

    @classmethod
    def make(cls, it: abc.Iterable["Container"] = ()):
        return (
            it
            if isinstance(it, cls)
            else cls((a, None) for at in it for a in at.atomic)
        )

    def atomic(self):
        return self

    def _eval_hashable(self):
        return tuple(self)


class ContainerMeta(ABCMeta):

    _registry: t.ClassVar[_ContainerRegistry] = _ContainerRegistry()
    register: t.Final = ABCMeta.register

    def __call__(self, *args, **kwds):
        if not "module" in kwds:
            kwds["module"] = _calling_module()
        res: Container = super().__call__(*args, **kwds)
        self._registry.add(res)
        return res


@ProPredicate.register
@private_setattr(frozen="_pro")
class BaseContainer(_PredicateOpsMixin, metaclass=ContainerMeta):

    __slots__ = ()
    is_atomic: bool = True

    @classmethod
    @abstractmethod
    def _collect(cls, *a, **kw) -> "Group":
        ...  # pragma: no cover

    @property
    def _is_anonymous(self) -> bool:
        """`True` if this container can be added to the registry or `False` if
        otherwise.
        """
        return not self.name

    @property
    @abstractmethod
    def atomic(self):
        """`AtomicProEntries`(s)"""

    @property
    @abstractmethod
    def bases(self) -> abc.Mapping[Injectable, Provider]:
        """the base container."""

    @property
    @abstractmethod
    def providers(self) -> abc.Mapping[Injectable, Provider]:
        """A mapping of providers registered in the container."""

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
        return f"{self.module}:{self.name}"

    @property
    @abstractmethod
    def g(self) -> ReadonlyDict["Graph", "Graph"]:
        ...  # pragma: no cover

    @property
    @abstractmethod
    def module(self) -> str:
        ...  # pragma: no cover

    @property
    @abstractmethod
    def name(self) -> str:
        ...  # pragma: no cover

    def extends(self, other: Self) -> bool:
        """Check whether this container extends the given base.

        Params:
            base (Container): The base container to check

        Returns:
            bool:
        """
        return other in self.pro
        # if other.is_atomic:
        #     return other in self.pro
        # else:
        #     return all(self.extends(x) for x in other.atomic)

    def get_graph(self, base: "Graph"):
        try:
            return self.g[base]
        except KeyError:
            return _dict_setdefault(self.g, base, self.create_graph(base))

    def create_graph(self, base: "Graph"):
        return Graph(self, base)

    def pro_entries(
        self, it: abc.Iterable["Container"], graph: "Graph", src: "DepSrc"
    ) -> abc.Iterable["Container"]:
        pro = self.pro
        return tuple(c for c in it if c in pro)

    def _evaluate_pro(self):
        if self.is_atomic:
            res, bases = {self: 0}, [*self.bases]
        else:
            res, bases = {}, [*self.atomic]

        if bases:
            i, miss = 0, 0
            ml = [*([*b.pro] for b in bases), [*bases]]
            while ml:
                if i == len(ml):
                    if miss >= i:
                        raise ProError(
                            f"Cannot create a consistent provider resolution order {miss=}, {ml=}"
                        )
                    i = 0
                ls = ml[i]
                h = ls[0]
                if h in res:
                    pass
                elif any(l.index(h) > 0 for l in ml if not l is ls and h in l):
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

        return AtomicProEntrySet.fromkeys(res)

    def __eq__(self, o) -> bool:
        if isinstance(o, BaseContainer):
            return self is o
        return NotImplemented

    def __ne__(self, o) -> bool:
        if isinstance(o, BaseContainer):
            return not self is o
        return NotImplemented

    def __hash__(self) -> int:
        return id(self)

    def __or__(self, o):
        if isinstance(o, BaseContainer):
            return self._collect((self, o))
        else:
            return super().__or__(o)

    __ior__ = __or__

    # def __ror__(self, o):
    #     if isinstance(o, BaseContainer):
    #         return self._collect((o, self))
    #     else:
    #         return super().__ror__(o)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.qualname!r})"


class Container(BaseContainer, ProviderRegistryMixin):
    """A mapping of dependencies to their providers. We use them to bind
    dependencies to their providers.

    Attributes:
        name (str): The container's name
        bases (tuple[Container]): The container's bases
        default_access_modifier (AccessModifier): The default `access_modifier` to assign
        to providers registered in this container
    """

    __slots__ = (
        "module",
        "name",
        "providers",
        "bases",
        "default_access_modifier",
        "g",
        "_pro",
        "__weakref__",
    )

    name: str
    bases: ProEntrySet
    default_access_modifier: AccessModifier
    g: ReadonlyDict["Graph", "Graph"]
    providers: ReadonlyDict[Injectable, Provider]
    _pro: FrozenDict[Self, int]
    is_atomic: t.Final = True

    def __init__(
        self,
        name: str = None,
        *bases: Self,
        module: str,
        access_modifier: AccessModifier = PUBLIC,
    ) -> None:
        """Create a container.

        Params:
            name (str, optional): Name of the container
            *bases (Container, optional): Base container.
            access_modifier (AccessModifier, optional): The default `access_modifier`
                to assign providers
        """
        if name and not name.isidentifier():
            raise ValueError(f"name must be a valid identifier not {name!r}")

        self.__setattr(
            _pro=None,
            bases=ProEntrySet(),
            name=name or f"__anonymous__",
            providers=ReadonlyDict(),
            module=module,
            g=ReadonlyDict(),
            default_access_modifier=AccessModifier(access_modifier),
        )

        bases and self.extend(*bases)
        signals.on_container_create.send(self.__class__, container=self)

    @property
    def atomic(self):
        """`AtomicProEntries`(s)"""
        return AtomicProEntrySet(((self, None),))

    def extend(self, *bases: Self) -> Self:
        """Adds containers to extended by this container.
        Args:
            *bases (Container): The base containers to be extended

        Returns:
            Self: this container
        """
        self.__setattr(bases=self.bases | ProEntrySet.make(bases))
        return self

    def access_modifier(self, accessor: Self):
        """Get the `AccessModifier`

        Params:
            accessor (Container):

        Returns:
            access_modifier (AccessModifier):
        """
        if accessor is self:
            return PRIVATE
        elif self.extends(accessor):
            return GUARDED
        elif accessor.extends(self):
            return PROTECTED
        else:
            return PUBLIC

    @classmethod
    def _collect(cls, *a, **kw) -> "Group":
        return Group(*a, **kw)

    def _on_register(self, abstract: Injectable, provider: Provider):
        pass

    def __contains__(self, x):
        return x in self.providers or any(x in b for b in self.bases)

    def __setitem__(self, key: Injectable, provider: Provider) -> Self:
        """Register a dependency provider

            container[_T] = providers.Value('abc')

        Params:
            abstract (Injectable): The dependency to be provided
            provider (Provider): The provider to provide the dependency
        """
        if not is_injectable(key):
            raise TypeError(
                f"expected `Injectable` not. `{key.__class__.__qualname__}`"
            )

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

    def _resolve(self, key: "DepKey", graph: "Graph"):
        if prov := self[key.abstract]:
            access = prov.access_modifier or self.default_access_modifier

            if access in self.access_modifier(key.container):
                if prov._can_resolve(key, graph):
                    return (prov,)
        return ()

    def __bool__(self):
        return True


class Group(BaseContainer):
    """A `Container` group."""

    __slots__ = (
        "_g",
        "bases",
        "name",
        "module",
        "_pro",
        "_is_anonymous",
        "__weakref__",
    )
    is_atomic = False

    bases: ProEntrySet
    _pro: FrozenDict[Self, int]

    def __new__(
        cls: type[Self],
        bases: t.Union[abc.Iterable[Container], Self] = (),
        *,
        name: str = None,
        module: str,
    ) -> Self:
        self = _object_new(cls)
        # typ: type[bases] = bases.__class__
        # if issubclass(typ, cls):
        #     if not name and module == bases.module:
        #         return bases
        #     else:
        #         bases = bases.bases
        # else:
        #     bases = ProEntrySet.make(bases)

        self.__setattr(
            _pro=None,
            bases=ProEntrySet.make(bases),
            _is_anonymous=not name,
            module=module,
            name=name or f'[{"|".join(ordered_set(c.qualname for c in bases))}]',
        )
        return self

    @property
    def g(self):
        try:
            return self._g
        except AttributeError:
            self.__setattr(_g=ReadonlyDict())
            return self._g

    @property
    def atomic(self):
        return self.bases.atomic()

    @property
    def qualname(self) -> None:
        return f"{self.module}:{self.name}"

    @property
    def providers(self):
        return ChainMap(*(a.providers for a in self.bases))

    @classmethod
    def _collect(cls, *a, **kw):
        return cls(*a, **kw)

    def __sub__(self, o):
        if isinstance(o, BaseContainer):
            check = o.atomic
            return self._collect(x for x in self.atomic if not x in check)
        return NotImplemented

    __isub__ = __sub__

    # def __rsub__(self, o):
    #     if isinstance(o, Group):
    #         check = self.atomic
    #         return self._collect(x for x in o.atomic if not x in check)
    #     return NotImplemented

    def __bool__(self):
        return not not self.bases

    def __contains__(self, x):
        return any(x in b for b in self.bases)


ContainerMeta.register = None
