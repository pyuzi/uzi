
import typing as t
import logging

from functools import partial, update_wrapper
from collections.abc import Hashable, Iterable, Mapping, Callable, Sequence
from django.core.exceptions import BadRequest
from django.views.decorators.csrf import csrf_exempt

from djx.di.common import Depends, InjectionToken
from djx.di.container import IocContainer
from djx.di.scopes import REQUEST_SCOPE

from .abc import BodyParser, Args, Body, Kwargs
from djx.common.collections import frozendict

from djx.di import ioc, get_ioc_container
from djx.common.utils import export, lookup_property, class_only_method
from djx.schemas import QueryLookupSchema, OrmSchema, Schema




from djx.core.models import base as m


from .  import exc, Request
from .types import HttpMethod
from .config import ViewConfig, ActionConfig, ModelViewConfig


logger = logging.getLogger(__name__)

_T_Co = t.TypeVar('_T_Co', covariant=True)

_T_Schema = t.TypeVar('_T_Schema', bound=Schema)

_T_Resource = t.TypeVar('_T_Resource', bound='Resource', covariant=True)
_T_Entity = t.TypeVar('_T_Entity', covariant=True)
_T_Data = t.TypeVar('_T_Data', covariant=True)
_T_Payload = t.TypeVar('_T_Payload', covariant=True)

_T_Model = t.TypeVar('_T_Model', m.Model, t.Any, covariant=True)
_T_Key = t.TypeVar('_T_Key', str, int, t.SupportsInt, Hashable)


_config_lookup = partial(lookup_property, source='config', read_only=True)




_T_ActionResolveFunc = Callable[['View', Request], ActionConfig]
_T_ActionResolver = Callable[[ViewConfig, Mapping[_T_Co, ActionConfig]], _T_ActionResolveFunc]




@export()
class ActionDescriptor(t.Generic[_T_Co]):

    __slots__ = 'func', 'conf',

    func: t.Union[t.Callable[..., _T_Co], None]
    conf: frozendict[str, t.Any]

    def __init__(self, 
                func: t.Union[t.Callable[..., _T_Co], None]=None, 
                conf: dict[str, t.Any] = frozendict(), /, 
                **config):
        self.func = func
        self.conf = frozendict(conf, **config)

    def replace(self, conf: dict[str, t.Any] = frozendict(), /, **config):
        return self.__class__(self.func, self.conf.merge(conf, **config))
        
    def __set_name__(self, owner, name):
        vardump(__set_name__=name, __owner__=owner)        
        if not isinstance(owner, ViewType):
            raise RuntimeError(f'{self.__class__.__name__} can only be added to ViewTypes not {owner}')

    def __call__(self, func: t.Callable[..., _T_Co]) -> t.Callable[..., _T_Co]:
        return self.__class__(func, self.conf)
        

def action(func: t.Union[t.Callable[..., _T_Co], None]=None, 
        conf: dict[str, t.Any] = frozendict(), /, 
        **config: t.Any):

    return ActionDescriptor(func, conf, **config)





class ViewType(type):

    __config_instance__: t.Final[ViewConfig]
    __local_actions__: t.Final[dict[str, dict[str, t.Any]]] = ...

    def __new__(mcls, name: str, bases: tuple[type], dct: dict, **kwds):
        attrs = {}
    
        attrs['__local_actions__'] = actions = {}
        attrs['__config_instance__'] = None

        for n, val in dct.items():
            if isinstance(val, ActionDescriptor):
                actions[n] = val.conf
                if val.func:
                    attrs[n] = val.func
            elif n not in attrs:
                attrs[n] = val

        if 'Config' not in attrs:
            attrs['Config'] = type('Config', (), kwds)
        elif kwds:
            raise TypeError('cannot use both config keywords and Config at the same time')
        

        cls = super().__new__(mcls, name, bases, attrs)
        if any(isinstance(b, ViewType) for b in bases):
            pass
        
        return cls

    @property
    def __actions__(self):
        return self.__config__.actions

    @property
    def __config__(self):
        res = self.__config_instance__
        if res is None:
            res = self.__config_instance__ = self._create_config_instance_('__config__', '__config_class__')
        return res

    def _create_config_instance_(self, attr, cls_attr):
        cls = ViewConfig.get_class(self, cls_attr)
        return cls(self, attr, self.Config)

    def as_view(cls: type['View'], actions=None, resolver: _T_ActionResolver=None, path_params=None, **initkwargs):
        """
        Because of the way class based views create a closure around the
        instantiated view, we need to totally reimplement `.as_view`,
        and slightly modify the view function that is created and returned.
        """
        
        # name and suffix are mutually exclusive
        if 'name' in initkwargs and 'suffix' in initkwargs:
            raise TypeError("%s() received both `name` and `suffix`, which are "
                            "mutually exclusive arguments." % (cls.__name__))

        config = cls.__config__
        ioc = config.ioc
        oactions = actions
        actions, get_action = config.get_action_resolver(actions, resolver)
        
        # actions must not be empty
        if not actions:
            raise TypeError("The `actions` argument must be provided when "
                            "calling `.as_view()` on a ViewSet. For example "
                            "`.as_view({'get': 'list'})`")

        # if not ioc.is_injectable(cls):
            # ioc.alias()(cls, use=cls, at=REQUEST_SCOPE, priority=-10)

        token = InjectionToken(f'{cls.__name__}.actions[{" | ".join(dict.fromkeys(a.name for a in actions.values()))}]')

        ioc.type(token, use=cls, at=REQUEST_SCOPE, cache=True, kwargs=initkwargs)

        vardump(token, oactions, initkwargs)

        def view(req: Request, *args, **kwargs):
            nonlocal cls, ioc, get_action, initkwargs
            inj = ioc.injector
            # inj[Args] = args
            # inj[Kwargs] = frozendict(kwargs)

            # vardump(inj, *inj.scope.providers.keys())
            self: View = inj[token]
            action = get_action(self, req)

            return self.dispatch(req, action, *args, **kwargs)

        # take name and docstring from class
        update_wrapper(view, cls, updated=())

        # and possible attributes set by decorators
        # like csrf_exempt from dispatch
        update_wrapper(view, cls.dispatch, assigned=())

        # We need to set these on the view function, so that breadcrumb
        # generation can pick out these bits of information from a
        # resolved URL.
        view.cls = cls
        view.initkwargs = initkwargs
        view.actions = actions
        return csrf_exempt(view)



@export()
class View(t.Generic[_T_Entity], metaclass=ViewType):
    """ResourceManager Object"""
    
    __slots__ = 'action', 'request', 'ioc', # '__dict__'

    if t.TYPE_CHECKING:
        __config__: t.Final[ViewConfig] = ...

    # config: ViewConfig
    # schemas: AttributeMapping[t.Any, type[_T_Schema]] = _config_lookup('schemas')

    parser: BodyParser

    ioc: t.Final[IocContainer]
    request: t.Final[Request]
    action: t.Final[ActionConfig]


    class Config:
        abstract = True

    def __init__(self, request: Request, ioc: IocContainer, **kwargs):
        """
        Constructor. Called in the URLconf; can contain helpful extra
        keyword arguments, and other things.
        """
        # Go through keyword arguments, and either save their values to our
        # instance, or raise an error.
        self.request = request
        self.ioc = ioc

        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def config(self):
        """
        Get the current `ViewConfig`. Uses `self.action` if present. 
        Otherwise the view  `self.__config__`
        """
        return self.action or self.__config__

    # @property
    # def data(self):
    #     raise AttributeError('data')
        
    @property
    def object(self) -> _T_Entity:
        raise AttributeError('object')

    @property
    def objects(self) -> Iterable[_T_Entity]:
        raise AttributeError('objects')

    @property
    def params(self):
        raise AttributeError('params')
        
    
    if t.TYPE_CHECKING:
        def _set_private_attr_(self, name, val):
            ...

    _setprivateattr_ = object.__setattr__

    # Note: Views are made CSRF exempt from within `as_view` as to prevent
    # accidental removal of this exemption in cases where `dispatch` needs to
    # be overridden.
    def dispatch(self, request: Request, action: t.Optional[ActionConfig]=None, *args, **kwargs):
        """
        `.dispatch()` is pretty much the same as Django's regular dispatch,
        but with extra hooks for startup, finalize, and exception handling.
        """
        self.action = action
        self.request = request
        
        handler = action.get_handler()

        return handler(self)

    @t.overload
    def get_payload(self, objects: Iterable[_T_Entity], *, many: t.Literal[True]) -> Sequence[_T_Payload]:
        ...

    @t.overload
    def get_payload(self, object: _T_Entity, *, many: t.Literal[False]=False) -> _T_Payload:
        ...

    def get_payload(self, data: t.Union[Iterable[_T_Entity], _T_Entity], *, many: bool=False) -> _T_Payload:
        if many is True:
            return self.config.get_list_response_schema()(list(data))
        else:
            return self.config.get_response_schema().validate(data)

    def abort(self, status=400, errors=None, **kwds):
        raise BadRequest(f'{errors or ""} code={status}')

    def parse_params(self, data=None, *, using: t.Union[type[Schema], None]=None):
        pass

    def parse_body(self, body=..., /, **kwds):
        if body is ...:
            body = self.ioc[Body]

        schema = self.config.request_schema
        if isinstance(body, (str, bytes)):
            res = schema.parse_raw(body, **kwds)
        else:
            res = schema.parse_obj(body, **kwds)
        return res



@export()
class GenericView(View[_T_Model]):
    """ResourceManager Object"""
    
    __slots__ = '_params', '_obj', '_objs', '_qs',

    # _data: t.Final[_T_Data]
    _params: t.Final[t.Any]

    _obj: t.Final[_T_Model]
    _objs: t.Final[t.Union[m.QuerySet[_T_Model], Iterable[_T_Model]]]

    # Model: type[_T_Model] = _config_lookup('model')

    __config_class__ = ModelViewConfig

    @property
    def objects(self) -> m.QuerySet[_T_Model]:
        """
        The list of filtered items for this view.
        
        This must be an iterable, and may be a queryset.
        Override `self._get_objects()`.

        """
        try:
            return self._objs
        except AttributeError:
            self._objs = self._get_objects()
            return self._objs

    @property
    def object(self) -> _T_Model:
        """
        The current object for this request.
        
        This must be an iterable, and may be a queryset.
        Override `self._get_objects()`.

        """
        try:
            return self._obj
        except AttributeError:
            self._obj = self._get_object()
            return self._obj

    @property
    def params(self):
        """
        Get the list of items for this view.
        This must be an iterable, and may be a queryset.
        Defaults to using `self.queryset`.

        Override `self._get_queryset()` if you need to provide different
        querysets depending on the incoming request.
        """
        try:
            return self._params
        except AttributeError:
            self._params = self.parse_params()
            return self._params

    def filter_queryset(self, queryset: m.QuerySet[_T_Model]):
        """
        Given a queryset, filter it with whichever filter backend is in use.

        You are unlikely to want to override this method, although you may need
        to call it either from a list view, or from a custom `get_object`
        method if you want to apply the configured filtering backend to the
        default queryset.
        """

        # for backend in list(self.filter_backends):
        #     queryset = backend().filter_queryset(queryset, self)
        return queryset

    def get_queryset(self) -> m.QuerySet[_T_Model]:
        """
        Create the list of items for this view.
        This must be an iterable, and may be a queryset.
        Defaults to using `self.config.queryset`.

        You may want to override this if you need to provide different
        querysets depending on the incoming request.

        (Eg. return a list of items that is specific to the user)
        """
        
        queryset = self.config.queryset
        if isinstance(queryset, m.QuerySet):
            # Ensure queryset is re-evaluated on each request.
            queryset = queryset.all()
        return queryset

    def _get_objects(self) -> m.QuerySet[_T_Model]:
        """
        Returns the sequence of filtered objects for this request.
        Must be an iterable, and may be a queryset.
        Defaults to using filtered `self.queryset`.

        You may want to override this if you need to provide non-standard iterables.
        """
        return self.filter_queryset(self.get_queryset())

    def _get_object(self):
        """
        Returns the object the view is displaying.

        You may want to override this if you need to provide non-standard
        queryset lookups.  Eg if objects are referenced using multiple
        keyword arguments in the url conf.
        """
        conf = self.config
        return self.objects.get(**{ conf.lookup_field: self.params[conf.lookup_param_name]})


