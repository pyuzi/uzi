
import inspect as ins
from functools import partial

from cachetools import LFUCache, cached
from weakref import WeakSet
from typing import (
    Any, Callable, ClassVar, ForwardRef, 
    Generic, Literal, Optional, TypeVar, 
    _GenericAlias,
    Union, get_args, get_origin
)
from collections.abc import Iterator

from flex.utils.decorators import export

from .interfaces import Injector
from .symbols import Symbol

_empty = ins.Parameter.empty

_INJECTABLE_MARKER = '__injectable__'


def isinjectable(obj) -> bool:
    if callable(obj) or isinstance(obj, (Symbol,)):
        return True
    return False


is_symbol: Callable[..., bool] = partial(isinstance, type=Symbol)


_expand_generics = {Union, Literal, type, ForwardRef,  Optional[Any]}


_depends_set = WeakSet()

def Depends(tp: Any, *deps):
    bases = (tp,) if isinstance(tp, type) else ()
    _depends_set.add(rv := type(f'Depended{bases and tp.__name__.title() or "Type"}', bases, dict(__dependencies__=tuple(deps))))
    return rv




def injectable_args(obj) -> Iterator[Any]:
    if isinjectable(obj):
        yield obj
    elif obj in _depends_set:
        for d in obj.__dependencies__:
            yield from injectable_args(d)
    elif get_origin(obj) in _expand_generics:
        for d in get_args(obj):
            yield from injectable_args(d)
        


@export()
def is_symbol(obj) -> bool:
    return isinstance(obj, Symbol)


@export()
def isinjectable(obj) -> bool:
    return hasattr(obj, _INJECTABLE_MARKER) or isinstance(obj, Symbol)



@export()
@cached(LFUCache(2**16)) 
def signature(callable: Callable[..., Any], *, follow_wrapped=True) -> 'InjectableSignature':
    return InjectableSignature.from_callable(callable, follow_wrapped=follow_wrapped)


from pydantic import BaseModel, constr
_D = TypeVar('_D', bound=Callable[..., Any])


_depends = {}


@export()
class Depend(type):

    __injectable__ = True
    __dependencies__: ClassVar[tuple]

    __slots__ = ('_dependencies', '_default')

    def __getitem__(cls, params) -> None:
        if not isinstance(params, tuple):
            params = (params,)
        tp, *deps = params
        return _GenericAlias()
        type('DependedType', (tp, cls), dict(__dependencies__=tuple(deps)))

    def __init__(self, deps: Optional[Union[_D,tuple[_D], list[_D]]] = None, /, default=_empty):
        if isinstance(deps, (list, tuple)):
            self._dependencies = tuple(d for d in deps if d)
        else:
            self._dependencies = (deps,) if deps else ()

        self._default = default

    @property
    def default(self) -> Any:
        return self._default

    @property
    def dependencies(self) -> Iterator[_D]:
        for d in self._dependencies:
            yield from injectable_args(d)




@export()
class InjectableParameter(ins.Parameter):
    
    __slots__ = ('_dependencies',)
    
    def __init__(self, name, kind, *, default=_empty, annotation=_empty):

        super().__init__(name, kind, default=default, annotation=annotation)

        self._dependencies = tuple(injectable_args(self._annotation))

    @property
    def default(self):
        return self._default

    @property
    def dependencies(self):
        return self._dependencies

    def __repr__(self):
        return f'<{self.__class__.__name__} "{self}"  deps={{ {", ".join(str(d) for d in self.dependencies)} }}>'





@export()
class InjectableBoundArguments(ins.BoundArguments):
    __slots__ = ()
    
    def apply_dependencies(self, injector: Injector) -> None:
        pass

    

@export()
class InjectableSignature(ins.Signature):
    __slots__ = ()

    _parameter_cls: ClassVar[type[InjectableParameter]] = InjectableParameter
    _bound_arguments_cls: ClassVar[type[InjectableBoundArguments]] = InjectableBoundArguments


