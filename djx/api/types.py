from abc import abstractmethod
from functools import cache, reduce
import typing as t 

from collections.abc import Set, Iterable, Callable
from djx.common.enum import Enum, StrEnum, auto, IntFlag, Flag

from djx.common.utils import export, cached_class_property


if t.TYPE_CHECKING:
    from .views import View


T_HttpMethodNameLower = t.Literal['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']
T_HttpMethodStr = t.Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE']

T_HttpMethodName = t.Literal[T_HttpMethodNameLower, T_HttpMethodStr]


T_HttpMethods = t.Union[T_HttpMethodName, 'HttpMethod', Iterable[t.Union[T_HttpMethodName, 'HttpMethod']]]




_T_View = t.TypeVar('_T_View', bound='View', covariant=True)


@export()
class HttpMethod(Flag):

    # ANY: 'HttpMethod'       = auto()

    name: T_HttpMethodStr

    OPTIONS:  'HttpMethod'  = auto() #1 << 1
    HEAD:  'HttpMethod'     = auto() 
    GET:  'HttpMethod'      = auto()
    POST:  'HttpMethod'     = auto()
    PUT:  'HttpMethod'      = auto() 
    PATCH:  'HttpMethod'    = auto() 
    DELETE:  'HttpMethod'   = auto()
    TRACE:  'HttpMethod'    = auto()
    
    options:  'HttpMethod'  = OPTIONS
    head:  'HttpMethod'     = HEAD 
    get:  'HttpMethod'      = GET 
    post:  'HttpMethod'     = POST
    put:  'HttpMethod'      = PUT 
    patch:  'HttpMethod'    = PATCH 
    delete:  'HttpMethod'   = DELETE
    trace:  'HttpMethod'    = TRACE

    @cached_class_property
    def ALL(cls) -> 'HttpMethod':
        return ~cls.TRACE | cls.TRACE
    
    @cached_class_property
    def NONE(cls) -> 'HttpMethod':
        return cls(0)
    
    @classmethod
    def _missing_(cls, val):
        tp = val.__class__
        if tp is int:
            return super()._missing_(val)
        elif tp is str:
            mem = cls._member_map_.get(val)
            if mem is None:
                raise ValueError(f"{val!r} is not a valid {cls.__qualname__}")
            return mem
        elif issubclass(tp, set):
            if val:
                return reduce(lambda a, b: a|cls(b), val, cls.NONE)
            return cls.NONE
        
        return super()._missing_(val)
    
    @property
    @cache
    def methods(self) -> tuple['HttpMethod', ...]:
        return *(m for m in self.__class__ if m in self),

    def __contains__(self, x) -> bool:
        if x.__class__ is str:
            return x in self.__class__._member_map_
        return super().__contains__(x)
    
    def __iter__(self):
        yield from self.methods



# vardump([*HttpMethod], HttpMethod['get'] == 'GET', ~HttpMethod('GET'), ~HttpMethod.GET & HttpMethod.POST)

# vardump(GET=HttpMethod.GET, GET_INV=~HttpMethod.GET, ANY=~HttpMethod.GET & HttpMethod.DELETE, GET_EQ=HttpMethod['get'] == 'GET')

# print('-'*80)
# print('',
#     f'{HttpMethod({"get", "POST", "PUT"})=!r}', 
#     f'{HttpMethod.GET in HttpMethod.HEAD=!r}', 
#     f'{HttpMethod.HEAD in HttpMethod.GET=!r}', 
#     sep='\n  ', end='\n\n'
# )

# print('-'*80)



class ViewMethod(Callable, t.Generic[_T_View]):

    __slots__ = ()

    __name__: str

    @abstractmethod
    def __call__(self: _T_View, *args, **kwds):
        ...

    @classmethod
    def __subclasshook__(cls, sub) -> None:
        if cls is ViewMethod:
            return issubclass(cls, Callable)
        return NotImplemented
    



class ActionMethod(ViewMethod[_T_View]):

    __slots__ = ()

    slug: str
    config: dict[str, t.Any]
    mapping: 'MethodMapper'
    
    url_path: t.Optional[str]
    url_name: t.Optional[str]
    detail: t.Optional[bool]




class MethodMapper(dict[T_HttpMethodStr, ViewMethod[_T_View]]):
    """
    Enables mapping HTTP methods to different ViewSet methods for a single,
    logical action.

    Example usage:

        class MyViewSet(ViewSet):

            @action(detail=False)
            def example(self, request, **kwargs):
                ...

            @example.mapping.post
            def create_example(self, request, **kwargs):
                ...
    """

    __slots__ = 'action', 

    action: ActionMethod[_T_View]

    def __init__(self, action: ActionMethod[_T_View], methods: Iterable[t.Union[T_HttpMethodName, HttpMethod]]):
        self.action = action
        for method in methods and HttpMethod(methods if methods.__class__ is str else set(methods)) or ():
            self[method.name] = self.action.__name__

    def map(self, methods: t.Union[T_HttpMethodName, HttpMethod], func: ViewMethod[_T_View]) -> ViewMethod[_T_View]:
        for m in HttpMethod(methods if methods in HttpMethod.ALL else set(methods)):
            name = m.name
            assert name not in self, (
                "Method '%s' has already been mapped to '.%s'." % (name, self[name]))
            assert func.__name__ != self.action.__name__, (
                "Method mapping does not behave like the property decorator. You "
                "cannot use the same method name for each mapping declaration.")

            self[name] = func.__name__

            return func

    def get(self, func: ViewMethod[_T_View]) -> ViewMethod[_T_View]:
        return self.map('get', func)

    def post(self, func: ViewMethod[_T_View]) -> ViewMethod[_T_View]:
        return self.map('post', func)

    def put(self, func: ViewMethod[_T_View]) -> ViewMethod[_T_View]:
        return self.map('put', func)

    def patch(self, func: ViewMethod[_T_View]) -> ViewMethod[_T_View]:
        return self.map('patch', func)

    def delete(self, func: ViewMethod[_T_View]) -> ViewMethod[_T_View]:
        return self.map('delete', func)

    def head(self, func: ViewMethod[_T_View]) -> ViewMethod[_T_View]:
        return self.map('head', func)

    def options(self, func: ViewMethod[_T_View]) -> ViewMethod[_T_View]:
        return self.map('options', func)

    def trace(self, func: ViewMethod[_T_View]) -> ViewMethod[_T_View]:
        return self.map('trace', func)
