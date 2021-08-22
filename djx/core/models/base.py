from collections.abc import Mapping, Callable
from collections import ChainMap
from itertools import chain
from operator import or_
import typing as t


from functools import cache, cached_property, partial, reduce
from django.db import models as m
from django.contrib.postgres.fields import ArrayField

from django.db.models.functions import Now
from django.db.models.query import Prefetch

from djx.common.collections import fallbackdict
from djx.common.metadata import metafield, BaseMetadata, get_metadata_class
from djx.common.moment import Moment, moment


from djx.common.utils import (
    export, class_property, class_only_method, cached_class_property
)
from djx.common.utils.data import assign
from djx.core.models.moment import MomentField

from .urn import ModelUrn
from .alias import aliased



_T_Model = t.TypeVar('_T_Model', bound='Model', covariant=True)
_T_Config = t.TypeVar('_T_Config', bound='ModelConfig', covariant=True)




@export()
class ModelConfig(BaseMetadata[_T_Model]):

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

    # @cached_property
    # def hidden_alias_query_vars(self):

    @metafield[dict](inherit=True)
    def select_related(self, value, base=None):
        if value:
            if isinstance(value, str):
                value = { value: value }
            elif not isinstance(value, Mapping):
                value = map(lambda v: (v,v), value)
        
        return assign(dict(), base, value)

    @metafield[dict](inherit=True)
    def prefetch_related(self, value, base=None):
        if value:
            if isinstance(value, str):
                value = { value: value }
            elif not isinstance(value, Mapping):
                value = map(lambda v: (v,v), value)
        
        return assign(dict(), base, value)

    @cached_property[dict]
    def alias_query_vars(self) -> dict:
        
        val = dict()

        for i, b in enumerate(reversed(self.target.mro())):
            if issubclass(b, m.Model):
                for k, v in b.__dict__.items():
                    if isinstance(v, aliased):
                        val.setdefault(k, (i, v._order))

        return val
    
    @metafield[tuple[str]](inherit=True)
    def natural_keys(self, value, base=None):
        value = value or base
        if value is None:
            value = ()
        elif isinstance(value, str):
            value = value,
        else:
            value = tuple(value)
        return value
    
    @metafield[Callable[[t.Any], m.Q]](inherit=True)
    def natural_key_lookup(self, value, base=None):
        fn = value or base
        assert fn is None or callable(fn)
        
        if fn is None or (isinstance(fn, partial) and fn.func is _natural_key_q):
            fn = partial(_natural_key_q, self)
        return fn

    # @metafield[Callable[[t.Any], str]]('which_natural_key_fields', inherit=True)
    # def _which_natural_key_fields(self, value, base=None):
    #     return value or base

    def which_natural_key_fields(self, value, *, strict: bool=None):
        return self.which_valid_fields(value, self.natural_keys or (), strict=strict)

    def which_valid_fields(self, value, fields=None, *, strict: bool=None):
        found = bool(strict)
        if fields is None:
            fields = self.target._meta.fields
            found = True if strict is None else found

        for n in fields:
            f: m.Field = self.target._meta.get_field(n)
            try:
                f.run_validators(f.to_python(value))
            except Exception as e:
                continue
            else:
                found = True
                yield n

        if not found:
            yield from fields

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

    def _initialize_queryset(self, qs: m.QuerySet, manager):

        if rel := self.select_related:
            qs = qs.select_related(*rel.values())
            
        if rel := self.prefetch_related:
            qs = qs.prefetch_related(*rel.values())
        
        if aliases := self.get_query_aliases():
            qs = qs.alias(**aliases)
            if annot := self.get_query_annotations():
                qs = qs.annotate(**annot)

        return qs
        
    # def get_aliased_query_var(self, name):
    #     return
        
    def add_aliased_attr(self, aka: 'aliased'):

        if aka.name in self.alias_query_vars:
            return

        del self.alias_query_vars
        self.get_alias_fields.cache_clear()
        self.get_query_aliases.cache_clear()
        self.get_query_annotations.cache_clear()
        return True

    def __ready__(self):
        self._setup_timestamps()
    
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
                    ), fget=is_deleted
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
                    ), fget=will_delete
                )

    def _setup_timestamps(self):
        fields = set(self.target._meta.fields or ())
        for ts, name  in self.timestamp_fields.items():
            if name and name not in fields:
                field = getattr(self, f'make_{ts}_field')()
                field and field.contribute_to_class(self.target, name)




def _natural_key_q(self: ModelConfig, val, lookup='exact'):
    fields = self.which_natural_key_fields(val, strict=False)
    seq = (m.Q(**{f'{f}__{lookup}': val }) for f in fields)
    return reduce(or_, seq, m.Q())



@export()
class Manager(m.Manager, t.Generic[_T_Model]):

    model: type[_T_Model]
    
    if t.TYPE_CHECKING:
        def get(self, *args, **kwds) -> _T_Model:
            ...

        def get_queryset(self) -> m.QuerySet[_T_Model]:
            ...

        def get_by_natural_key(self, key) -> _T_Model:
            ...




@export()
class Model(m.Model):

    class Meta:
        abstract = True

    if t.TYPE_CHECKING:
        __config_class__: t.ClassVar[type[_T_Config]]
        __config__: t.ClassVar[ModelConfig]
        objects: t.ClassVar[Manager]
        _default_manager: t.ClassVar[Manager]
    
        created_at: Moment
        updated_at: Moment
        deleted_at: Moment

        is_deleted: bool
        will_delete: bool
        

    def __init_subclass__(cls, **kwds) -> None:
        cls._setup_model_config_()
        return super().__init_subclass__(**kwds)

    @class_only_method
    def _setup_model_config_(cls):
        conf_cls = get_metadata_class(cls, '__config_class__', base=ModelConfig, name='Config')
        return conf_cls(cls, '__config__', cls.__dict__.get('Config'))

    @class_property
    def Urn(cls) -> type[ModelUrn]:
        return ModelUrn[cls]

    @property
    def urn(self) -> ModelUrn:
        return self.Urn(self)

    if t.TYPE_CHECKING:
        Urn: t.ClassVar[type[ModelUrn]]





try:
    from mptt.models import MPTTModel
except ImportError:
    MPTTModel = m.Model


class MPTTModel(Model, MPTTModel):

    class Config:
        ...

    class Meta:
        abstract = True




try:
    from polymorphic.models import PolymorphicModel
except ImportError:
    PolymorphicModel = m.Model

@export()
class PolymorphicModel(Model, PolymorphicModel):

    class Meta:
        abstract = True




try:
    from mptt.models import MPTTModel as BaseMPTTModel
    from polymorphic_tree.models import PolymorphicMPTTModel
except ImportError:
    PolymorphicMPTTModel = BaseMPTTModel = m.Model



@export()
class PolymorphicMPTTModel(Model, PolymorphicMPTTModel, BaseMPTTModel):

    class Meta:
        abstract = True




if t.TYPE_CHECKING:
    from .alias import aliased

from . import AppModel
