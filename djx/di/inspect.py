
import inspect as ins
import typing as t 


from collections.abc import Mapping, Callable

from djx.common.utils import export
from djx.common.typing import get_origin, get_args, eval_type
from djx.common.imports import ImportRef

from .abc import Injector


_empty = ins.Parameter.empty


_expand_generics = {t.Annotated}



_VAR_KEYWORD = ins.Parameter.VAR_KEYWORD
_VAR_POSITIONAL = ins.Parameter.VAR_POSITIONAL
_POSITIONAL_OR_KEYWORD = ins.Parameter.POSITIONAL_OR_KEYWORD

_KEYWORD_ONLY = ins.Parameter.KEYWORD_ONLY




# @export()
# class Depends(type):

#     __depends__: t.Union[list, t.Any]

#     def __class_getitem__(cls, parameters):
#         if not isinstance(parameters, tuple):
#             parameters = (parameters,)
        
#         typ, *deps = parameters
#         deps = [*deps] if len(deps) > 1 else deps[0] if deps else typ if isinstance(typ, type) else None

#         return t.Union[cls('Depends', (), dict(__depends__=deps)), typ]

#     def __repr__(cls) -> str:
#         return f'Depends({cls.__depends__!r})'

#     def __str__(cls) -> str:
#         return f'Depends({cls.__depends__})'



__last_id: int = 0

@export()
def ordered_id():
    global __last_id
    __last_id += 1
    return __last_id


__builtin_values = None

def builtin_values():
    global __builtin_values

    if __builtin_values is None:
        __builtin_values = frozenset(__builtins__.values())

    return __builtin_values

# ins.isbuiltin()

def annotated_deps(obj) -> t.Union[list, t.Any]:
    from .providers import DependencyAnnotation
    from .container import ioc

    if obj in ioc:
        return obj
    elif isinstance(obj, DependencyAnnotation):
        return obj.deps[0]
    elif (orig := get_origin(obj)) in ioc:
        return obj
    elif orig in _expand_generics:
        for d in get_args(obj):
            if rv := annotated_deps(d):
                return rv
        







@export()
def signature(callable: Callable[..., t.Any], *, follow_wrapped=True, evaltypes=True) -> 'InjectableSignature':
    sig = InjectableSignature.from_callable(callable, follow_wrapped=follow_wrapped)

    if not isinstance(sig, InjectableSignature):
        sig = InjectableSignature(sig.parameters.values(), sig.return_annotation)

    if evaltypes:
        if follow_wrapped:
            callable = ins.unwrap(callable, stop=(lambda f: hasattr(f, "__signature__")))
        
        gns = getattr(callable, '__globals__', None) \
            or getattr(ImportRef(callable).module(None), '__dict__', None)

        return sig.evaluate_annotations(gns)
        
    return sig



@export()
class Parameter(ins.Parameter):
    
    __slots__ = ('_dependency', '_type',)
    
    def __init__(self, name, kind, *, default=_empty, annotation=_empty):
        super().__init__(name, kind, default=default, annotation=annotation)
        self._dependency = annotated_deps(self._annotation) or None

    # @property
    # def is_dependency(self):
    #     return bool(self._depends)

    @property
    def dependency(self):
        return self._dependency

    @property
    def is_dependency(self):
        return self._dependency is not None

    def __repr__(self):
        deps = f', <Depends: {self.dependency}>' if self.dependency else ''
        return f'<{self.__class__.__name__} {self}{deps}>'

    def __reduce__(self):
        return (type(self),
                (self._name, self._kind),
                {'_default': self._default,
                 '_annotation': self._annotation})
    
    def __setstate__(self, state):
        self._default = state['_default']
        self._annotation = state['_annotation']


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

                if param.dependency:
                    try:
                        new_arguments.append((name, injector[param.dependency]))
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


    def inject_args(self, inj: Injector, values: dict = None):
        deps = bool(self._signature.positional_dependencies)

        if deps and values and self.arguments:
            for param_name, param in self._signature.positional_parameters.items():
                if param_name in values:
                    arg = values[param_name]
                elif param_name in self.arguments:
                    arg = self.arguments[param_name]
                elif param.dependency is not None:
                    try:
                        arg = inj.make(param.dependency)
                    except KeyError:
                        break
                else:
                    break
            
                if param.kind == _VAR_POSITIONAL:
                    yield from arg # *args
                else:
                    yield arg # plain positional argument

        elif deps and values and not self.arguments:

            for param_name, param in self._signature.positional_parameters.items():
                if param_name in values:
                    arg = values[param_name]
                elif param.dependency is not None:
                    try:
                        arg = inj.make(param.dependency)
                    except KeyError:
                        break
                else:
                    break
            
                if param.kind == _VAR_POSITIONAL:
                    yield from arg # *args
                else:
                    yield arg # plain positional argument

        elif deps and not values and self.arguments:

            for param_name, param in self._signature.positional_parameters.items():
                if param_name in self.arguments:
                    arg = self.arguments[param_name]
                elif param.dependency is not None:
                    try:
                        arg = inj.make(param.dependency)
                    except KeyError:
                        break
                else:
                    break
            
                if param.kind == _VAR_POSITIONAL:
                    yield from arg # *args
                else:
                    yield arg # plain positional argument

        elif deps and not values and not self.arguments:

            for param_name, param in self._signature.positional_parameters.items():
                if param.dependency is not None:
                    try:
                        arg = inj.make(param.dependency)
                    except KeyError:
                        break
                else:
                    break
            
                if param.kind == _VAR_POSITIONAL:
                    yield from arg # *args
                else:
                    yield arg # plain positional argument

        elif not deps and not values and self.arguments:
            for param_name, param in self._signature.positional_parameters.items():
                if param_name in self.arguments:
                    arg = self.arguments[param_name]
                else:
                    break
            
                if param.kind == _VAR_POSITIONAL:
                    yield from arg # *args
                else:
                    yield arg # plain positional argument


    
    def inject_kwargs(self, inj: Injector, values: dict=None):
        kwargs = dict()
        deps = bool(self._signature.keyword_dependencies)
        
        if deps and self.arguments and values:
            for param_name, param in self._signature.keyword_parameters.items():
                if param_name in values:
                    arg = values[param_name]
                elif param_name in self.arguments:
                    arg = self.arguments[param_name]
                elif param.dependency is not None:
                    try:
                        arg = inj.make(param.dependency)
                    except KeyError:
                        continue    
                else:
                    continue
                
                if param.kind == _VAR_KEYWORD:
                    kwargs.update(arg) # **kwargs
                else:
                    kwargs[param_name] = arg # plain keyword argument

        elif deps and not self.arguments and values:
            for param_name, param in self._signature.keyword_parameters.items():
                if param_name in values:
                    arg = values[param_name]
                elif param.dependency is not None:
                    try:
                        arg = inj.make(param.dependency)
                    except KeyError:
                        continue    
                else:
                    continue
                
                if param.kind == _VAR_KEYWORD:
                    kwargs.update(arg) # **kwargs
                else:
                    kwargs[param_name] = arg # plain keyword argument

        elif deps and self.arguments and not values:
            for param_name, param in self._signature.keyword_parameters.items():
                if param_name in self.arguments:
                    arg = self.arguments[param_name]
                elif param.dependency is not None:
                    try:
                        arg = inj.make(param.dependency)
                    except KeyError:
                        continue    
                else:
                    continue
                
                if param.kind == _VAR_KEYWORD:
                    kwargs.update(arg) # **kwargs
                else:
                    kwargs[param_name] = arg # plain keyword argument

        elif deps and not self.arguments and not values:
            for param_name, param in self._signature.keyword_parameters.items():
                if param.dependency is not None:
                    try:
                        arg = inj.make(param.dependency)
                    except KeyError:
                        continue    
                else:
                    continue
                
                if param.kind == _VAR_KEYWORD:
                    kwargs.update(arg) # **kwargs
                else:
                    kwargs[param_name] = arg # plain keyword argument

        elif not deps and self.arguments and values:
            for param_name, param in self._signature.keyword_parameters.items():
                if param_name in values:
                    arg = values[param_name]
                elif param_name in self.arguments:
                    arg = self.arguments[param_name]
                else:
                    continue
                
                if param.kind == _VAR_KEYWORD:
                    kwargs.update(arg) # **kwargs
                else:
                    kwargs[param_name] = arg # plain keyword argument

        elif not deps and self.arguments and not values:
            for param_name, param in self._signature.keyword_parameters.items():
                if param_name in self.arguments:
                    arg = self.arguments[param_name]
                else:
                    continue
                
                if param.kind == _VAR_KEYWORD:
                    kwargs.update(arg) # **kwargs
                else:
                    kwargs[param_name] = arg # plain keyword argument

        elif not deps and not self.arguments and values:
            for param_name, param in self._signature.keyword_parameters.items():
                if param_name in values:
                    arg = values[param_name]
                else:
                    continue
                
                if param.kind == _VAR_KEYWORD:
                    kwargs.update(arg) # **kwargs
                else:
                    kwargs[param_name] = arg # plain keyword argument

        return kwargs
    
    def copy(self):
        return self.__class__(self._signature, self.arguments.copy())

    __copy__ = copy

    def __bool__(self):
        return bool(self._signature.parameters)




@export()
class InjectableSignature(ins.Signature):
    __slots__ = ('_pos_params', '_pos_deps', '_kw_params', '_kw_deps', '_bound')

    _parameter_cls: t.ClassVar[type[Parameter]] = Parameter
    _bound_arguments_cls: t.ClassVar[type[BoundArguments]] = BoundArguments
    _bound: BoundArguments

    parameters: Mapping[str, Parameter]

    @property
    def positional_parameters(self):
        try:
            return self._pos_params
        except AttributeError:
            self._pos_params = { n : p 
                    for n,p in self.parameters.items() 
                        if p.kind not in (_VAR_KEYWORD, _KEYWORD_ONLY)
                }
            return self._pos_params

    @property
    def positional_dependencies(self):
        try:
            return self._pos_deps
        except AttributeError:
            self._pos_deps = { n : p 
                    for n,p in self.positional_parameters.items() 
                        if p.is_dependency
                }
            return self._pos_deps

    @property
    def keyword_parameters(self):
        try:
            return self._kw_params
        except AttributeError:
            self._kw_params = { n : p 
                    for n,p in self.parameters.items() 
                        if p.kind in (_VAR_KEYWORD, _KEYWORD_ONLY)
                }
            return self._kw_params

    @property
    def keyword_dependencies(self):
        try:
            return self._kw_deps
        except AttributeError:
            self._kw_deps = { n : p 
                    for n,p in self.keyword_parameters.items() 
                        if p.is_dependency
                }
            return self._kw_deps

    def evaluate_annotations(self, globalns, localns=None):
        eval = lambda an: eval_type(an, globalns, localns)
        params = (
                p.replace(annotation=eval(p.annotation)) 
                    for p in self.parameters.values()
            )
        
        return self.replace(
                parameters=params, 
                return_annotation=eval(self.return_annotation)
            )


    def inject(self, _injector: Injector, *args: t.Any, **kwargs: t.Any) -> BoundArguments:
        rv = self.bind_partial(*args, **kwargs)
        rv.apply_injected(_injector)
        return rv

    def bound(self) -> BoundArguments:
        try:
            return self._bound.copy()
        except AttributeError:
            self._bound = super().bind_partial()
            return self._bound.copy()

    def bind(self, *args: t.Any, **kwargs: t.Any) -> BoundArguments:
        if not args and not kwargs:
            return self.bound()
        return super().bind(*args, **kwargs)

    def bind_partial(self, *args: t.Any, **kwargs: t.Any) -> BoundArguments:
        if not args and not kwargs:
            return self.bound()
        return super().bind_partial(*args, **kwargs)
        
        


if t.TYPE_CHECKING:
    class Signature(InjectableSignature):
        __slots__ = ()

else:
    Signature = InjectableSignature


