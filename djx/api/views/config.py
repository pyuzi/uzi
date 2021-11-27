
from abc import abstractmethod
from functools import cache
from itertools import chain
import typing as t
import logging

from collections import ChainMap, defaultdict
from collections.abc import Callable, Mapping, Set, Sequence, Iterable

from django.db import models as m
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
    from djx.core.models.base import Model
    from . import View, GenericView

else:
    Model = m.Model


from ..types import ActionMethod, HttpMethod, MethodMapper, T_HttpMethodName, T_HttpMethodStr, ViewMethod
from .. import Request
from ..common import http_method_action_resolver


logger = logging.getLogger(__name__)


_T_Entity = t.TypeVar('_T_Entity', covariant=True)

_T_Model = t.TypeVar('_T_Model', bound=Model, covariant=True)




_T_ActionResolveFunc = Callable[['View', Request], 'ActionConfig']
_T_ActionResolver = Callable[['ViewConfig', Mapping[t.Any, str]], _T_ActionResolveFunc]

_T_ActionMap = Mapping[t.Any, 'ActionConfig']



@export()
class BaseConfig(BaseMetadata, t.Generic[_T_Entity]):

    __add_to_target__: t.Final[bool] = False
    

    target: type['View[_T_Entity]']

    entity: type[_T_Entity]
    
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
        return self.target.__name__

    # def __repr__(self):
    #     nl = "\n  "
    #     return f'{self.__class__.__name__}({self.target.__name__}, '\
    #         f'{{{nl}{f",{nl}".join(f"{k}: {v!r}" for k,v in self.__dict__.items() if k in self.__fields__)}{nl}}})'
        
















@export()
class ViewConfig(BaseConfig[_T_Entity]):

    is_abstract = metafield[bool]('abstract', default=False, inherit=False)

    # @metafield[dict[T_HttpMethodNameUpper, str]](default=...)
    # def detail_actions(self, value, base=...):
    #     if value is ...:
    #         if base is ...:
    #             return 
    #         return { }
    #     return value

    # @metafield[dict[T_HttpMethodNameUpper, str]](default=...)
    # def list_action(self, value, base=...):
    #     if value is ...:
    #         if base is ...:
    #             return 
    #         return base
    #     return value

    # @cached_property
    # def root_actions(self) -> list[Callable]:
    #     mapping = self.action_mapping
    #     if mapping is 
    #     return [
            
    #     ]

    # @cached_property
    # def actions_config(self) -> dict[str, dict[str, t.Any]]:
    #     from . import ViewType
    #     res = defaultdict(dict)
        
    #     bases = chain((
    #         b.__local_actions__ 
    #         for b in reversed(self.target.mro())
    #             if isinstance(b, ViewType)
    #     ))

    #     for dct in bases:
    #         for k, v in dct.items():
    #             res[k].update(v)

    #     return dict(res)

    # @cached_property
    # def concrete_actions(self) -> list[str]:
    #     return [a for a in self.actions_config if callable(getattr(self.target, a, None))]
        
    @metafield[_T_ActionResolver]('action_resolver', default=...)
    def default_action_resolver(self, value, base=...):
        if value is ...:
            if base is ...:
                return http_method_action_resolver
            return base
        return value
    
    @metafield[Set[_T_ActionResolver]](default=...)
    def allowed_action_resolvers(self, value, base=...):
        if value is ...:
            if base is ...:
                return {t.Any}
            return base
        elif value is not None:
            return set(value)
    
    @metafield[str]()
    def action_param(self, value, base=None):
        return value or base

    @cached_property
    def action_config_class(self) -> type['OperationConfig']:
        return self._eval_action_config_class()

    # @cached_property
    # def actions(self) -> fallbackdict[str, 'ActionConfig']:
    #     return self._create_actions_dict()

    # def _create_actions_dict(self):
    #     fb = self._get_action_dict_fallback()
    #     return fallback_default_dict(fb)

    # def _get_action_dict_fallback(self):
    #     def fallback(key):
    #         nonlocal self
    #         try:
    #             return self.create_action(key, self.actions_config[key])
    #         except KeyError:
    #             return None

    #     return fallback

    def create_action(self, name: str, conf: dict=frozendict()):
        return self.action_config_class(self.target, name, conf, self)

    def has_action(self, name: str):
        return getattr(self.target, name, None) is not None

    def _eval_action_config_class(self):
        cls: type[OperationConfig] = self._get_base_action_config_class()
        return type(cls.__name__, (cls, self.__class__,), {})

    def _get_base_action_config_class(self) -> type['OperationConfig']:
        return OperationConfig.get_class(self.target, '__action_config_class__')

    # def which_action_resolver(self, 
    #                         using: t.Union[_T_ActionResolver, None]=None,
    #                         actions: t.Union[_T_ActionMap, None]=None) -> t.Union[_T_ActionResolver, None]:
    #     if using is None:
    #         return self.default_action_resolver
    #     return using

    # def get_resolvable_actions(self, actions: t.Union[Mapping[t.Any, str], None]=None, using: t.Union[_T_ActionResolver, None]=None) -> _T_ActionResolveFunc:
    #     if actions:
    #         res = dict()
    #         all = self.actions
    #         for k, n in actions.items():
    #             a = all[n]
    #             if not a.is_available:
    #                 raise LookupError(f'action {n!r} is not available in {self.target}')
    #             res[k] = a
    #         return res

    # def get_action_resolver(self, 
    #     actions: t.Union[Mapping[t.Any, str], None]=None, 
    #     using: t.Union[_T_ActionResolver, None]=None
    # ) -> tuple[t.Optional[_T_ActionMap], _T_ActionResolveFunc]:

    #     using = self.which_action_resolver(using, actions)
    #     actions = self.get_resolvable_actions(actions, using)
    #     return actions, self.ioc.make(using, self, actions)

    def get_action_func(self, name) -> ActionMethod:
        func = getattr(self.target, name, None)
        if not isinstance(func, ViewMethod):
            raise TypeError(
                f'{name!r} is not a valid action. expected callable '
                f'but got {func.__class__} in {self.target.__name__}'
            )
        return func

    def get_action_config(self, action: ActionMethod, default=frozendict()):
        return getattr(action, 'config', default)

    def get_action_mapping(self, 
                        actions: Mapping[T_HttpMethodName, str], 
                        config: Mapping=frozendict()) -> Mapping[T_HttpMethodStr, tuple[str, 'OperationConfig']]:

        # mapping = dict(actions)      
        # res = {}  
        mapping: MethodMapper = config.get('mapping')

        if mapping and mapping.action:
            bases = self.get_action_config(mapping.action),
        else:
            bases = ()

        return {
            HttpMethod(m).name: (a, self.create_action(a, ChainMap(config, self.get_action_config(self.get_action_func(a)), *bases))) 
            for m, a in actions.items()
        }





class ActionConfig(ViewConfig):

    # is_root = 

    @property
    def attr(self):
        return self.__name__
    
    @cached_property
    def parent(self) -> 'OperationConfig':
        return None

    def __loaded__(self):
        super().__loaded__()
        self.parent = self.__base__




class OperationConfig(BaseConfig):

    @property
    def attr(self):
        return self.__name__

    @cached_property
    def parent(self) -> 'OperationConfig':
        return None

    @metafield[str](inherit=False)
    def name(self, value):
        if value and self.suffix:
            raise TypeError(
                f"{self.__class__.__name__}() received both `name` and `suffix`, which are "
                f"mutually exclusive."
            )
        elif not self.suffix:
            value = text.humanize(self.__name__).capitalize()
        
        return value
    
    @metafield[str](inherit=False)
    def suffix(self, value):
        return value

    def __loaded__(self):
        super().__loaded__()
        self.parent = self.__base__





@export()
class GenericViewConfig(ViewConfig[_T_Model]):
    """ModelViewConfig Object"""

    target: type['GenericView[_T_Model]']

    @property
    def entity(self) -> type[_T_Model]:
        return self.model

    @metafield[orderedset[t.Any]]()
    def filter_pipes(self, value, base=None):
        return orderedset(value if value is not None else base if base is not None else ())
    
    @cached_property
    def filter_pipeline(self) -> Callable[['View[_T_Model]']]:
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
    
    @metafield[str]()
    def lookup_param(self, value, base=None):
        return value or base
    
    @property
    def lookup_param_name(self):
        return self.lookup_param or self.lookup_field
    
    @property
    def model(self) -> type[_T_Model]:
        if qs := self.queryset:
            return qs.model
    
    @metafield[m.QuerySet[_T_Model]]()
    def queryset(self, value, base=None):
        return value or base

    def _make_filter_pipeline(self):
        return [h for b in self.filter_pipes if (h := ioc.make(b))]

