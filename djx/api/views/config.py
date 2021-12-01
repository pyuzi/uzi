
from abc import abstractmethod
from functools import cache
from itertools import chain
import typing as t
import logging

from collections import ChainMap, defaultdict
from collections.abc import Callable, Mapping, Set, Sequence, Iterable

from djx.api.abc import Headers
from djx.common.collections import fallback_default_dict, fallbackdict, frozendict, orderedset
from djx.common.typing import get_type_parameters

from djx.di import ioc, get_ioc_container
from djx.common.utils import export, cached_property, text
from djx.common.metadata import metafield, BaseMetadata, get_metadata_class
from djx.di.container import IocContainer
from djx.schemas import QueryLookupSchema, OrmSchema, Schema, create_schema
# from djx.schemas import QueryLookupSchema, OrmSchema, Schema, create_schema


if t.TYPE_CHECKING:
    from djx.core.models.base import Model, QuerySet
    from . import View, GenericView



from ..types import ViewActionFunction, HttpMethod, ActionRouteDescriptor, T_HttpMethodName, T_HttpMethodStr, ViewFunction
from .. import Request
from ..common import http_method_action_resolver


logger = logging.getLogger(__name__)


_T_Model = t.TypeVar('_T_Model', covariant=True)

_T_DbModel = t.TypeVar('_T_DbModel', bound='Model', covariant=True)




_T_ActionResolveFunc = Callable[['View', Request], 'ActionConfig']
_T_ActionResolver = Callable[['ViewConfig', Mapping[t.Any, str]], _T_ActionResolveFunc]

_T_ActionMap = Mapping[t.Any, 'ActionConfig']


def _is_db_model(cls: type[_T_Model]):
    from django.db.models.base import ModelBase
    return isinstance(cls, ModelBase)


@export()
class BaseConfig(BaseMetadata, t.Generic[_T_Model]):

    __add_to_target__: t.Final[bool] = False
    
    
    # name = None
    target: type['View[_T_Model]']

    
    @metafield[bool](default=...)
    def detail(self, value, base=...):
        if value is ...:
            if base is ...:
                return None
            return base
        return value

    @metafield[str]('basename')
    def basename(self, value, base=None):
        if value:
            return value
        elif isinstance(self, ActionConfig):
            return base
        else:
            return self.get_default_basename()

    @metafield[str](inherit=False)
    def title(self, value):
        if value and self.suffix:
            raise TypeError(
                f"{self.__class__.__name__}() received both `title` and `suffix`, which are "
                f"mutually exclusive."
            )
        elif not (value or self.suffix):
            value = self.get_default_title() 
        
        return value
        
    @metafield[str](inherit=False)
    def suffix(self, value):
        return value

    @metafield[str]()
    def description(self, value, base=None):
        return value or base

    @metafield[Headers]()
    def headers(self, value, base=None):

        # val = dict({
        #     'Allow': ', '.join(self.allowed_methods),
        # }
        
        # )
        # # if len(self.renderer_classes) > 1:
        # #     headers['Vary'] = 'Accept'
        # # return headers
        # if value is None:
        #     val.update()
        return frozendict((base or ()) if value is None else value or ())

    @metafield[HttpMethod]()
    def http_methods(self, value, base=None):
        if value is None:
            if base is None:
                return HttpMethod.ALL
            return HttpMethod(base)
        return HttpMethod(value)

    # @metafield[dict[T_HttpMethodStr,str]]()
    # def mapping(self, value, base=None):
    #     if value is None:
    #         if base is None:
    #             return HttpMethod.ALL
    #         return HttpMethod(base)
    #     return HttpMethod(value)

    @cached_property
    def http_method_names(self):
        return frozenset(m for m in HttpMethod if m in self.http_methods)

    @metafield[type[Schema]]()
    def request_schema(self, value, base=None):
        return value or base
        
    @metafield[type[Schema]]()
    def response_schema(self, value, base=None):
        return value or base
        
    @metafield[bool]()
    def multi_response(self, value, base=None):
        return base if value is None else value
        
    @metafield[type[Schema]](default=...)
    def multi_response_schema(self, value, base=...):
        if value is ...:
            if base is ...:
                return None
            return base
        return value
        
    @metafield[type[Schema]]()
    def param_schema(self, value, base=None):
        return value or base
    
    @cached_property
    def the_response_schema(self):
        if self.multi_response:
            if sch := self.multi_response_schema:
                return sch
            else:
                typ = list[self.response_schema]
                return create_schema(
                    f'{self.target.__name__}MultiResponseSchema',
                    __module__=self.target.__module__,
                    __root__=(typ, ...)
                )
        return self.response_schema

    @cached_property
    def ioc(self):
        return get_ioc_container()

    def get_response_schema(self):
        return self.response_schema

    def get_default_basename(self):
        return 

    def get_default_title(self):
        return text.humanize(self.target.__name__).capitalize() 

    def __repr__(self):
        nl = "\n  "
        attrs = () #  (f"{k}: {v!r}" for k,v in self.__dict__.items() if k in self.__fields__)
        return f'{self.__class__.__name__}({self.__name__}@{self.target.__name__}, '\
            f'{{{nl}{f",{nl}".join(attrs)}{nl}}})'
        
















@export()
class ViewConfig(BaseConfig[_T_Model]):

    is_abstract = metafield[bool]('abstract', default=False, inherit=False)
    
    @property
    def root(self):
        return self

    @metafield[str]()
    def action_param(self, value, base=None):
        return value or base

    @cached_property
    def action_config_class(self) -> type['ActionConfig']:
        return self._get_action_config_class()

    @metafield[orderedset[t.Any]]()
    def renderers(self, value, base=None):
        return orderedset(value if value is not None else base if base is not None else ())
    
    @cached_property
    def renderer_instances(self):
        return self._make_renderer_instances()

    def create_action(self, name: str, conf: dict=frozendict()):
        return self.action_config_class(self.target, name, conf, self)

    def has_action(self, name: str, method=None):
        return not not ActionRouteDescriptor.get_existing_descriptor(getattr(self.target, name, None))

    def _get_action_config_class(self):
        cls: type[ActionConfig] = self._get_base_action_config_class()
        return type(cls.__name__, (cls, self.__class__,), {})

    def _get_base_action_config_class(self) -> type['ActionConfig']:
        return ActionConfig.get_class(self.target, '__action_config_class__')

    def get_action_func(self, name: str, *, default=...) -> ViewActionFunction:
        func = getattr(self.target, name, None)
        descr = ActionRouteDescriptor.get_existing_descriptor(func)
        if not descr:
            if default is ...:
                raise TypeError(
                    f'{name!r} is not a valid action. expected callable '
                    f'but got {func.__class__} in {self.target.__name__}'
                )
            return default

        return func

    def get_action_config(self, action: ViewActionFunction, method: str, config=frozendict()):
        route = action.route.mapping[method]
        if route.name != action.__name__:
            raise TypeError(
                f'cannot bind `{action.__name__}` to `{method}`. '
                f'The method is bound to `{route.name}`'
            )
        return ChainMap(config, route.__dict__, action.route.__dict__)        

    def get_method_map(self, action=None):
        if action is None:
            pass

    def get_action_mapping(self, 
                        actions: Mapping[T_HttpMethodName, str], 
                        config: Mapping=frozendict()) -> Mapping[T_HttpMethodStr, tuple[str, 'ActionConfig']]:

        vardump(config=config, actions=actions)
        
        return {
            HttpMethod(m).name: (a, self.create_action(a, self.get_action_config(self.get_action_func(a), m, config))) 
            for m, a in actions.items()
        }

    def _make_renderer_instances(self):
        return [h for b in self.renderers if (h := ioc.make(b))]



class ActionConfig(BaseConfig):

    @property
    def name(self):
        return self.__name__

    @metafield[str](inherit=False)
    def method(self, value):
        return value or self.name

    @cached_property
    def parent(self) -> t.Union['ActionConfig', 'ViewConfig']:
        raise AttributeError(f'attribute `parent` is not yet available.')

    @property
    def root(self) -> ViewConfig:
        return self.parent.root

    def __loaded__(self):
        super().__loaded__()
        if isinstance(self.__base__, BaseConfig):
            self.parent = self.__base__

    def get_default_title(self):
        return text.humanize(self.name).capitalize() 




@export()
class GenericViewConfig(ViewConfig[_T_DbModel]):
    """ModelViewConfig Object"""

    target: type['GenericView[_T_DbModel]']

    @metafield[t.Optional[type[_T_DbModel]]](default=...)
    def model(self, value, base=...) -> type[_T_DbModel]:
        if value is ...:
            if isinstance(self, ActionConfig):
                return base
            return None
        return value

    @model.getter
    def model(self) -> t.Optional[type[_T_DbModel]]:
        if md := self.__dict__['model']:
            return md
        elif qs := self.queryset:
            return qs.model

    @metafield[orderedset[t.Any]]()
    def filter_pipes(self, value, base=None):
        return orderedset(value if value is not None else base if base is not None else ())
    
    @cached_property
    def filter_pipeline(self) -> Callable[['View[_T_DbModel]']]:
        return self._make_filter_pipeline()

    @metafield[type[t.Any]]()
    def filterset_class(self, value, base=None):
        return value or base

    @metafield[list[str]]()
    def filterset_fields(self, value, base=None):
        return list(value or base or ())

    @metafield[str]()
    def lookup_field(self, value, base=None):
        return value or base or 'pk'
    
    # @metafield[str]()
    # def lookup_param(self, value, base=None):
    #     return value or base
    
    # @property
    # def lookup_param_name(self):
    #     return self.lookup_param or self.lookup_field
    
    lookup_url_kwarg = metafield[str]()
    lookup_value_regex = metafield[str](default=r'[^/.]+')

    @metafield['QuerySet[_T_DbModel]']()
    def queryset(self, value, base=None):
        return value or base

    def _make_filter_pipeline(self):
        return [h for b in self.filter_pipes if (h := ioc.make(b))]

    def get_default_basename(self):
        if mod := self.model:
            if _is_db_model(mod):
                return mod._meta.object_name.lower()
        return super().get_default_basename()
