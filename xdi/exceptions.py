

import attr


class XdiException(Exception):
    """Base class for all internal exceptions."""




@attr.s()
class FinalProviderOverrideError(TypeError, XdiException):
    """Raised when a final provider has an override.
    """
    
    abstract: 'Injectable' = attr.ib(default=None)
    final: 'Provider' = attr.ib(default=None)
    overrides: tuple['Provider' ]= attr.ib(default=(), converter=tuple)



@attr.s()
class InjectorLookupError(KeyError, XdiException):
    """Raised by ~Injector` when a missing dependency is requested.
    
    Args:
        abstract (Injectable): the missing dependency
    """

    abstract: "Injectable" = attr.ib(default=None)
    scope: "DepGraph" = attr.ib(default=None)





class ProError(TypeError, XdiException):
    """Raised when there is an issue with provider resolution order (`pro`) 
        consistency
    """




class InjectorError(TypeError, XdiException):
    """Raise by `Scope`s"""




from .providers import Provider
from .markers import Injectable
from .graph import DepGraph