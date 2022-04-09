import typing as t

import attr

from xdi import DependencyLocation


from ._dependency import SimpleDependency, Dependency



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
            self._resolved[key][self.container, DependencyLocation.GLOBAL] = key = SimpleDependency(self, key, use=val)
        self._dependencies[key] = key
