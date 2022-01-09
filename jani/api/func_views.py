from collections import ChainMap
from inspect import Parameter
import typing as t 

from functools import update_wrapper
from itertools import groupby

from collections.abc import Callable, Collection, Sequence, Mapping, Hashable
from jani.api.common import ParamFlag
from jani.common.enum import IntFlag, auto
# from jani.api.params.fields import Body, Cookie, File, Form, Header, Path, Query

from jani.common.utils import export, class_property
# from jani.common.typing import get_all_type_hints, get_true_types, get_origin, get_args, eval_type, iter_true_types

from jani.di import get_ioc_container, IocContainer, Injector
from jani.common.collections import MappingProxy, fallback_chain_dict, fallback_default_dict, fallbackdict, frozendict, nonedict, orderedset
from jani.di.common import Injectable
from jani.schemas import OrmSchema, Schema, FieldInfo, ValidationError, validate_schema

from jani.schemas.decorator import ValidatedFunction, ValidatedFunctionSchema, ParameterInfo
from jani.abc.api import Kwargs, Arguments, Request, Response
from jani.schemas.utils import is_collection_type, is_singular_type, supports_validation, is_sequential_type, is_mapped_type


from jani.common.exc import ImproperlyConfigured

from . import abc


from .params import ParamFieldInfo, ParamSource


ioc = get_ioc_container()

_T_Return = t.TypeVar('_T_Return')
T_ViewFuncion = Callable[..., _T_Return]

class ParamSourceAlias(str):

    __slots__ = 'srcs',

    srcs: tuple[tuple[Injectable, Hashable]]

    def __new__(cls, name, *srcs):
        self = str.__new__(cls, name)
        self.srcs = srcs
        return self





class ViewArgumentsDict(dict[ParamSourceAlias, t.Any]):
    
    __slots__ = 'inj',

    inj: Injector

    def __init__(self, inj: Injector, /):
        dict.__init__(self)
        self.inj = inj

    def get(self, key: ParamSourceAlias, default=None):
        for src, aka in key.srcs:
            try:
                if aka is ...:
                    return self.inj[src]
                else:
                    return self.inj[src][aka]
            except KeyError:
                pass
                # vardump(src=src, aka=aka, key=key, srcs=key.srcs)
        
        return default

    def __getitem__(self, key: ParamSourceAlias):
        for src, aka in key.srcs:
            try:
                if aka is ...:
                    return self.inj[src]
                else:
                    return self.inj[src][aka]
            except KeyError:
                pass
        raise KeyError(key)



def _param_source_group_fallback(key):
    if ioc.is_injectable(key):
        return [Injector]
    
class ParamFlag(IntFlag):
    injectable: 'ParamFlag'     = auto()
    none: 'ParamFlag'           = auto() 
    object: 'ParamFlag'         = auto()
    mapping: 'ParamFlag'        = auto()
    singular: 'ParamFlag'       = auto()
    sequential: 'ParamFlag'     = auto()
    validates: 'ParamFlag'      = auto()

    @class_property
    def mapped(cls):
        return cls.mapping | cls.object

    if t.TYPE_CHECKING:
        mapped: 'ParamFlag' = mapping | object

    @classmethod
    def _missing_(cls, val):
        if val is None:
            return cls.none
        return super()._missing_(val)



class ViewParameterInfo(ParameterInfo):

    __slots__ = '_explicit_sources', '_implicit_sources', '_flags',

    _validated_sources = {
        k: k 
        for k in (
            abc.Args, 
            abc.Kwargs, 
            abc.Arguments, 

            abc.Query, 
            abc.QueryList,

            abc.Body, 
            abc.RawBody,

            abc.Form, 
            abc.FormList, 
            abc.Files, 

            abc.Headers, 
            abc.Cookies, 

            abc.Inputs,
            abc.Params,
        )
    }

    _validated_sources.update({
        (abc.Query, ParamFlag.sequential): abc.QueryList,
        (abc.Form, ParamFlag.sequential): abc.FormList,
    })

    @property
    def flags(self) -> ParamFlag:
        try:
            return self._flags
        except AttributeError:
            self._flags = self._eval_flags()
            return self._flags
            
    @property
    def explicit_sources(self):
        try:
            return self._explicit_sources
        except AttributeError:
            self._setup_sources()
            return self._explicit_sources
        
    @property
    def implicit_sources(self):
        try:
            return self._implicit_sources
        except AttributeError:
            self._setup_sources()
            return self._implicit_sources

    @property
    def has_source(self):
        return bool(self.explicit_sources or self.implicit_sources)

    @property
    def all_sources(self):
        return ChainMap(self.implicit_sources, self.explicit_sources)

    @property
    def sourcekey(self) ->tuple[Injectable, Hashable]:
        field = self.field
        if isinstance(field, ParamFieldInfo):
            return field.param_src
        else:
            return self.annotation, field and field.alias or ... 
        
    def _eval_flags(self):
        typs = self.get_true_types()

        flags: ParamFlag = ParamFlag.none

        if ioc.is_injectable(self.annotation):
            flags |= ParamFlag.injectable
        # elif self.annotation != self.sourcekey[0]:


        if all(supports_validation(t) for t in typs):
            flags |= ParamFlag.validates

        if all(is_sequential_type(t) for t in typs):
            flags |= ParamFlag.sequential
        elif all(is_mapped_type(t) for t in typs):
            if all(is_collection_type(t) for t in typs):
                flags |= ParamFlag.mapping
            else:
                flags |= ParamFlag.object
        elif all(is_singular_type(t) for t in typs):
            flags |= ParamFlag.singular
        
        return flags

    def _setup_sources(self):
        self._explicit_sources, self._implicit_sources = self._eval_sources()

    def _eval_sources(self):
        explicit = dict()
        implicit = dict()

        ann, aka = self.sourcekey
        flags = self.flags

        vsrc = self._get_validated_source(ann)

        if vsrc:
            if not flags & flags.validates:
                ImproperlyConfigured(
                    f'arbitrary types not allowed for {vsrc.__name__} parameters. '
                    f'{ann!r} must implemtnent SupportsValidation'
                )
            
            if flags & flags.sequential:
                explicit[vsrc] = self.alias if aka is ... and vsrc is not abc.Body else aka
            elif flags & flags.mapped:
                explicit[vsrc] = aka
            else:
                explicit[vsrc] = self.alias if aka is ... else aka

            if ann != self.annotation and flags & flags.injectable:
                implicit[self.annotation] = aka
                
        elif self.field:    
            if not flags & flags.validates:
                ImproperlyConfigured(
                    f'arbitrary types not allowed for Field parameters. '
                    f'{ann!r} must implemtnent SupportsValidation.'
                )

            if flags & flags.sequential:
                implicit[self._get_validated_source(abc.Query)] = self.alias if aka is ... else aka
                # implicit[self._get_validated_source(abc.Body)] = self.alias if aka is ... else aka
            elif flags & flags.mapped:
                implicit[self._get_validated_source(abc.Body)] = aka  
            else:
                implicit[self._get_validated_source(abc.Arguments)] = self.alias if aka is ... else aka
                implicit[self._get_validated_source(abc.Query)] = self.alias if aka is ... else aka
            
        elif flags & flags.validates:
            if flags & flags.sequential:
                implicit[self._get_validated_source(abc.Query)] = self.alias
                # implicit[self._get_validated_source(abc.Body)] = self.alias if aka is ... else aka
            elif flags & flags.mapped:
                implicit[self._get_validated_source(abc.Body)] = ...  
            else:
                implicit[self._get_validated_source(abc.Kwargs)] = self.alias
                implicit[self._get_validated_source(abc.Query)] = self.alias
        elif ann != self.annotation: 
            explicit[ann] = aka
        elif flags & flags.injectable:
            explicit[self.annotation] = aka
        
        if flags & flags.injectable:
            implicit[self.annotation] = aka
            
        return frozendict(explicit), frozendict(implicit)


    def _get_validated_source(self, tp: type[t.Any]):
        if res := self._validated_sources.get(tp):
            flags = self.flags
            for fl in ParamFlag:
                if flags & fl:
                    if _res := self._validated_sources.get((res, fl)):
                        return self._get_validated_source(_res)
        return res

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name}, expl_sources={self.explicit_sources}, impl_sources={self.implicit_sources})'




# class KindofParamType:



@export()
class ViewFunction(ValidatedFunction):

    if t.TYPE_CHECKING:
        def view() -> t.Any:
            ...

    __slots__ = 'ioc', 'view', '_inj_args', '_inj_kwargs', '_view_schemas', '_param_src_groups',


    params: dict[str, ViewParameterInfo]

    _param_info_class = ViewParameterInfo

    def __init__(self, func: T_ViewFuncion, config=None, *, ioc: IocContainer=ioc):
        self.ioc = ioc
        super().__init__(func, config)
        self._inj_args = []
        self._inj_kwargs = []
        self._setup_view()

    @property
    def view_schemas(self):
        try:
            return self._view_schemas
        except AttributeError:
            self._setup_view_schemas()
            return self._view_schemas

    @property
    def param_src_groups(self):
        try:
            return self._param_src_groups
        except AttributeError:
            self._setup_param_src_groups()
            return self._param_src_groups

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
        injector = ViewArgumentsDict(self.ioc.injector)
        vals, fset, errs = validate_schema(self.schema, injector)
        if errs is not None:
            raise ValidationError(errs, self.schema)

        return vals


    def _validate_arguments(self, args=(), kwargs=frozendict()):
        vals, fset, errs = validate_schema(self.schema, ChainMap(kwargs, ViewArgumentsDict(self.ioc.injector)), args)
        if errs is not None:
            raise ValidationError(errs, self.schema)

        # injector = ViewArgumentsDict(self.ioc.injector)
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
        
    def _setup_view_schemas(self):
        self._view_schemas = self._create_view_schemas(
            self._eval_view_param_src_groups()
        )

    def _create_view_schemas(self, groups: dict[t.Any, list[ViewParameterInfo]]):
        schemas = {}
        params = self.params
        
        for g, params in groups.items():
            if params: # and g not in {Injector, None}:
                schema = self._create_schema(
                    getattr(g, '__name__', ''), 
                    fields={
                        p.alias: (p.annotation, self._create_param_field(p)) 
                        for p in params
                    },
                    config=...
                )
            schemas[g] = schema

        return schemas
    
    def _setup_param_src_groups(self):
        self._param_src_groups = self._eval_view_param_src_groups()

    def _eval_view_param_src_groups(self):
        res = fallback_default_dict(list)
        for p in self.params.values():
            srcs = self._get_param_src_groups(p)
            if not isinstance(srcs, (list, tuple)):
                srcs = srcs,
            
            for src in srcs:
                res[src].append(p.name)
                    
        return res      

    # def _get_param_src_groups(self, p: ViewParameterInfo):
    #     src, aka = self.get_param_src(p)
    #     for src in p.sources:

    #     return self._param_source_groups[src] or [None]

    def _get_args(self, values: dict):
        # if self._inj_args:
        #     inj = values[Injector]
        #     for arg in self._inj_args:
        #         yield inj[arg]

        for name in self.args:
            yield values[name]

        if self.var_arg:
            yield from values[self.var_arg]

    def _get_var_arg(self, values: dict):
        return values[self.var_arg]

    def _get_kwargs(self, values: dict):
        kwds = dict()
        for name in self.kwargs:
            kwds[name] = values[name]
    
        if self.var_kwarg:
            kwds.update(values[self.var_kwarg])

        return kwds

    def _get_var_kwarg(self, values: dict):
        return values[self.var_kwarg]

    def _setup_schema(self):
        super()._setup_schema()
        schema = self.schema

        expl_bodies = orderedset(p for p in self.params.values() if abc.Body in p.explicit_sources)
        expl_body_roots = orderedset(p for p in expl_bodies if p.explicit_sources[abc.Body] is ...)
        expl_body_keys = orderedset(p for p in expl_bodies if p.explicit_sources[abc.Body] is not ...)
        expl_body = len(expl_body_roots) == 1 and expl_body_roots[0] or None

        impl_bodies = orderedset(p for p in self.params.values() if abc.Body in p.implicit_sources)
        impl_body_roots = orderedset(p for p in impl_bodies if p.implicit_sources[abc.Body] is ...)
        impl_body_keys = orderedset(p for p in impl_bodies if p.implicit_sources[abc.Body] is not ...)
        impl_body = len(impl_body_roots) == 1 and impl_body_roots[0] or None

        all_bodies = expl_bodies | impl_bodies
        root_bodies = expl_body_roots | impl_body_roots
        body = expl_body if expl_body else impl_body

        _group_srcs = lambda p, s=None:  groupby(
            (s := p.all_sources if s is None else s), 
            key=lambda i: s[i]
        )

        
        for name, f in schema.__fields__.items():

            p = self.params[name]
            srcs = dict(p.all_sources)

            if p.explicit_sources: 
                if not expl_body and p in expl_body_roots:
                    if srcs[abc.Body] is ...:
                        srcs[abc.Body] = p.alias
            elif p.implicit_sources:
                if p in all_bodies:
                    if p is not body:
                        raise ImproperlyConfigured(
                                f'ambiguous param source in {p}'
                            )
            else: 
                raise ImproperlyConfigured(
                    f'unknown param source for {p}'
                )
            
            # grps_ = dict((t.Union[tuple(s)], k) for k, s in grps.items()) # type: ignore

            f.alias = aka = ParamSourceAlias(f.alias, *srcs.items())

            # if  p.flags & p.flags.injectable and not p.flags & p.flags.validates:
            #     if name in self.args:
            #         self.args[self.args.index(name)] = aka
            #     elif name == self.var_arg:
            #         self.var_arg = aka
            #     elif name in self.kwargs:
            #         self.kwargs[self.args.index(name)] = aka
            #     elif name == self.var_kwarg:
            #         self.var_kwarg = aka

            #     schema.__fields__.pop(name)

        vardump(__param__=self.params, __schema__=schema.__fields__, 
        schema_args=schema.__config__.init_args, 
        args=self.args[-3].__class__, kwargs=self.kwargs, var_arg=self.var_arg, var_kwarg=self.var_kwarg)


    # def _set_param_field(self, p: ViewParameterInfo, field: FieldInfo, fields: dict):
    
    #     if  p.flags & p.flags.injectable and not p.flags & p.flags.validates:
    
    #         name = p.name
    #         grps_ = dict((t.Union[tuple(s)], k) for k, s in groupby(p.all_sources, key=lambda i: p.all_sources[i])) # type: ignore
    #         aka = ParamSourceAlias(p.name, *grps_.items())
    #         if name in self.args:
    #             self.args[self.args.index(name)] = aka
    #         elif name == self.var_arg:
    #             self.var_arg = aka
    #         elif name in self.kwargs:
    #             self.kwargs[self.kwargs.index(name)] = aka
    #         elif name == self.var_kwarg:
    #             self.var_kwarg = aka
        
    #     elif not p.has_source:
    #         raise ImproperlyConfigured(
    #                 f'unknown param source for {p}'
    #             )
    #     else:
    #         super()._set_param_field(p, field, fields)

    # def _create_schema_fields(self):
    #     ret = super()._create_schema_fields()
    #     params = self.params

    #     for n in ret:
    #         field = ret[n][1]
    #         field.alias = ParamSourceAlias(n, *self._eval_param_source(params[n], field))
    #     return ret

    def get_param_src(self, param: ViewParameterInfo, field: ParamFieldInfo=None):
        field = field or param.field
        if isinstance(field, ParamFieldInfo):
            return field.param_src
        else:
            return param.annotation, field and field.alias or ... 







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




                


    
    