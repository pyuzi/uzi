from collections.abc import Mapping, Callable, Iterable, Set
from logging import getLogger
from operator import or_, and_
from types import MethodType, new_class
import typing as t


from functools import cache, lru_cache, reduce
from django.db import models as m
from django.core.exceptions import FieldDoesNotExist, ValidationError

from django.apps import apps
from django.db.models.functions import Now

from djx.common.collections import fallback_chain_dict, fallback_default_dict, fallbackdict, nonedict, orderedset
from djx.common.metadata import metafield, BaseMetadata
from djx.common.moment import Moment, moment


from djx.common.utils import (
    export, cached_property
)
from djx.common.utils.data import getitem, result, DataPath
from djx.core.models.moment import MomentField

from .alias import aliased


from . import AppModel

_T_Model = t.TypeVar('_T_Model', bound='Model', covariant=True)
_T_Config = t.TypeVar('_T_Config', bound='ModelConfig', covariant=True)

logger = getLogger(__name__)


if t.TYPE_CHECKING:
    from django.contrib.contenttypes.models import ContentType
    from django.db.models.fields import Field
    from django.db.models.options import Options
    from .base import Model
else:
    ContentType = AppModel('contenttypes.ContentType')




@export()
class ModelConfig(BaseMetadata[_T_Model]):

    is_prepared: bool = False
    is_polymorphic: bool = False
    __allowextra__ = True

    __cached_properties: set[str]
    __cached_methods: set[str]

    def __init_subclass__(cls) -> None:
        cls.__cached_methods = set()
        cls.__cached_properties = set()
        for k in dir(cls):
            v = getattr(cls, k, None)
            if isinstance(v, cached_property):
                cls.__cached_properties.add(k)
            elif not isinstance(v, type) and callable(v) and callable(getattr(v, 'cache_clear', None)):
                cls.__cached_methods.add(k)

        return super().__init_subclass__()

    @metafield[dict](inherit=True)
    def on_prepare(self, value, base: dict=None):
        if value:
            if isinstance(value, Mapping):
                pass
            elif isinstance(value, (str, DataPath)) or not isinstance(value, Iterable):
                value = { value : value }
            else:
                value = map(lambda v: (v if isinstance(v, tuple) else (v,v)), value)
        
        if 'on_prepare' in self.__fieldset__:
            val = self.on_prepare
        else:
            val = fallback_chain_dict(base)
        
        value and val.update(value)
        return val

    @property
    def abstract(self) -> bool:
        return self.modelmeta.abstract

    @property
    def model(self) -> type[_T_Model]:
        return self.target

    @property
    def proxy(self) -> bool:
        return self.modelmeta.proxy

    @cached_property
    def parent(self: _T_Config) -> t.Optional[_T_Config]:
        from .base import ModelType
        parents = (b.__config__ for b in self.target.__bases__ if isinstance(b, ModelType))
        return next((p for p in parents if not p.abstract), None)

    @cached_property
    def modelmeta(self) -> 'Options':
        return self.target._meta

    @metafield[bool](inherit=True)
    def timestamps(self, value, base=None) -> bool:
        return bool(base) if value is None else bool(value)

    @metafield[bool](inherit=True)
    def soft_deletes(self, value, base=None) -> bool:
        return bool(base) if value is None else bool(value)
    
    @metafield[dict[str,str]](inherit=True)
    def timestamp_fields(self, value, base=None):
        base = fallbackdict(None, base or ())
        rv = dict(base,
            created_at=base['created_at'] or self.timestamps, 
            updated_at=base['updated_at'] or self.timestamps, 
            deleted_at=base['deleted_at'] or self.soft_deletes,
            is_deleted=base['is_deleted'] or bool(base['deleted_at']) or self.soft_deletes,
            will_delete=base['will_delete'] or bool(base['deleted_at']) or self.soft_deletes,
        )

        value and rv.update(value)
        return { k: k if v is True else v for k,v in rv.items() }

    @metafield[dict[str, bool]](inherit=True)
    def tracked(self, value, base=None) -> dict[str, bool]:

        if 'tracked' in self.__fieldset__:
            val = self.tracked
        else:
            val = fallback_chain_dict(base)

        if value:
            if isinstance(value, str):
                val.update({ value: True })
            elif not isinstance(value, Mapping):
                val.update(v if isinstance(v, tuple) else (v, True) for v in value)
            else:
                val.update(value)
        return val

    @metafield
    def initial_kwargs(self, value, base=None) -> dict[str, t.Any]:
        # del self.the_inital_kwrags

        if 'initial_kwargs' in self.__fieldset__:
            val = self.initial_kwargs
        else:
            val = fallback_chain_dict(base)

        value and val.update(value)
        return val

    @metafield[dict](inherit=True)
    def initial_query(self, value, base: dict=None):
        del self.the_inital_query
        if value:
            if isinstance(value, m.Q):
                value = { value: value }
            elif not isinstance(value, Mapping):
                value = map(lambda v: (v if isinstance(v, tuple) else (v,v)), value)
        
        if 'initial_query' in self.__fieldset__:
            val = self.initial_query
        else:
            val = fallback_chain_dict(base)

        value and val.update(value)
        return val

    @metafield[dict](inherit=True)
    def select_related(self, value, base=None):
        del self.the_select_related
        if value:
            if isinstance(value, str):
                value = { value: value }
            elif not isinstance(value, Mapping):
                value = map(lambda v: (v,v), value)
        
        if 'select_related' in self.__fieldset__:
            val = self.select_related
        else:
            val = fallback_chain_dict(base)

        value and val.update(value)
        return val

    @metafield[fallback_chain_dict](inherit=True)
    def prefetch_related(self, value, base=None):
        del self.the_prefetch_related
        if value:
            if isinstance(value, str):
                value = { value: value }
            elif not isinstance(value, Mapping):
                value = map(lambda v: (v,v), value)
        
        if 'prefetch_related' in self.__fieldset__:
            val = self.prefetch_related
        else:
            val = fallback_chain_dict(base)

        value and val.update(value)
        return val

    
    @metafield(inherit=True, alias='natural_key', default=())
    def natural_keys(self, value, base=()) -> orderedset[tuple[str]]:
        if not value:
            value = orderedset()
        elif isinstance(value, str):
            value = orderedset(tuple((value,)))
        else:
            value = orderedset((v,) if isinstance(v, str) else tuple(v) for v in value)

        return value | base
    
    @metafield[Callable[[t.Any], m.Q]](inherit=True)
    def natural_key_lookup(self, value, base=None):
        fn = value or base
        assert fn is None or callable(fn)
        
        if fn is None or isinstance(fn, MethodType) and fn.__func__ is _natural_key_q:
            fn = MethodType(_natural_key_q, self)
            # fn = partial(_natural_key_q, self)
        return fn

    @cached_property
    def content_type(self):
        try:
            return ContentType.objects.get_for_model(self.target, for_concrete_model=False)
        except Exception as e:
            logger.exception(f'ContentType for {self.model} not loaded', stack_info=True)

    @cached_property
    def concrete_content_type(self):
        try:
            return ContentType.objects.get_for_model(self.target, for_concrete_model=True)
        except Exception as e:
            logger.exception(f'ContentType for {self.model} not loaded', stack_info=True)

    @cached_property[dict]
    def alias_query_vars(self) -> dict:
        
        val = dict()

        for i, b in enumerate(reversed(self.target.mro())):
            if issubclass(b, m.Model):
                for k, v in b.__dict__.items():
                    if isinstance(v, aliased):
                        val.setdefault(k, (i, v._order))

        return val
    
    @cache
    def get_alias_fields(self) -> dict[str, 'aliased']:
        attrs = map(
            (lambda x: (isinstance(v := getattr(self.target, x, ...), aliased)) and v or None),
            self.alias_query_vars
        )

        return { 
            a.attrname : a
            for a in sorted(filter(None, attrs), key=lambda x: self.alias_query_vars[x.attrname])
        }
    
    @cache
    def get_query_aliases(self) -> dict[str, t.Any]:
        return { 
            a.name : a.expr(self.target)
            for a in self.get_alias_fields().values()
        }
    
    @cache
    def get_query_annotations(self) -> dict[str, t.Any]:
        return { 
            a.name : m.F(a.name)
            for a in self.get_alias_fields().values() if a.annotate
        }
    
    @cached_property
    def tracked_attrs(self):
        fields = orderedset(f.attname for f in self.modelmeta.concrete_fields) \
            - set(f.attname if (f := self.get_field(k, None)) else k for k,v in self.tracked.items() if v is False)

        tracked = fields | orderedset(f.attname if (f := self.get_field(k, None)) else k for k,v in self.tracked.items() if v)
        return tracked

    @cached_property
    def the_inital_query(self) -> t.Optional[m.Q]:
        if self.initial_query:
            q = (
                _v if isinstance((_v := result(v, self)), m.Q) \
                    else None if _v is None else m.Q(**{ k: _v }) \
                        for k,v in self.initial_query.items()
            )
            return reduce(and_, filter(None, q), m.Q())

    @cached_property
    def the_select_related(self):
        if  self.select_related:
            return tuple(result(v, self) for v in self.select_related.values())

    @cached_property
    def the_prefetch_related(self):
        if self.prefetch_related:
            return tuple(result(v, self) for v in self.prefetch_related.values())

    @cached_property
    def the_inital_kwrags(self) -> t.Optional[dict]:
        if self.initial_kwargs:
            return { k: result(v, self) for k,v in self.initial_kwargs.items() }
        return nonedict()

    def update_init_kwargs(self, *args, **kwds):
        self.initial_kwargs = dict(*args, **kwds)
        # del self.the_inital_kwrags

    def update_inital_query(self, *args, **kwds):
        for arg in args:
            self.initial_query = arg
        self.initial_query = kwds

    @cache
    def has_field(self, name):
        return self.get_field(name, default=None) is not None

    def get_field(self, name, default=...):
        try:
            return self.modelmeta.get_field(name)
        except FieldDoesNotExist:
            if default is ...:
                raise
            return default

    def which_natural_key_fields(self, val, *, strict: bool=None):
        if self.natural_keys:
            return self.which_valid_fields(*(val if val.__class__ is tuple else (val,)), fields=self.natural_keys, strict=strict)
        else:
            return ()

    def which_valid_fields(self, *values, fields: Iterable[str]=None, flat=False, strict: bool=None):
        found = bool(strict)
        if fields is None:
            fields = self.modelmeta.fields
            found = True if strict is None else found

        if not found:
            defaults = []

        len_vals = len(values)

        get_field = self.modelmeta.get_field
        check = self._valid_field_values

        if flat:
            for fset in fields:
                if fset.__class__ is tuple:
                    if len_vals != len(fset):
                        continue
                    elif check(fset, values, get_field):
                        yield from zip(fset, values)
                        found = True
                    elif found is False:
                        defaults.extend(zip(fset, values))
                elif len_vals != 1:
                    continue
                elif check((fset,), values, get_field):
                    yield fset, values[0]
                    found = True
                elif found is False:
                    defaults.append((fset, values[0]))
        else:
            for fset in fields:
                if fset.__class__ is tuple:
                    if len_vals != len(fset):
                        continue
                    elif check(fset, values, get_field):
                        yield zip(fset, values)
                        found = True
                    elif found is False:
                        defaults.append(zip(fset, values))
                elif len_vals != 1:
                    continue
                elif check((fset,), values, get_field):
                    yield tuple((fset, values[0],))
                    found = True
                elif found is False:
                    defaults.append(((fset, values[0]),))

        if found is False:
            yield from defaults

    def _valid_field_values(self, fields: Iterable[str], values: Iterable[t.Any], get_field):
        try:
            for n, v in zip(fields, values):
                f = get_field(n)
                f.to_python(v)
        except Exception:
            return False
        else:
            return True

    def _initialize_queryset(self, qs: m.QuerySet, manager):

        if rel := self.the_select_related:
            qs = qs.select_related(*rel)
            
        if rel := self.the_prefetch_related:
            qs = qs.prefetch_related(*rel)
        
        if aliases := self.get_query_aliases():
            qs = qs.alias(**aliases)
            if annot := self.get_query_annotations():
                qs = qs.annotate(**annot)

        if q := self.the_inital_query:
            qs = qs.filter(q)

        return qs

    def set_aliased_attr(self, aka: 'aliased', *, overwrite=True):
        if overwrite is not True:
            if aka.name in self.alias_query_vars or aka.name in self.modelmeta.fields:
                return

        if hasattr(self, 'alias_query_vars'):
            del self.alias_query_vars
                
            self.get_alias_fields.cache_clear()
            self.get_query_aliases.cache_clear()
            self.get_query_annotations.cache_clear()

        return True    

    def add_aliased_attr(self, aka: 'aliased'):
        return self.set_aliased_attr(aka, overwrite=False) 

    def make_created_at_field(self):
        return MomentField(auto_now_add=True, editable=False)

    def make_updated_at_field(self):
        return MomentField(auto_now=True, editable=False)

    def make_deleted_at_field(self):
        return MomentField(null=True, default=None, db_index=True, editable=False)

    def make_is_deleted_field(self):
        look = self.timestamp_fields['deleted_at']
        aka = self.timestamp_fields['is_deleted']
        if look and aka not in self.alias_query_vars:
            def is_deleted(self):
                val: Moment = getattr(self, look, None)
                return val is not None and val <= moment.now(val.tzinfo)

            return aliased(m.Case(
                        m.When(m.Q(**{ f'{look}__lte': Now() }), m.Value(True)),
                        default=m.Value(False)
                    ), getter=is_deleted
                )

    def make_will_delete_field(self):
        look = self.timestamp_fields['deleted_at']
        aka = self.timestamp_fields['will_delete']
        if look and aka not in self.alias_query_vars:
            def will_delete(self):
                val: Moment = getattr(self, look, None)
                return val is not None and val > moment.now(val.tzinfo)

            return aliased(m.Case(
                        m.When(m.Q(**{ f'{look}__gte': Now() }), m.Value(True)),
                        default=m.Value(False)
                    ), getter=will_delete
                )

    def _setup_timestamps(self):
        if not self.modelmeta.proxy:
            bases = [self.modelmeta, *(b._meta for b in self.target.__bases__ if issubclass(b, m.Model) and b is not m.Model)]
            fields = frozenset(f.name for b in bases for f in b.local_fields)
            for ts, name  in self.timestamp_fields.items():
                if name and name not in fields:
                    field = getattr(self, f'make_{ts}_field')()
                    field and field.contribute_to_class(self.target, name)

    def __ready__(self):
        self._setup_timestamps()

        if apps.models_ready:
            self._prepare_()

    def _prepare_(self):
        if self.is_prepared: 
            raise TypeError(f'{self} already prepared')

        for p in self.__cached_properties:
            delattr(self, p)

        for m in self.__cached_methods:
            getattr(getattr(self, m), 'cache_clear')()

        self.is_prepared = True
        self._run_on_prepare()
        self.prepared()

    def _run_on_prepare(self):
        for func in self.on_prepare.values():
            if callable(func):
                func(self)
            else:
                result(getitem(self, func, None), self)

    def prepared(self) -> None:
        ...

    # TODO: Multi db support
    # def using(self, db_alias) -> _T_Config:
    #     return self

        
    @property
    def _bases_(self):
        return tuple(c for b in self.target.__bases__ if isinstance((c := getattr(b, '__config__', None)), ModelConfig))



@lru_cache(512)
def _natural_key_q(self: ModelConfig, val, *, lookup='exact'):
    fields = self.which_natural_key_fields(val, strict=False)
    seq = (m.Q(**{f'{k}__{lookup}': v for k,v in kv }) for kv in fields)
    return reduce(or_, seq, m.Q())

