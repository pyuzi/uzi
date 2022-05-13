import attr


class UziException(Exception):
    """Base class for all internal exceptions."""


@attr.s()
class FinalProviderOverrideError(TypeError, UziException):
    """Raised when a final provider has an override."""

    abstract: "Injectable" = attr.ib(default=None)
    final: "Provider" = attr.ib(default=None)
    overrides: tuple["Provider"] = attr.ib(default=(), converter=tuple)


class InvalidStateError(UziException):
    """The operation is not allowed in this state."""


@attr.s()
class InjectorLookupError(KeyError, UziException):
    """Raised by ~Injector` when a missing dependency is requested.

    Args:
        abstract (Injectable): the missing dependency
    """

    abstract: "Injectable" = attr.ib(default=None)
    scope: "Graph" = attr.ib(default=None)


class ProError(TypeError, UziException):
    """Raised when there is an issue with provider resolution order (`pro`)
    consistency
    """


from .providers import Provider
from .markers import Injectable
from .graph.core import Graph
