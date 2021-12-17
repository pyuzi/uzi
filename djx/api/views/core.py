
from abc import abstractmethod
from inspect import getmembers
import io
from types import MethodType
import typing as t
import logging

from functools import partial, update_wrapper
from collections.abc import Hashable, Iterable, Mapping, Callable, Sequence, Collection
from django.core.exceptions import BadRequest
from django.http.response import HttpResponseBase, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from djx.api.abc import Headers
from djx.common.tests import data

from djx.di.common import Depends, InjectionToken
from djx.di.container import IocContainer
from djx.di.scopes import REQUEST_SCOPE

from ..abc import BodyParser, Args, Body, Kwargs
from djx.common.collections import frozendict

from djx.common.utils import export, lookup_property, text
from djx.schemas import QueryLookupSchema, OrmSchema, Schema, parse_obj_as
from djx.schemas.tools import _get_parsing_type

from ..response import Response





from ..  import exc, Request
from .config import ViewConfig, ActionConfig
from ..types import ContentShape, HttpStatus

from .actions import ActionRouteDescriptor, is_action_func, action

logger = logging.getLogger(__name__)

_T_Co = t.TypeVar('_T_Co', covariant=True)

_T_Schema = t.TypeVar('_T_Schema', bound=Schema)

_T_Resource = t.TypeVar('_T_Resource', bound='Resource', covariant=True)
_T_View = t.TypeVar('_T_View', bound='View', covariant=True)
_T_Entity = t.TypeVar('_T_Entity', covariant=True)
_T_Data = t.TypeVar('_T_Data', covariant=True)
_T_Payload = t.TypeVar('_T_Payload', covariant=True)

_T_Key = t.TypeVar('_T_Key', str, int, t.SupportsInt, Hashable)


_config_lookup = partial(lookup_property, source='config', read_only=True)




_T_ActionResolveFunc = Callable[['View', Request], ActionConfig]
_T_ActionResolver = Callable[[ViewConfig, Mapping[_T_Co, ActionConfig]], _T_ActionResolveFunc]


@export()
class ViewType(type):

    __config_instance__: t.Final[ViewConfig]
    __local_actions__: t.Final[dict[str, dict[str, t.Any]]] = ...

    def __new__(mcls, name: str, bases: tuple[type], dct: dict, **kwds):
        attrs = dct

        attrs['__config_instance__'] = attrs['config'] = None
    
        if 'Config' not in attrs:
            attrs['Config'] = type('Config', (), kwds)
        elif kwds:
            raise TypeError('cannot use both config keywords and Config at the same time')
        

        cls = super().__new__(mcls, name, bases, attrs)
        if any(isinstance(b, ViewType) for b in bases):
            pass
        
        return cls

    @property
    def __config__(self) -> ViewConfig:
        res = self.__config_instance__
        if res is None:
            res = self.__config_instance__ = self.config = self._create_config_instance_('__config__', '__config_class__')
        return res

    def _create_config_instance_(self, attr, cls_attr):
        cls = ViewConfig.get_class(self, cls_attr)
        assert not issubclass(cls, ActionConfig), (
            f"""View config should not be action config. {attr=}, {cls_attr=}
            {cls.mro()}
        """
        )
        return cls(self, attr, self.Config)

    def get_all_action_descriptors(self: type[_T_View]) -> dict[str, ActionRouteDescriptor[_T_View]]:
        """
        Get the methods that are marked as an extra ViewSet `@action`.
        """
        return { 
            r.action: r
                for name, method
                in getmembers(self, is_action_func) if (r := ActionRouteDescriptor.get_existing_descriptor(method))
            }



@export()
class View(t.Generic[_T_Entity], metaclass=ViewType):
    """ResourceManager Object"""
    
    # __slots__ = 'action', 'request', 'args', 'kwargs', '_params', '_ioc', # '__dict__'

    if t.TYPE_CHECKING:
        __config__: t.Final[ViewConfig] = ...

        def run(self, *args, **kwargs) -> t.Union[_T_Entity, Iterable[_T_Entity], HttpResponseBase, None]:
            ...
            
    # config: ViewConfig
    # schemas: AttributeMapping[t.Any, type[_T_Schema]] = _config_lookup('schemas')

    parser: BodyParser

    # ioc: t.Final[IocContainer]
    request: t.Final[Request]
    if t.TYPE_CHECKING:
        config: t.Final[t.Union[ActionConfig, ViewConfig]] = ...


    class Config:
        abstract = True

    @property
    def ioc(self):
        try:
            return self.__dict__['ioc']
        except KeyError:
            return self.__dict__.setdefault('ioc', self.config.ioc.current())

    @ioc.setter
    def ioc(self, val):
        self.__dict__['ioc'] = val
        
    # @property
    # def run(self) -> Callable:
    #     try:
    #         return self.__dict__['run']
    #     except KeyError:
    #         return self.__dict__.setdefault('run', self.missing_handler())
    
    # @run.setter
    # def run(self, val):
    #     self.__dict__['run'] = val

    @property
    def headers(self) -> Headers:
        try:
            return self.__dict__['headers']
        except KeyError:
            return self.__dict__.setdefault('headers', self._get_default_headers())
        
    @property
    def object(self) -> _T_Entity:
        raise AttributeError('object')

    @property
    def objects(self) -> Iterable[_T_Entity]:
        raise AttributeError('objects')

    @property
    def params(self):
        try:
            return self._params
        except AttributeError:
            self._params = res = self.parse_params()
            return res
        
    @property
    def response(self) -> Response:
        try:
            return self.__dict__['response']
        except KeyError:
            return self.__dict__.setdefault('response', self.make_response())
    
    @response.setter
    def response(self, value):
        self.__dict__['response'] = value

    if t.TYPE_CHECKING:
        def _set_private_attr_(self, name, val):
            ...

    @classmethod
    def as_view(cls, actions: Mapping[str, str], /, **config):

        """
        Because of the way class based views create a closure around the
        instantiated view, we need to totally reimplement `.as_view`,
        and slightly modify the view function that is created and returned.
        """
        
        conf = cls.__config__
        ioc = conf.ioc

        mapping = conf.get_action_mapping(actions, config)

        # actions must not be empty
        if not mapping:
            raise TypeError("The `actions` argument must be provided when "
                            "calling `.as_view()` on a ViewSet. For example "
                            "`.as_view({'get': 'list'})`")

        def view(req: Request, *args, **kwargs):
            nonlocal cls, ioc, mapping
            try:
                handler, conf = mapping[req.method]
            except KeyError:
                return HttpResponseNotAllowed(list(mapping), content=b"Method not allowed")
            else:
                inj = ioc.current()
                self: cls = inj[cls]
                self.ioc = inj
                self.config = conf
                if handler is not None:
                    self.run = getattr(self, handler)
                
                return self.dispatch(req, *args, **kwargs)

        # take name and docstring from class
        update_wrapper(view, cls, updated=())

        # and possible attributes set by decorators
        # like csrf_exempt from dispatch
        update_wrapper(view, cls.dispatch, assigned=())

        # We need to set these on the view function, so that breadcrumb
        # generation can pick out these bits of information from a
        # resolved URL.
        view.cls = cls
        view.initkwargs = config
        view.actions = actions
        return csrf_exempt(view)

    def dispatch(self, request: Request, *args, **kwargs):
        self.request = request
        self.args = args
        self.kwargs = kwargs
        try:
            self.finalize(self.run(request, *args, **kwargs))
        except Exception as e:
            return self.handle_exception(e)
        else:
            return self.response

    def finalize(self, res: t.Optional[t.Any]=None):
        """
        Returns the final response object.
        """
        if isinstance(res, HttpResponseBase):
            self.response = res
        elif res is not None:
            self.response.data = self.dump(res)
        elif getattr(res := self.response, 'is_empty', False) is True:
            if res.status_code == HttpStatus.OK_200:
                res.data = self.dump()
            else:
                res.data = None

        # Add new vary headers to the response instead of overwriting.
        # vary_headers = self.headers.pop('Vary', None)
        # if vary_headers is not None:
        #     patch_vary_headers(response, cc_delim_re.split(vary_headers))
        # self.response = res

    def handle_exception(self, exc):
        self.raise_uncaught_exception(exc)

    def raise_uncaught_exception(self, exc):
        raise exc

    # def missing_handler(self) -> Callable:
    #     return getattr(self, self.request.method.lower())

    @t.overload
    def get_payload(self, objects: Iterable[_T_Entity], *, many: t.Literal[True]) -> Sequence[_T_Payload]:
        ...

    @t.overload
    def get_payload(self, object: _T_Entity, *, many: t.Literal[False]=False) -> _T_Payload:
        ...

    def get_payload(self, data: t.Union[Iterable[_T_Entity], _T_Entity], *, many: t.Optional[bool]=None) -> _T_Payload:
        cls = self.config.the_response_schema
        if many:
            return _get_parsing_type(list[cls]).validate(data)
        else:
            return cls.validate(data)

    def dump(self, data: t.Union[Iterable[_T_Entity], _T_Entity]=None):
        conf = self.config
        if data is None:
            shape = conf.shape
            if shape is ContentShape.blank:
                return None
            elif shape is ContentShape.multi:
                data = list(self.objects)
            else:
                data = self.object

        if sch := conf.the_response_schema:
            return sch.validate(data)

        return data

    def abort(self, status=400, errors=None, **kwds):
        self.response.status_code = status
        # raise BadRequest(f'{errors or ""} code={status}')

    def parse_params(self, data=None, *, using: t.Union[type[Schema], None]=None):
        return self.request.GET

    def parse_body(self, body=..., /, **kwds):
        if body is ...:
            body = self.ioc[Body]

        res = body
        if schema := self.config.request_schema:
            if isinstance(body, (str, bytes)):
                res = schema.parse_raw(body, **kwds)
            else:
                res = schema.parse_obj(body, **kwds)
        return res

    def _get_default_headers(self):
        return dict(self.config.headers)
    
    def make_response(self, status=None):
        conf = self.config
        res = conf.response_class(status=status or conf.status, headers=conf.headers)
        res.accepted_renderer, res.accepted_media_type = conf.the_content_negotiator.select_renderer(
            self.request, 
            conf.the_renderers, 
        )
        return res

    @action(detail=True, outline=True)
    def options(self, *args, **kwargs):
        """
        Handler method for HTTP 'OPTIONS' request.
        """
        conf = self.config
        self.response.data = dict(
            title=conf.title,
            description=conf.description.strip()
        )
    