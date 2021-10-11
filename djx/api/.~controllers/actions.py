from functools import partial
import typing as t 


from types import GenericAlias, MethodDescriptorType, MethodType
from djx.common.imports import ImportRef
from djx.common.intervals import Bound
from djx.common.proxy import proxy

from djx.common.utils import export, cached_property
from djx.di import inspect, di


_T = t.TypeVar('_T')


_T_Func = t.Callable[[t.Any], _T]


from djx.schemas.decorator import ValidatedFunction

if t.TYPE_CHECKING:
    from djx.schemas.decorator import ConfigType
    from ..core import Controller
else:
    Controller = proxy(ImportRef(f'{__package__}.core', 'Controller'), cache=True)




@export()
class Action(t.Generic[_T]):

    _signature: inspect.Signature
    # func: _T_Func

    def __init__(self, 
                func: t.Callable[[t.Any], _T], 
                name: str = None,
                config: 'ConfigType'=None,
                doc: str=None,
            ):
        
        self.func = func
        self.__name__ = name or func.__name__
        self._config = config
        self.__doc__ = doc or func.__doc__
    
    @property
    def validated(self):
        try:
            return self._validated
        except AttributeError:
            self._validated = ValidatedFunction(self, self._config)
            return self._validated

    @cached_property
    def __signature__(self):
        return inspect.signature(self.func)

    def __set_name__(self, owner, name):
        self.__name__ = name

    def __get__(self, obj, typ=None) -> None:
        if obj is None:
            return self

        if typ is None:
            typ = obj.__class__

        debug(typ, obj)
        alias = BoundAction[self, typ]

        try:
            return obj.__dict__[alias]
        except KeyError:
            obj.__dict__[alias] = MethodType(di.make(alias, typ, self), obj)
            return obj.__dict__[alias]
    
    def __call__(_self, self, /, *args: t.Any, **kwds: t.Any) -> t.Any:
        return _self.__get__(self)(*args, **kwds)

    def as_view(self, ctrl, **kwds):

        def view(req, *args, **kwds):
            pass




@export()
# @di.wrap(cache=True)
# @di.injectable(cache=True, )
class BoundAction:

    __slots__ = 'action', 'ctrlcls', '__call__'

    __class_getitem__ = classmethod(GenericAlias)
    
    # __bound = dict

    # def __class_getitem__(cls, params):
    #     if not isinstance(params, tuple):
    #         params,
        
    #     # klass = cls.__bound[params]
    #     cache = cls.__bound
    #     if params[] not in cls.__

    #     # di.wrap()


    def __init__(_self, cls: type[Controller], action: Action):
        _self.action = action
        _self.ctrlcls = cls 

        def __call__(self, /, *a, **kw):
            pass
                    

        _self.__call__ = __call__

    def __getattr__(self, name) -> None:
        if name not in {'action', 'ctrlcls'}:
            return getattr(self.action, name)
        raise AttributeError(name) 
    

    def run(_self, self, *args, **kwargs):
        pass

    def as_view(self, **kwds):
        pass




class Foo:

    def act(self):
        """This was added"""
        pass
    act.v = 'good'
    act = Action(act)


    @classmethod
    def fun(cls, arg) -> None:
        pass
    
    

# foo = Foo()

# debug(Foo.act, Foo.fun)
# debug(foo.act.__doc__, foo.fun)

