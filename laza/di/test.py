import typing as t





from .containers import Container, InjectorContainer
from .injectors import Injector
from .ctx import InjectorContext
from .providers.util import BindingsMap



class TestContainer(Container):
    ...



class TestInjectorContainer(InjectorContainer):
    ...



class TestInjectorContext(InjectorContext):

    __setitem__ = dict.__setitem__
    __delitem__ = dict.__delitem__
    setdefault = dict.setdefault
    update = dict.update
    pop = dict.pop
    


class TestBindingsMap(BindingsMap):

    __setitem__ = dict.__setitem__
    __delitem__ = dict.__delitem__
    setdefault = dict.setdefault
    update = dict.update
    pop = dict.pop
    



class TestInjector(Injector):
    
    _bindings_class = TestBindingsMap
    _container_class = TestInjectorContainer
    _context_class = TestInjectorContext



    


