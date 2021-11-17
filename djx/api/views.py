from collections import ChainMap
from inspect import Parameter
import typing as t 

from functools import update_wrapper

from collections.abc import Callable, Collection, Iterable, Mapping
from djx.api.common import ParamFlag
from djx.api.params.fields import Body, Cookie, File, Form, Header, Path, Query

from djx.common.utils import export
from djx.common.typing import get_all_type_hints, get_true_types, get_origin, get_args, eval_type, iter_true_types

from djx.di import get_ioc_container, IocContainer, Injector
from djx.common.collections import MappingProxy, fallback_default_dict, frozendict, nonedict, orderedset
from djx.schemas import OrmSchema, Schema, FieldInfo, ValidationError, validate_schema

from djx.schemas.decorator import ValidatedFunction, ValidatedFunctionSchema, ParameterInfo
from djx.abc.api import Request, Response
from djx.schemas.types import SupportsValidation
from pydantic.utils import GetterDict




from .params import ParamFieldInfo, ParamSource




_T_Return = t.TypeVar('_T_Return')
T_ViewFuncion = Callable[..., _T_Return]

class ParamSourceAlias(str):

    __slots__ = 'src', 'aka',

    def __new__(cls, name, src, alias=...):
        self = str.__new__(cls, name)
        self.src = src
        self.aka = name if alias is ... else alias or name
        return self





class ViewArgumentsDict(dict[ParamSourceAlias, t.Any]):
    
    __slots__ = 'inj',

    inj: Injector

    def __init__(self, inj: Injector, values=(), /):
        self.inj = inj
        dict.__init__(self, values)

    def get(self, key, default=None):
        try:
            return self.inj[key.src][key.aka]
            # return self[key]
        except KeyError:
            return default
        # return default

    def __missing__(self, key: ParamSourceAlias):
        # vardump(__inj=self.inj.vars[s], __missing__=key, __src__=key.src, __aka__=key.aka)
        # if (src := key.src) is not None:
        return self.inj[key.src][key.aka]
            
        # raise KeyError(key)





@export()
class ViewFunction(ValidatedFunction):

    if t.TYPE_CHECKING:
        def view() -> t.Any:
            ...

    __slots__ =  'ioc', 'view', # '_param_sources',


    
    def __init__(self, func: T_ViewFuncion, config=None, *, ioc: IocContainer=None):
        self.ioc = ioc or get_ioc_container()
        super().__init__(func, config)
        self._setup_view()

    # @property
    # def param_sources(self):
    #     try:
    #         return self._param_sources
    #     except AttributeError:
    #         self._setup_param_sources()
    #         return self._param_sources

    def get_view_injector(self):
        return self.ioc.injector

    def _setup_view(self):
        self.view = update_wrapper(self.create_view(), self.func)

    # def validate_view(self, *args, **kwargs) -> ViewFunctionSchema:
    #     val = self.build_view_values(args, kwargs)
    #     return self.validate_values(val)

    # def build_view_values(self, args, kwargs) -> ViewFunctionSchema:
    #     return self.schema._decompose_class(ViewArgumentsDict(self, self.view_injector, kwargs))

    def _validate_view_arguments(self, args=(), kwargs=frozendict()):
        vals, fset, errs = validate_schema(self.schema, ViewArgumentsDict(
            self.ioc.injector
        ))
        if errs:
            raise ValidationError(errs, self.schema)
        return vals
        
    def create_view(self):
        func = self.func
        def view_func(*a, **kw):
            nonlocal self, func
            try:
                return self.make_response(func(*a, **kw))
            except Exception as e:
                return self.handle_view_exception(e, a, kw)

        view = self._create_wrapper(
            fvalidate=self.__class__._validate_view_arguments,
            func=view_func
        )
        return view

    
    def handle_view_exception(self, exc, args=(), kwargs=frozendict()):
        raise exc

    def make_response(self, res):
        from django.http import JsonResponse, HttpResponse
        if not isinstance(res, Response):
            return JsonResponse(res)
        return res
        

    # def _setup_param_sources(self):
    #     self._param_sources = self._create_param_sources()

    # def _create_param_sources(self):
    #     res = {}
    #     for p in self.params.values():
    #         res[p.alias] = list(self._eval_param_source(p))
    #     return res      

    def _setup_schema(self):
        super()._setup_schema()
        params = self.params
        for f in self.schema.__fields__.values():
            f.alias = ParamSourceAlias(f.name, *self._eval_param_source(f.field_info, params[f.name]))

    # def _create_schema_fields(self):
    #     ret = super()._create_schema_fields()
    #     params = self.params

    #     for n in ret:
    #         field = ret[n][1]
    #         field.alias = ParamSourceAlias(n, *self._eval_param_source(params[n], field))
    #     return ret

    def _eval_param_source(self, field: ParamFieldInfo,  param: ParameterInfo):
        if isinstance(field, ParamFieldInfo):
            return field.param_src
        else:
            return None, None







def _is_container_type(tp: type[t.Any]):
    return issubclass(tp, (Mapping, Schema))



def _is_collection_type(tp: type[t.Any]):
    return issubclass(tp, Iterable) and not issubclass(tp, (str, bytes)) 


_string_ = frozenset([
    int,
    float,
    str,
    bytes,
    bool,
    
])


_collection_types = frozenset([
    Collection,
    Schema,
])




                


    
    