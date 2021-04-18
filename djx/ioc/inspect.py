
import inspect as ins
from functools import partial

from cachetools.func import lru_cache
from weakref import WeakSet
from typing import (
    Any, Callable, ClassVar, ForwardRef, 
    Generic, Literal, Optional, Type, TypeVar, 
    TYPE_CHECKING,
    Union, get_args, get_origin
)
from collections.abc import Iterator, Mapping

from flex.utils.decorators import export
from flex.utils.proxy import Proxy, ValueProxy


from .abc import Injector


_empty = ins.Parameter.empty


_expand_generics = {Union, Literal, type, Type}







@export()
class Depends(type):

    __depends__: Union[list, Any]

    def __class_getitem__(cls, parameters):
        if not isinstance(parameters, tuple):
            parameters = (parameters,)
        
        typ, *deps = parameters
        deps = [*deps] if len(deps) > 1 else deps[0] if deps else typ if isinstance(typ, type) else None

        return Union[cls('Depends', (), dict(__depends__=deps)), typ]

    def __repr__(cls) -> str:
        return f'Depends({cls.__depends__!r})'

    def __str__(cls) -> str:
        return f'Depends({cls.__depends__})'




def annotated_deps(obj) -> Union[list, Any]:
    if is_injectable(obj):
        return obj
    elif isinstance(obj, Depends):
        return obj.__depends__
    elif get_origin(obj) in _expand_generics:
        for d in get_args(obj):
            if rv := annotated_deps(d):
                return rv
        



@export()
def is_injectable(obj) -> bool:
    from .providers import is_provided
    return is_provided(obj)




@export()
@lru_cache(2**20)
def signature(callable: Callable[..., Any], *, follow_wrapped=True) -> 'InjectableSignature':
    return InjectableSignature.from_callable(callable, follow_wrapped=follow_wrapped)






@export()
class Parameter(ins.Parameter):
    
    __slots__ = ('_depends',)
    
    def __init__(self, name, kind, *, default=_empty, annotation=_empty):
        
        super().__init__(name, kind, default=default, annotation=annotation)

        self._depends = annotated_deps(self._annotation)

    @property
    def default(self):
        return self._default

    # @property
    # def is_dependency(self):
    #     return bool(self._depends)

    @property
    def depends(self):
        return self._depends

    def __repr__(self):
        deps = f', <Depends: {self.depends}>' if self.depends else ''
        return f'<{self.__class__.__name__} {self}{deps}>'





@export()
class BoundArguments(ins.BoundArguments):
    
    __slots__ = ()

    _signature: 'InjectableSignature'

    def apply_injected(self, injector: Injector, *, set_defaults: bool = False) -> None:
        """Set the values for injectable arguments.

        This should be called before apply_defaults
        """
        arguments = self.arguments
        new_arguments = []
        for name, param in self._signature.parameters.items():
            try:
                new_arguments.append((name, arguments[name]))
            except KeyError:

                if param.depends:
                    try:
                        new_arguments.append((name, injector[param.depends]))
                    except KeyError:
                        pass
                    else:
                        continue

                if set_defaults:
                    if param.default is not _empty:
                        val = param.default
                    elif param.kind is Parameter.VAR_POSITIONAL:
                        val = ()
                    elif param.kind is Parameter.VAR_KEYWORD:
                        val = {}
                    else:
                        # This BoundArguments was likely produced by
                        # Signature.bind_partial().
                        continue
                    new_arguments.append((name, val))
                            
        self.arguments = dict(new_arguments)






@export()
class InjectableSignature(ins.Signature):
    __slots__ = ()

    _parameter_cls: ClassVar[type[Parameter]] = Parameter
    _bound_arguments_cls: ClassVar[type[BoundArguments]] = BoundArguments

    parameters: Mapping[str, Parameter]

    def inject(self, _injector: Injector, *args: Any, **kwargs: Any) -> BoundArguments:
        rv = self.bind_partial(*args, **kwargs)
        rv.apply_injected(_injector)
        return rv


    if TYPE_CHECKING:
        def bind(self, *args: Any, **kwargs: Any) -> BoundArguments:
            return super().bind(*args, **kwargs)

        def bind_partial(self, *args: Any, **kwargs: Any) -> BoundArguments:
            return super().bind_partial(*args, **kwargs)
        
        

