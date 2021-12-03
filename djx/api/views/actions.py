from abc import abstractmethod
from collections import ChainMap
from types import FunctionType
import typing as t 
import http

from collections.abc import Mapping, Callable
from djx.common.abc import Representation
from djx.common.collections import MappingProxy, fallbackdict, frozendict

from djx.common.utils import export, text


from ..types import HttpMethod, T_HttpMethods, T_HttpMethodStr, T_HttpMethodName, Route

if t.TYPE_CHECKING:
    from .core import View




_T_View = t.TypeVar('_T_View', bound='View', covariant=True)





@t.overload
def action(methods: t.Union[T_HttpMethods, None]=None, 
        url_path: t.Union[str, t.Pattern, None] = None, 
        url_name: t.Union[str, None] = None,  
        *,
        detail:bool=...,
        outline:bool=...,
        **config) -> Callable[['ViewActionFunction[_T_View]'], 'ViewActionFunction[_T_View]']:
    ...

@export()
def action(methods: t.Union[T_HttpMethods, None]=None, 
        url_path: t.Union[str, t.Pattern, None]=None, 
        url_name=None, 
        **config):

    def decorator(func: ViewActionFunction[_T_View]):
        ActionRouteDescriptor(func, methods, url_path=url_path, url_name=url_name, **config)
        return func

    return decorator






def is_action_func(attr):
    # if isinstance(attr, ViewFunction):
    return not not ActionRouteDescriptor.get_existing_descriptor(attr)



@export()
class ViewFunction(Callable, t.Generic[_T_View]):

    __slots__ = ()

    __name__: str

    @abstractmethod
    def __call__(self: _T_View, *args, **kwds):
        ...

    @classmethod
    def __subclasshook__(cls, sub) -> None:
        if cls is ViewFunction:
            return issubclass(cls, FunctionType)
        return NotImplemented
    




@export()
class ViewActionFunction(ViewFunction[_T_View]):

    __slots__ = ()

    route: 'ActionRouteDescriptor'

    # slug: str
    
    # config: dict[str, t.Any]
    # mapping: 'ActionRouteDescriptor'
    
    # url_path: t.Optional[str]
    # url_name: t.Optional[str]
    # detail: t.Optional[bool]




@export()
class RouteDescriptor(Representation):

    __slots__ = 'detail', 'outline', '_frozen', '__dict__',

    name: str
    action: str
    detail: t.Optional[bool]
    outline: t.Optional[bool]

    __dict__: t.Final[frozendict[str, t.Any]]

    @t.overload
    def __init__(self, 
                action: str, 
                name: t.Optional[str]=None, 
                /, *,
                detail:bool=...,
                outline:bool=...,
                http_methods: HttpMethod=HttpMethod.ALL,
                **config):
        ...

    def __init__(self, 
                action: str, 
                name: t.Optional[str]=None, 
                /,
                detail:t.Optional[bool]=None,
                outline:t.Optional[bool]=None,  
                *,
                http_methods=HttpMethod.ALL,
                **config):
        self.detail = detail
        self.outline = outline
        self.__dict__ = frozendict(
                config, 
                action=action, 
                name=name or action,
                http_methods=HttpMethod(http_methods), 
            )
        self._frozen = True

    def extend(self, 
                detail:t.Optional[bool]=None,
                outline:t.Optional[bool]=None, 
                **config):
        new = self.__class__.__new__(self.__class__)
        new.detail = self.detail if detail is None else detail
        new.outline = self.outline if outline is None else outline
        new.__dict__ = self.__dict__.merge(config)
        new._frozen = True
        return new
        
    def is_detail(self, default=None) -> bool:
        if self.detail is None:
            if self.outline is None:
                return default
            return not self.outline
        return self.detail
        
    def is_outline(self, default=None) -> bool:
        if self.outline is None:
            if self.detail is None:
                return default
            return not self.detail
        return self.outline
    
    def __repr_args__(self):
        fskip = lambda s: s.startswith('_') or s in {'name', 'action'}
        attrs = ((s, getattr(self, s)) for s in self.__dict__ if not fskip(s))
        return [
            ('action', self.action), 
            ('name', self.name), 
            *[(a, v) for a, v in attrs if v is not None][:7],
            (None, ...),
        ][:10]

    def __setattr__(self, name: str, value) -> None:
        if hasattr(self,'_frozen'):
            raise AttributeError(f'cannot set attribute {name!r} on {self.__class__.__name__}')
        super().__setattr__(name, value)



@export()
class ActionRouteDescriptor(RouteDescriptor, t.Generic[_T_View]):

    __slots__ = '_method_descriptors_', 'url_path', 'url_name',

    _descriptor_attr_: t.ClassVar[str] = 'route'
    _method_descriptors_: t.Final[fallbackdict[T_HttpMethodName, RouteDescriptor]]

    @t.overload
    def __init__(self, 
                action: ViewActionFunction[_T_View], 
                methods: T_HttpMethods =(), 
                /, *,
                detail:bool=...,
                outline:bool=...,
                url_path: t.Union[str, t.Pattern, None] = None, 
                url_name: t.Union[str, None] = None, 
                http_methods: HttpMethod=HttpMethod.ALL,
                **config):
        ...

    def __init__(self, 
                action: ViewActionFunction[_T_View], 
                methods: T_HttpMethods =(), 
                /, 
                url_path: t.Union[str, t.Pattern, None] = None, 
                url_name: t.Union[str, None] = None, 
                **config):
        action.__doc__ and config.setdefault('description', action.__doc__)
        self._method_descriptors_ = None
        self.url_path = url_path
        self.url_name = url_name

        super().__init__(action.__name__, action.__name__, **config)

        self.add(methods or self.get_default_http_method(), action)

    @property
    def slug(self):
        return text.slug(text.snake(self.action, sep=' '))

    @property
    def mapping(self) -> Mapping[T_HttpMethodName, RouteDescriptor]:
        return MappingProxy(self._method_descriptors_)
            
    def add(self, 
            methods: T_HttpMethods, 
            func: t.Union[ViewFunction[_T_View], str]=..., /, 
            **config):

        if func is ...:
            def wrapper(fn: ViewFunction[_T_View]) -> ViewFunction[_T_View]:
                nonlocal self, methods, config
                return self.add(methods, fn, **config)
            return wrapper
        
        if isinstance(func, str):
            name = func
        else:
            name = func.__name__

            if old := self.get_existing_descriptor(func):
                raise TypeError(f'{name!r} already bound to {old!r}' )
        
        methods = HttpMethod(methods or 0)

        if name == self.name:
            if self._method_descriptors_ is None:
                object.__setattr__(self, '_method_descriptors_', fallbackdict(None))
            elif name is not func:
                raise TypeError(
                    f"{self.__class__.__name__} does not behave like regular property decorators. "
                    "You cannot use the same method name for each mapping declaration."
                )
            
            if name in HttpMethod.ALL and ~HttpMethod[name] & methods:
                raise TypeError(
                    f'action name {name!r} cannot be used with {~HttpMethod[name] & methods} '
                    f'as it implies the {HttpMethod[name]} method of the root action.'
                )
        elif self.name in HttpMethod.ALL:
            raise TypeError(
                f'Action {self.name!r} cannot be mapped to '
                f'as it implies the {HttpMethod[self.name]} method of the root action.'
            )

        if methods:
            mapping = self._method_descriptors_
            is_detail = self.is_detail()
            is_outline = self.is_outline()

            for m in HttpMethod(methods):
                method = m.name

                assert method not in mapping, (
                    "Method '%s' has already been mapped to '.%s'." % (method, mapping[method]))

                if descriptor := mapping[method]:
                    assert descriptor.name == name, (
                        f'Expected function (`{name}`) to match base attribute name '
                        f'(`{descriptor.name}`). If using a decorator, ensure the inner function is '
                        f'decorated with `functools.wraps`, or that `{name}.__name__` '
                        f'is otherwise set to `{descriptor.name}`.'
                    )
                    mapping[method] = descriptor.extend(action=self.action, **config)    
                else:
                    mapping[method] = descriptor = RouteDescriptor(self.action, name, **config)
                
                assert is_detail or not descriptor.is_detail(), (
                    f'`detail` mode not enabled for {self.action!r}'
                )
                assert is_outline or not descriptor.is_outline(), (
                    f'`outline` mode not enabled for {self.action!r}'
                )
        
        if func is name:
            return
        
        setattr(func, self._descriptor_attr_, self)
        return func

    def extend(self, 
                action: ViewActionFunction[_T_View], 
                methods: T_HttpMethods =(), 
                /, *,
                detail:bool=...,
                outline:bool=...,
                http_methods: HttpMethod=HttpMethod.ALL,
                **config):
        raise NotImplementedError()

    def get(self, func:  ViewFunction[_T_View]= ..., **config) -> ViewFunction[_T_View]:
        return self.add('get', func, **config)

    def post(self, func:  ViewFunction[_T_View]=..., **config) -> ViewFunction[_T_View]:
        return self.add('post', func, **config)

    def put(self, func:  ViewFunction[_T_View]=..., **config) -> ViewFunction[_T_View]:
        return self.add('put', func, **config)

    def patch(self, func: ViewFunction[_T_View] =..., **config) -> ViewFunction[_T_View]:
        return self.add('patch', func, **config)

    def delete(self, func: ViewFunction[_T_View] =..., **config) -> ViewFunction[_T_View]:
        return self.add('delete', func, **config)

    def head(self, func: ViewFunction[_T_View] =..., **config) -> ViewFunction[_T_View]:
        return self.add('head', func, **config)

    def options(self, func: ViewFunction[_T_View] =..., **config) -> ViewFunction[_T_View]:
        return self.add('options', func, **config)

    def trace(self, func: ViewFunction[_T_View] =..., **config) -> ViewFunction[_T_View]:
        return self.add('trace', func, **config)

    def get_config(self, method=None, *, fallback: bool=False, default=...) -> dict[T_HttpMethodStr, str]:
        if method is None:
            return self.config
        elif mm := super().get(method):
            return ChainMap(mm.config, self.config)
        elif fallback:
            return default
        elif default is not ...:
            if fallback:
                return ChainMap(default, self.config)
            return default
        elif fallback:
            return self.config
        raise KeyError(f'Method {method} is not mapped to {self.name!r}')
    
    def get_mapping(self, default: t.Optional[T_HttpMethods]=None) -> dict[T_HttpMethodStr, str]:
        return { m: self.name for m in self or (x.name for x in HttpMethod(default or ())) }

    def get_detail_mapping(self) -> t.Optional[dict[T_HttpMethodStr, str]]:
        if self.is_detail():
            mapping = self._method_descriptors_
            return { m.name: d.name for m in HttpMethod if (d := mapping[m.name]) and d.is_detail(True) }

    def get_outline_mapping(self) -> t.Optional[dict[T_HttpMethodStr, str]]:
        if self.is_outline():
            mapping = self._method_descriptors_
            return { m.name: d.name for m in HttpMethod if (d := mapping[m.name]) and d.is_outline(True) }

    def get_implicit_mapping(self) -> t.Optional[dict[T_HttpMethodStr, str]]:
        if None is self.is_outline(None) is self.is_detail(None):
            mapping = self._method_descriptors_
            return { 
                m.name: d.name 
                for m in HttpMethod 
                if (d := mapping[m.name]) 
                    and None is d.is_outline(None) is d.is_detail(None)
            }

    def detail_route(self):
        if self.is_detail():
            return Route(self.url_path, self.url_name, self.get_detail_mapping(), True)

    def outline_route(self):
        if self.is_outline():
            return Route(self.url_path, self.url_name, self.get_outline_mapping(), False)

    def implicit_route(self):
        if None is self.is_outline(None) is self.is_detail(None):
            return Route(self.url_path, self.url_name, self.get_implicit_mapping(), None)

    def get_default_http_method(self):
        return HttpMethod(self.action) if self.action in HttpMethod.ALL else HttpMethod.GET

    @classmethod
    def get_existing_descriptor(cls, obj, *, attr=None):
        if isinstance(val := getattr(obj, attr or cls._descriptor_attr_, None), RouteDescriptor):
            return val
    



# @export()
# class ActionDescriptor(t.Generic[_T_Co]):

#     # __slots__ = 'func', 'conf',

#     func: t.Union[t.Callable[..., _T_Co], None]
#     conf: frozendict[str, t.Any]

#     mapping: MethodMapper


#     def __init__(self, 
#                 methods: T_HttpMethods=..., 
#                 url_path: t.Union[str, t.Pattern, None]=..., 
#                 url_name: t.Union[str, None] = None, *,
#                 detail: bool, 
#                 **config):

#         self.mapping = 
#         self.func = func
#         self.conf = frozendict(conf, **config)

#     # def replace(self, conf: dict[str, t.Any] = frozendict(), /, **config):
#     #     return self.__class__(self.func, self.conf.merge(conf, **config))
        
#     def __set_name__(self, owner, name):
#         vardump(__set_name__=name, __owner__=owner)        
#         if not isinstance(owner, ViewType):
#             raise RuntimeError(f'{self.__class__.__name__} can only be added to ViewTypes not {owner}')

#     def __call__(self, func: t.Callable[..., _T_Co]) -> t.Callable[..., _T_Co]:

#         return self.__class__(func, self.conf)
        

