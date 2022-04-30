

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
    scope: "Scope" = attr.ib(default=None)




class ProIndexError(IndexError, XdiException):
    """Raised 
    """


class ProValueError(ValueError, XdiException):
    ...




from .providers import Provider
from .core import Injectable
from .scopes import Scope