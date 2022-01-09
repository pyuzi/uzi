
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from contextlib import nullcontext
from itertools import chain
from types import GenericAlias
import typing as t
import logging

from functools import partial
from collections.abc import Hashable, Iterable

from django.db import models as m, transaction
from jani.common.collections import orderedset, AttributeMapping
from jani.common.imports import ImportRef, ObjectImportRef

from jani.core.models import ModelUrn
from jani.common.utils import export, lookup_property, assign
from jani.common.metadata import metafield, BaseMetadata, get_metadata_class
from jani.schemas import QueryLookupSchema, OrmSchema, Schema, create_schema
from pydantic.class_validators import validator
from pydantic.fields import ModelField


if t.TYPE_CHECKING:
    from jani.core.models.base import Model, Manager as _DbManager
    from jani.schemas import BaseConfig as BaseSchemaConfig

else:
    Model = m.Model
    _DbManager = m.Manager
    BaseSchemaConfig = object



logger = logging.getLogger(__name__)


_T_Schema = t.TypeVar('_T_Schema', bound=Schema)

_T_Resource = t.TypeVar('_T_Resource', bound='Resource', covariant=True)
_T_Entity = t.TypeVar('_T_Entity', covariant=True)

_T_Model = t.TypeVar('_T_Model', bound=Model, covariant=True)
_T_Key = t.TypeVar('_T_Key', str, int, t.SupportsInt, Hashable)



@export
class ResourceType(Hashable):

    @property
    @abstractmethod
    def urn(self):
        ...

    @classmethod
    def __subclasshook__(cls, C):
        if cls is ResourceType:
            return hasattr(C, '__hash__') and hasattr(C, '__eq__') and hasattr(C, 'Urn') and hasattr(C, 'urn')

        return NotImplemented


ResourceType.register(Model)



_config_lookup = partial(lookup_property, source='config', read_only=True)


@export()
class SchemaConfig(OrmSchema, t.Generic[_T_Resource]):

    class Config(BaseSchemaConfig):
        extra = 'allow'
        auto_imports = True
        validate_assignment = True
        arbitrary_types_allowed = True
        copy_on_model_validation = False
        underscore_attrs_are_private = True
        alternatives = dict(
            View=['Base'],
            List=['View'],
            Embed=['List'],
        
            Create=['Base'],
            Update=['Create'],
            
            Created=['View'],
            Updated=['Created'],
        )

        @classmethod
        def get_alternatives(cls, *names, include_self=True, skip=None) -> None:
            skip = skip or set(names)
            for name in names:

                if include_self:
                    yield name

                for alt in cls.alternatives.get(name, ()):
                    if alt in skip or skip.add(alt):
                        continue

                    yield from cls.get_alternatives(alt, skip=skip)

                
        @classmethod
        def prepare_class(cls, klass) -> None:
            super().prepare_class(klass)

            val = defaultdict[str, orderedset](orderedset)
            for b in cls.mro():
                for k,v in (getattr(b, 'alternatives', {}) or {}).items():
                    val[k].update(v)

            cls.alternatives = dict(val)


    Base:     type[Schema] = None

    Query:    type[QueryLookupSchema] = create_schema('ResourceQueryLookups', QueryLookupSchema, pk=(t.Union[int, str], None))
    # Search:   type[OrmSchema] = create_schema('ResourceSearchSchema', __root__=_T_Key)

    Sort:     type[Schema] = None
    Paginate: type[Schema] = None

    View:      type[Schema] = None
    List:      type[Schema] = None
    Embed:     type[Schema] = None

    Create:    type[Schema] = None
    Update:    type[Schema] = None
    
    Created:   type[Schema] = None
    Updated:   type[Schema] = None

    @validator('*', pre=True, always=True, allow_reuse=True)
    def _pre_validate_schema(cls, v, values, config: Config, field: ModelField):
        if isinstance(v, str): # and v not in cls.__fields__:
            v = ObjectImportRef(v)()

        if isinstance(v, type):
            return v
        elif isinstance(v, (list, tuple)):
            alts = v
        elif v is None:
            alts = ()
        else:
            return v

        for alt in config.get_alternatives(*alts, field.name):
            if alt != field.name:
                alt = values.get(alt)
                if alt is not None:
                    return alt
    
        return v




@export()
class Config(BaseMetadata[_T_Resource], t.Generic[_T_Resource, _T_Entity]):

    is_abstract = metafield[bool]('abstract', default=False, inherit=False)

    SchemaConfig: type[SchemaConfig] = metafield(default=None, inherit=True)

    __allowextra__ = True

    __class_getitem__ = classmethod(GenericAlias)

    @metafield[type[SchemaConfig]](inherit=True)
    def schema_config_class(self, value, base=None):
        if isinstance(self.target, type):
            bases = [*{b:b for b in (value, base, self.SchemaConfig, SchemaConfig) if b}]
            class SchemaDef(*bases):
                ...

            return SchemaDef
        else:        
            return base

    @metafield[SchemaConfig](inherit=True)
    def schemas(self, value, base: SchemaConfig = None):
        rv = self.schema_config_class.validate(value or {})
        if base:
            exclude = rv.dict(exclude_defaults=True, exclude_unset=True).keys()
            base = base.dict(exclude=exclude, exclude_defaults=True, exclude_unset=True)
            assign(rv, base)
        return rv

    @metafield[type[_T_Resource]](inherit=True)
    def model(self, value, base=None):
        return value or base

    @metafield[bool](inherit=True)
    def atomic(self, value, base = None):
        return value if value is not None else bool(base)

    @metafield[bool](inherit=True)
    def atomic_create(self, value, base=None):
        return value if value is not None else base if base is not None else self.atomic

    @metafield[bool](inherit=True)
    def atomic_update(self, value, base: type[Schema]=None):
        return value if value is not None else base if base is not None else self.atomic

    @metafield[bool](inherit=True)
    def atomic_delete(self, value, base: type[Schema]=None):
        return value if value is not None else base if base is not None else self.atomic


        


BaseConfig = Config



if t.TYPE_CHECKING:

    class Schemas(t.Generic[_T_Schema]):

        __dict__: dict[str, type[_T_Schema]]

        def __getattr__(self, key: str) -> type[_T_Schema]:
            ...

        def __getattribute__(self, key: str) -> type[_T_Schema]:
            ...

@export()
class Controller(t.Generic[_T_Entity]):
    """ResourceManager Object"""
    
    config: Config 
    schemas: AttributeMapping[t.Any, type[_T_Schema]] = _config_lookup('schemas')

    class Config:
        abstract = True

    __class_getitem__ = classmethod(GenericAlias)

    def __init_subclass__(cls, *, config=None) -> None:
        conf_cls = get_metadata_class(cls, '__config_class__', base=Config, name='Config')
        cls.config = conf_cls(cls, 'config', cls.__dict__.get('Config') if config is None else config, )

    def __init__(self, config: BaseConfig = None, /, **kwds) -> None:
        self._configure(config, **kwds)
    
    def _configure(self, conf: BaseConfig = None, /, **kwds):
        # self.config = self.__class__.config.copy(target=self)
        # self.config.update(conf or (), **kwds)
        self.config = self.config.__class__(self, 'config', kwds, self.config)
        return self.config

    def _to_schema(self, typ: type[_T_Schema], val: _T_Schema=None, /, *args, **kwds) -> _T_Schema:
        if val is None:
            return typ(*args, **kwds)
        elif kwds or args:
            return typ(*args, **dict(val, **kwds))
        elif not isinstance(val, typ):
            return typ.validate(val)
        else:
            return val

    def _dump_data(self, data, default=None, /, *, to: t.Literal['dict', 'obj']='dict', **schema_kwds):
        if data is None:
            return default
        elif isinstance(data, Schema):
            if to == 'obj':
                return data.obj(**schema_kwds)
            else:
                return data.dict(**schema_kwds)
        elif to == 'obj' or isinstance(data, dict):
            return data
        else:
            return dict(data)

    if t.TYPE_CHECKING:    
        @abstractmethod
        def get(self, key: _T_Key, default=...) -> _T_Resource:
            ...

        @abstractmethod
        def create(self, obj, /, **kwds) -> _T_Resource:
            ...

        @abstractmethod
        def delete(self, obj:t.Union[_T_Resource, _T_Key]) -> bool:
            ...

        @abstractmethod
        def update(self, obj:t.Union[_T_Resource, _T_Key], *args, **kwds) -> bool:
            ...



@export()
class ModelController(Controller[_T_Model]):
    """ResourceManager Object"""
    
    __slots__ = ()

    Model: type[_T_Model] = _config_lookup('model')

    def get(self, key: _T_Key, default=..., /, **kwds) -> _T_Model:
        q = self.default_q()
        if kwds:
            q = q & self.schemas.Query(**kwds).obj()
        try:
            return self.get_urn_class()(key).object(q=q)
        except self.Model.DoesNotExist:
            if not isinstance(key, ModelUrn) and self.Model.__config__.natural_keys:
                return self._get_by_natural_key(
                    self.get_queryset(apply_default_q=False).filter(q), 
                    key, default
                )
            elif default is ...:
                raise
            return default

    def get_by_natural_key(self, key: _T_Key, default=..., /, **kwds) -> _T_Model:
        return self._get_by_natural_key(self.query(**kwds), key, default)

    def _get_by_natural_key(self, qs: m.QuerySet[_T_Model], key: _T_Key, default=...) -> _T_Model:
        try:
            if isinstance(key, self.Model):
                if qs.filter(pk=key.pk).exists():
                    return key
                raise self.Model.DoesNotExist(key.pk)
            return qs.get(self.Model.__config__.natural_key_lookup(key))
        except self.Model.DoesNotExist:
            if default is ...:
                raise
            return default

    def create(self, obj: Schema=None, /, **kwds) -> _T_Model:
        with self.get_operation_context('create'):
            return self._create(self._to_schema(self.schemas.Create, obj, **kwds))
    
    def _create(self, obj: t.Union[dict, _T_Schema], qs=None):
        if qs is None:
            qs = self.get_queryset()
        return qs.create(**self._dump_data(obj))
    
    def delete(self, obj:t.Union[_T_Resource, _T_Key]):
        with self.get_operation_context('delete'):
            return self._delete(self.get(obj))

    def _delete(self, obj: _T_Model, qs=None):
        return obj.delete()

    def update(self, obj:t.Union[_T_Resource, _T_Key], val=None, /, **kwds):
        with self.get_operation_context('update'):
            return self._update(self.get(obj), self._to_schema(self.schemas.Update, val, **kwds))

    def _update(self, obj: _T_Model, data: _T_Schema):
        assign(obj, **self._dump_data(obj, exclude_unset=True)).save()
        return obj

    def query(self, q: QueryLookupSchema=None, ordering=None, /, **kwds) -> m.QuerySet[_T_Model]:
        q = self._to_schema(self.schemas.Query, q, **kwds)
        qs = self.get_queryset().filter(q.obj())
        return qs.all()

    def get_queryset(self, *, apply_default_q: bool=True) -> m.QuerySet[_T_Model]:
        qs = self.get_db_manager().get_queryset()
        if apply_default_q is not False:
            qs = qs.filter(self.default_q())
        return qs

    def get_db_manager(self) -> _DbManager[_T_Model]:
        return self.Model._default_manager

    def default_q(self) -> m.Q:
        return m.Q()

    def get_urn_class(self) -> type[ModelUrn]:
        return self.Model.Urn

    def get_operation_context(self, op: str=None, *, atomic: bool = None):
        if atomic is None:
            atomic = self.config['atomic' if op is None else f'atomic_{op}']
        
        if atomic:
            meth = '_'.join(x for x in ('get_atomic', op, 'operation_context') if x)
            return getattr(self, meth, self.get_atomic_operation_context)()
        else:
            meth = '_'.join(x for x in ('get_non_atomic', op, 'operation_context') if x)
            return getattr(self, meth, self.get_non_atomic_operation_context)()

    def get_atomic_operation_context(self):
        return transaction.atomic()
        
    def get_non_atomic_operation_context(self):
        return nullcontext()
        