from functools import reduce, wraps
from inspect import Parameter, signature
from logging import getLogger
import operator
from types import FunctionType, GenericAlias, MethodType
import typing as t
from abc import ABC, ABCMeta, abstractmethod
from collections import abc
from enum import Enum

from typing_extensions import Self


from ._common import Missing, private_setattr
from ._common.lookups import Lookup as BaseLookup


if t.TYPE_CHECKING:  # pragma: no cover
    from .containers import Container
    from .graph.core import Graph, DepSrc


_object_new = object.__new__


T_Injected = t.TypeVar("T_Injected", covariant=True)
"""The injected type.
"""

T_Default = t.TypeVar("T_Default")
"""Default value type.
"""

T_Injectable = t.TypeVar("T_Injectable", bound="Injectable", covariant=True)
"""An `Injectable` type.
"""

logger = getLogger(__name__)

_NoneType = type(None)


_BLACKLIST = frozenset(
    {
        None,
        _NoneType,
        t.Any,
        type(t.Literal[1]),
        str,
        bytes,
        bytearray,
        tuple,
        int,
        float,
        frozenset,
        set,
        dict,
        list,
        Parameter.empty,
        Missing,
    }
)


def is_injectable(obj):
    """Returns `True` if the given type annotation is injectable.

    Params:
        typ (type): The type annotation to check.
    Returns:
        (bool): `True` if `typ` can be injected or `False` if otherwise.
    """
    return isinstance(obj, Injectable) and not (
        obj in _BLACKLIST or isinstance(obj, NonInjectable)
    )


def is_injectable_annotation(typ):
    """Returns `True` if the given type annotation is injectable.

    Params:
        typ (type): The type annotation to check.
    Returns:
        (bool): `True` if `typ` can be injected or `False` if otherwise.
    """
    return is_injectable(typ)


class Injectable(metaclass=ABCMeta):
    """Abstract base class for injectable types.

    An injectable is an object that can be used to represent a dependency.

    Builtin injectable types:- `type`, `TypeVar`, `FunctionType`, `MethodType`,
    `GenericAlias`
    """

    __slots__ = ()


Injectable.register(type)
Injectable.register(t.TypeVar)
Injectable.register(FunctionType)
Injectable.register(MethodType)
Injectable.register(GenericAlias)
Injectable.register(type(t.Generic[T_Injected]))
Injectable.register(type(t.Union))


class NonInjectable(metaclass=ABCMeta):
    """Abstract base class for non-injectable types."""

    __slots__ = ()


NonInjectable.register(_NoneType)
NonInjectable.register(type(t.Literal[1]))


__static_makers = {
    t.Union,
    t.Annotated,
}


@t.overload
def is_dependency_marker(obj: "DependencyMarker") -> True:
    ...  # pragma: no cover


@t.overload
def is_dependency_marker(obj: object) -> False:
    ...  # pragma: no cover


def is_dependency_marker(obj: t.Any, ind=0) -> bool:
    """Check if object is a `DependencyMarker`
    Args:
        obj (Any): the object to check

    Returns:
        bool:
    """
    return (
        isinstance(obj, (DependencyMarker, DependencyMarkerType))
        or obj in __static_makers
        or (not not (orig := t.get_origin(obj)) and is_dependency_marker(orig))
    )


class DependencyMarkerType(ABCMeta):
    ...  # pragma: no cover


class DependencyMarker(
    Injectable, t.Generic[T_Injectable], metaclass=DependencyMarkerType
):
    """Abstract base class for dependency markers.

    Dependency markers are used reperesent and/or annotate dependencies.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def __origin__(self):
        ...  # pragma: no cover


_3_nones = None, None, None

_T_Start = t.TypeVar("_T_Start", int, "ProPredicate", None)
_T_Stop = t.TypeVar("_T_Stop", int, "ProPredicate", None)
_T_Step = t.TypeVar("_T_Step", int, None)

_T_PredVar = t.TypeVar("_T_PredVar")
_T_PredVars = t.TypeVar("_T_PredVars", bound=tuple)
_T_Pred = t.TypeVar("_T_Pred", bound="ProPredicate", covariant=True)


@private_setattr
class _PredicateBase:

    __slots__ = ("vars",)

    vars: tuple[_T_PredVar]

    def __new__(cls, *vars: _T_PredVar):
        self = _object_new(cls)
        self.__setattr(vars=vars)
        return self

    @abstractmethod
    def pro_entries(
        self, it: abc.Iterable["Container"], graph: "Graph", src: "DepSrc"
    ) -> abc.Iterable["Container"]:  # pragma: no cover
        raise NotImplementedError(f"{self.__class__.__qualname__}.pro_entries()")

    def __copy__(self):
        return self.__class__(*self.vars)

    def __reduce__(self):
        return self.__class__, tuple(self.vars)


@private_setattr
class _PredicateOpsMixin:

    __slots__ = ()

    def __or__(self, x):
        if isinstance(x, ProPredicate):
            if x == self:
                return self
            return ProOrPredicate(self, x)
        return NotImplemented

    __ior__ = __or__

    def __and__(self, x):
        if isinstance(x, ProPredicate):
            if x == self:
                return self
            return ProAndPredicate(self, x)
        return NotImplemented

    __iand__ = __and__

    def __ror__(self, x):
        if isinstance(x, ProPredicate):
            return ProOrPredicate(x, self)
        return NotImplemented

    def __rand__(self, x):
        if isinstance(x, ProPredicate):
            return ProAndPredicate(x, self)
        return NotImplemented

    def __invert__(self):
        return ProInvertPredicate(self)


class _PredicateCompareMixin:

    __slots__ = ()

    def __eq__(self, o) -> bool:
        if isinstance(o, self.__class__):
            return self.vars == o.vars
        return NotImplemented

    def __ne__(self, o) -> bool:
        if isinstance(o, self.__class__):
            return self.vars != o.vars
        return NotImplemented

    def __forward_op(op):
        @wraps(op)
        def method(self: Self, *a):
            ident = self.vars
            if not a:
                return op(ident)
            elif isinstance(a := a[0], ProPredicate):
                return op(ident, a.vars)
            return NotImplemented

        return method

    __ge__, __gt__ = __forward_op(operator.ge), __forward_op(operator.gt)
    __le__, __lt__ = __forward_op(operator.le), __forward_op(operator.lt)

    __hash__ = __forward_op(hash)

    del __forward_op


class ProPredicate(_PredicateBase, _PredicateOpsMixin, _PredicateCompareMixin, ABC):

    __slots__ = ()

    vars: tuple[_T_PredVar]


@ProPredicate.register
class ProEnumPredicate(_PredicateBase, _PredicateOpsMixin, _PredicateCompareMixin):

    __slots__ = ()
    __setattr__ = object.__setattr__

    @property
    def _rawvalue_(self):
        return self.vars[0]

    # def __copy__(self):
    #     return self


class AccessModifier(ProEnumPredicate, Enum):
    """Access modifier for dependencies 

    Attributes:
        public (AccessModifier): public
        protected (AccessModifier): protected
        guarded (AccessModifier): guarded
        private (AccessModifier): private
    """

    public: "AccessModifier" = 1
    protected: "AccessModifier" = 2
    guarded: "AccessModifier" = 3
    private: "AccessModifier" = 4

    @classmethod
    def _missing_(cls, val):
        if val in _empty_access_modifiers:
            return cls.public
        elif val in _access_lavel_rawvalues:
            return _access_lavel_rawvalues[val]
        return super()._missing_(val)

    def pro_entries(
        self, it: abc.Iterable["Container"], scope: "Graph", src: "DepSrc"
    ) -> abc.Iterable["Container"]:
        return tuple(c for c in it if self in c.access_modifier(src.container))

    def __contains__(self, obj) -> bool:
        return isinstance(obj, AccessModifier) and self.vars >= obj.vars


_empty_access_modifiers = frozenset((None, 0, (0,), (None,)))
_access_lavel_rawvalues = {l._rawvalue_: l for l in AccessModifier}


class ScopePredicate(ProEnumPredicate, Enum):
    """The context in which to provider resolution."""

    only_self: "ScopePredicate" = True
    """Only inject from the current scope without considering parents"""

    skip_self: "ScopePredicate" = False
    """Skip the current scope and resolve from it's parent instead."""

    @classmethod
    def _missing_(cls, val):
        if val in _scope_predicate_rawvalues:
            return _scope_predicate_rawvalues[val]
        return super()._missing_(val)

    def pro_entries(
        self, it: abc.Iterable["Container"], scope: "Graph", src: "DepSrc"
    ) -> abc.Iterable["Container"]:
        return it if (scope is src.graph) is self._rawvalue_ else ()


_scope_predicate_rawvalues = {l._rawvalue_: l for l in ScopePredicate}


PUBLIC: AccessModifier = AccessModifier.public
"""public access modifier"""

PROTECTED: AccessModifier = AccessModifier.protected
"""protected access modifier"""

GUARDED: AccessModifier = AccessModifier.guarded
"""guarded access modifier"""

PRIVATE: AccessModifier = AccessModifier.private
"""private access modifier"""

ONLY_SELF: ScopePredicate = ScopePredicate.only_self
"""Only inject from the current scope without considering parents"""

SKIP_SELF: ScopePredicate = ScopePredicate.skip_self
"""Skip the current scope and resolve from it's parent instead."""


@private_setattr
class ProNoopPredicate(ProPredicate):

    __slots__ = ()

    vars = ()
    __pred = None

    def __new__(cls):
        if self := cls.__pred:
            return self
        self = cls.__pred = _object_new(cls)
        return self

    def pro_entries(
        self, it: abc.Iterable["Container"], *args
    ) -> abc.Iterable["Container"]:
        return it


@private_setattr
class ProOperatorPredicate(ProPredicate):

    __slots__ = ()

    vars: tuple[ProPredicate]

    @staticmethod
    @abstractmethod
    def operate(pros: abc.Set["Container"]) -> abc.Iterable["Container"]:
        ...  # pragma: no cover

    def _reduce(self, it: abc.Iterable[abc.Iterable["Container"]]):
        return reduce(self.operate, it)

    def pro_entries(
        self, it: abc.Iterable["Container"], *args
    ) -> abc.Iterable["Container"]:
        it = tuple(it)
        res = self._reduce({*pred.pro_entries(it, *args)} for pred in self.vars)
        return tuple(sorted(res, key=it.index))


class ProOrPredicate(ProOperatorPredicate):

    __slots__ = ()

    operate = staticmethod(operator.or_)


class ProAndPredicate(ProOperatorPredicate):

    __slots__ = ()

    operate = staticmethod(operator.and_)


class ProSubPredicate(ProOperatorPredicate):

    __slots__ = ()

    operate = staticmethod(operator.sub)


class ProInvertPredicate(ProSubPredicate):

    __slots__ = ()

    def __new__(cls: type[Self], *right: _T_Pred) -> Self:
        return super().__new__(cls, _noop_pred, *right)

    def __copy__(self):
        return self.__class__(*self.vars[1:])

    def __reduce__(self):
        return self.__class__, self.vars[1:]


class ProSlice(ProPredicate, t.Generic[_T_Start, _T_Stop, _T_Step]):
    """Represents a slice or the _Provider resolution order_"""

    __slots__ = ()

    vars: tuple[_T_Start, _T_Stop, _T_Step]

    def __new__(
        cls: type[Self],
        start: _T_Start = None,
        stop: _T_Stop = None,
        step: _T_Step = None,
    ) -> Self:
        return super().__new__(cls, start, stop, step)

    @property
    def start(self):
        return self.vars[0]

    @property
    def stop(self):
        return self.vars[1]

    @property
    def step(self):
        return self.vars[2]

    def pro_entries(
        self, it: abc.Iterable["Container"], scope: "Graph", src: "DepSrc"
    ) -> abc.Iterable["Container"]:
        it = tuple(it)
        start, stop, step = self.vars
        if isinstance(start, ProPredicate):
            start = it.index(next(iter(start.pro_entries(it, scope, src)), None))

        if isinstance(stop, ProPredicate):
            stop = it.index(next(iter(stop.pro_entries(it, scope, src)), None))

        return it[start:stop:step]

    def __repr__(self) -> str:
        start, stop, step = self.start, self.stop, self.step
        return f"[{start}:{stop}:{step}]"


_T_FilterPred = t.TypeVar(
    "_T_FilterPred", bound=abc.Callable[..., bool], covariant=True
)


class ProFilter(ProPredicate):

    __slots__ = ()

    def __new__(cls: type[Self], filter: _T_FilterPred, extra_args: int = None) -> Self:
        if extra_args is None:
            try:
                sig = signature(filter)
            except Exception:
                if not callable(filter):
                    raise
                extra_args = 0  # pragma: no-cover
            else:
                extra_args = len(sig.parameters) - 1
                if extra_args > 1 or any(
                    p.kind is Parameter.VAR_POSITIONAL for p in sig.parameters.values()
                ):
                    extra_args = max(2, extra_args)
        return super().__new__(cls, filter, extra_args)

    def pro_entries(
        self, it: abc.Iterable["Container"], *args
    ) -> abc.Iterable["Container"]:
        fn, ln = self.vars
        args = args[:ln]
        return tuple(c for c in it if fn(c, *args))


_noop_pred = ProNoopPredicate()


@private_setattr
class PureDep(DependencyMarker, t.Generic[T_Injectable]):
    """Explicitly marks given injectable as a dependency.

    Attributes:
        abstract (T_Injectable): the marked dependency.

    Params:
        abstract (T_Injectable): the dependency to mark.
    """

    __slots__ = ("_ident",)

    _ident: T_Injected

    predicate: ProPredicate = _noop_pred
    default: T_Default = Missing

    has_default: bool = False
    injects_default: bool = False

    def __new__(cls: type[Self], abstract: T_Injectable) -> Self:
        if abstract.__class__ is cls:
            return abstract
        self = _object_new(cls)
        self.__setattr(_ident=abstract)
        return self

    @property
    def abstract(self) -> T_Injectable:
        return self._ident

    @property
    def lookup(self):
        return Lookup(self)

    @property
    def __origin__(self):
        return self.__class__

    def __copy__(self):
        return self

    def __reduce__(self):
        return self.__class__, (self._ident,)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.abstract!s})"

    def __init_subclass__(cls, *args, **kwargs):
        if not cls.__module__.startswith(__package__):  # pragma: no cover
            raise TypeError(f"Cannot subclass {cls.__module__}.{cls.__qualname__}")

    def _as_dict(self):
        return {
            "abstract": self.abstract,
            "predicate": self.predicate,
            "default": self.default,
        }

    def replace(self, **kwds):
        return Dep(*(self._as_dict() | kwds).values())

    def __eq__(self, x) -> bool:
        cls = self.__class__
        if cls is PureDep:
            return self._ident == x
        elif isinstance(x, cls):
            return self._ident == x._ident
        return NotImplemented

    def __ne__(self, x) -> bool:
        cls = self.__class__
        if cls is PureDep:
            return self._ident != x
        elif isinstance(x, cls):
            return self._ident != x._ident
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._ident)

    def __and__(self, x) -> Self:
        if isinstance(x, ProPredicate):
            return self.replace(predicate=self.predicate & x)
        return NotImplemented

    def __rand__(self, x) -> Self:
        if isinstance(x, ProPredicate):
            return self.replace(predicate=x & self.predicate)
        return NotImplemented

    def __or__(self, x) -> Self:
        if isinstance(x, ProPredicate):
            return self.replace(predicate=self.predicate | x)
        return NotImplemented

    def __ror__(self, x) -> Self:
        if isinstance(x, ProPredicate):
            return self.replace(predicate=x | self.predicate)
        return NotImplemented

    def __invert__(self) -> Self:
        return self.replace(predicate=ProInvertPredicate(self.predicate))


_pure_dep_default_set = frozenset(
    [
        (PureDep.predicate, PureDep.default),
    ]
)


@private_setattr
class Dep(PureDep):

    """Marks an injectable as a `dependency` to be injected."""

    __slots__ = "_ash"

    def __new__(
        cls: type[Self],
        abstract: T_Injectable,
        predicate: ProPredicate = ProNoopPredicate(),
        default=Missing,
    ):

        ident = abstract, predicate or _noop_pred, default
        if ident[1:] in _pure_dep_default_set:
            if abstract.__class__ in (cls, PureDep):
                return abstract
            return PureDep(abstract)

        self = _object_new(cls)
        self.__setattr(_ident=ident)
        return self

    @property
    def __origin__(self):
        return self.__class__

    @property
    def abstract(self):
        return self._ident[0]

    @property
    def predicate(self):
        return self._ident[1]

    @property
    def default(self):
        return self._ident[2]

    @property
    def has_default(self):
        return not self.default is Missing

    @property
    def injects_default(self):
        return isinstance(self.default, DependencyMarker)

    def __reduce__(self):
        return self.__class__, self._ident

    def __hash__(self):
        try:
            return self._ash
        except AttributeError:
            self.__setattr(_ash=hash(self._ident))
            return self._ash

    def __repr__(self) -> str:
        abstract, predicate, default = self.abstract, self.predicate, self.default
        return (
            f"{self.__class__.__qualname__}({abstract=}, {predicate=!r}, {default=!r})"
        )


class Lookup(DependencyMarker, BaseLookup):
    """Represents a lazy lookup of a given dependency.

    Attributes:
        __abstract__ (Injectable): the dependency to lookup.

    Params:
        abstract (Injectable): the dependency to lookup.
    """

    __slots__ = ()
    __offset__ = 1

    @t.overload
    def __new__(cls: type[Self], abstract: type[T_Injected]) -> Self:
        ...  # pragma: no cover

    __new__ = BaseLookup.__new__

    @property
    def __abstract__(self) -> type[T_Injected]:
        return self.__expr__[0]

    @property
    def __origin__(self):
        return self.__class__
