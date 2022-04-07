import typing as t

import attr

from xdi import Dependency






from .containers import Container
from .injectors import Injector
from .scopes import Scope



class TestContainer(Container):
    ...



class TestInjectorContext(Injector):

    __setitem__ = dict.__setitem__
    __delitem__ = dict.__delitem__
    setdefault = dict.setdefault
    update = dict.update
    pop = dict.pop
    



class TestScope(Scope):

    def __setitem__(self, key, val):
        if not isinstance(key, Dependency):
            key = Dependency(key, self)
        self._resolver_map[key] = val
