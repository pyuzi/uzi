
from abc import ABCMeta, abstractmethod
from contextlib import nullcontext
import typing as t
import logging

from functools import partial
from collections.abc import Hashable, Iterable

from django.db import models as m, transaction
from djx.common.imports import ImportRef
from djx.common.utils.data import assign

from djx.core.models import ModelUrn
from djx.common.utils import export, lookup_property
from djx.common.metadata import metafield, BaseMetadata, get_metadata_class
from djx.schemas import GenericSchema, OrmSchema, Schema, create_schema
from pydantic.class_validators import validator
from pydantic.fields import ModelField


if t.TYPE_CHECKING:
    from djx.core.models.base import Model, Manager as _DbManager
else:
    Model = m.Model
    _DbManager = m.Manager

    

logger = logging.getLogger(__name__)

_T_Schema = t.TypeVar('_T_Schema', bound=Schema)

_T_Resource = t.TypeVar('_T_Resource', bound='Resource', covariant=True)
_T_Model = t.TypeVar('_T_Model', bound=Model, covariant=True)
_T_Key = t.TypeVar('_T_Key', str, int, t.SupportsInt, Hashable)



@export
class Resource(Hashable):

    @property
    @abstractmethod
    def urn(self):
        ...

    @classmethod
    def __subclasshook__(cls, C):
        if cls is Resource:
            return hasattr(C, '__hash__') and hasattr(C, '__eq__') and hasattr(C, 'Urn') and hasattr(C, 'urn')

        return NotImplemented


Resource.register(Model)



_config_lookup = partial(lookup_property, source='config', read_only=True)


class QueryLookups(Schema):

    def Q(self, **kwds):
        kwds.setdefault('exclude_none', True)
        dct = self.dict(**kwds)
        args = tuple(dct.pop(k) for k in tuple(dct) if isinstance(dct[k], m.Q))
        return m.Q(*args, **dct)





class ResourceSchemaDefs(OrmSchema, t.Generic[_T_Resource]):

    class Config:
        extra = 'allow'
        auto_imports = True
        validate_assignment = True
        arbitrary_types_allowed = True
        copy_on_model_validation = False
        underscore_attrs_are_private = True
        alternatives = dict(
            List=['View'],
            Embed=['List'],
            Create=['View'],
            Update=['Create'],
            Created=['View'],
        )

    Query:    type[QueryLookups] = create_schema('ResourceQueryLookups', QueryLookups, pk=(t.Union[int, str], None))
    # Search:   type[OrmSchema] = create_schema('ResourceSearchSchema', __root__=_T_Key)

    Sort:     type[OrmSchema] = None
    Paginate: type[Schema] = None

    View:      type[OrmSchema] = None
    List:      type[OrmSchema] = None
    Embed:     type[OrmSchema] = None

    Create:    type[Schema] = None
    Update:    type[Schema] = None
    
    Created:   type[OrmSchema] = None
    Updated:   type[OrmSchema] = None

    @validator('*', pre=True, always=True, allow_reuse=True)
    def _auto_import_strings(cls, v, values, field: ModelField):
        if isinstance(v, type):
            return v
        elif isinstance(v, str):
            return ImportRef(v)(v)
        elif v is None:
            for alt in cls.__config__.alternatives.get(field.name, ()):
                alt = values.get(alt)
                if alt is not None:
                    return alt
        else:
            return v




@export()
class Config(BaseMetadata['ResourceManager[_T_Resource]']):

    is_abstract = metafield[bool]('abstract', default=False)

    @metafield[type['ResourceSchemaDefs']](inherit=True)
    def SchemaDefs(self, value, base=None):
        if isinstance(self.target, type):
            if value is None:
                return base or ResourceSchemaDefs
            else:
                bases = filter(None, (value, base, (None if base is ResourceSchemaDefs else ResourceSchemaDefs)))
                class SchemaDef(*bases):
                    ...

                return SchemaDef
        else:        
            return base

    @metafield['ResourceSchemaDefs'](inherit=True)
    def schemas(self, value, base: type[Schema]=None):
        value = value and self.SchemaDefs.validate(value)
        return self.SchemaDefs.construct(**dict(base or (), **dict(value or ())))

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






@export()
class ResourceManager(t.Generic[_T_Resource]):
    """ResourceManager Object"""
    
    config: Config 
    schemas: ResourceSchemaDefs = _config_lookup('schemas')

    def __init_subclass__(cls, *, config=None) -> None:
        conf_cls = get_metadata_class(cls, '__config_class__', base=Config, name='Config')
        conf_cls(cls, 'config', cls.__dict__.get('Config') if config is None else config)

    def __init__(self, **config: t.Union[ResourceSchemaDefs, dict]) -> None:
        self._configure(config)
    
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

    def _configure(self, conf):
        base = self.__class__.config
        return base.__class__(self, 'config', conf, base)


class DbManager(m.Manager, t.Generic[_T_Model]):

    model: type[_T_Model]

    

@export()
class ModelResourceManager(ResourceManager[_T_Model]):
    """ResourceManager Object"""
    
    __slots__ = ()

    Model: type[_T_Model] = _config_lookup('model')

    def get(self, key: _T_Key, default=..., /, **kwds) -> _T_Model:
        q = self.default_q()
        if kwds:
            q = q & self.schemas.Query(**kwds).Q()
        
        try:
            return self.get_urn_class()(key).object(q=q)
        except self.Model.DoesNotExist:
            if False and self.Model.__config__.natural_keys:
                return self._get_by_natural_key(
                    self.get_db_manager().filter(q), 
                    key, default
                )
            elif default is ...:
                raise
            return default

    def get_by_natural_key(self, key: _T_Key, default=..., /, **kwds) -> _T_Model:
        q = self.default_q()
        if kwds:
            q = q & self.schemas.Query(**kwds).Q()
        return self._get_by_natural_key(
                self.get_db_manager().filter(q),
                key, default
            )

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

    def query(self, q: QueryLookups=None, ordering=None, /, **kwds) -> m.QuerySet[_T_Model]:
        q = self._to_schema(self.schemas.Query, q, **kwds)
        qs = self.get_queryset().filter(q.Q())
        return qs

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

    def _to_schema(self, typ: type[_T_Schema], val: _T_Schema=None, /, **kwds) -> _T_Schema:
        if val is None:
            return typ(**kwds)
        elif not isinstance(val, typ):
            raise TypeError(f'expected {typ} but got {type(val)}')
        elif kwds:
            return typ(**dict(val, **kwds))
        else:
            return val

    def _dump_data(self, data, default=None, /, **schema_kwds):
        if data is None:
            return default
        elif isinstance(data, dict):
            return data
        elif isinstance(data, Schema):
            return data.dict(**schema_kwds)
        else:
            return dict(data)

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
        