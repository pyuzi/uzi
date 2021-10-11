from collections.abc import Mapping, Callable, Iterable, Set
from logging import getLogger
from operator import index, or_, and_
from types import MethodType, new_class
import typing as t


from functools import cache, lru_cache, reduce
from django.db import models as m
from django.core.exceptions import FieldDoesNotExist, ValidationError

from django.apps import apps
from django.db.models.functions import Now

from djx.common.collections import fallback_chain_dict, fallback_default_dict, fallbackdict, none_dict, orderedset, result_fallback_chain_dict
from djx.common.metadata import metafield, BaseMetadata
from djx.common.moment import Moment, moment
from djx.common.proxy import ValueProxy


from djx.common.utils import (
    export, cached_property, Missing
)
from djx.common.exc import ImproperlyConfigured
from djx.common.utils.data import assign, getitem, result, DataPath
from djx.core.models.moment import MomentField
from djx.schemas import fields

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



class _PolymorphicValue(t.NamedTuple('_PolymorphicFieldValue', [('field', '_PolymorphicField'), ('value', t.Any)])):

    __slots__ = ()

    # field: '_PolymorphicField'
    # value: t.Any
    _field_attrs = frozenset(( 'index', 'alias', 'name', 'attname', 'root'))

    root: type[_T_Model]
    alias: str
    name: str
    attname: str
    
    index: int
    field: 'Field'

    def __getattr__(self, name):
        if name in self._field_attrs:
            return getattr(self.field, name)
        raise AttributeError(name)

    def __gt__(self, o) -> bool:
        if isinstance(o, _PolymorphicValue):
            return self.field > o.field
        return self.field > o
    
    def __ge__(self, o):
        return self.__gt__(o) or self.__eq__(o)

    def __lt__(self, o) -> bool:
        if isinstance(o, _PolymorphicValue):
            return self.field < o.field
        return self.field < o

    def __le__(self, o):
        return self.__lt__(o) or self.__eq__(o)



def _new_polymorphic_field_class(typ: type[_T_Model]) -> '_PolymorphicField[_T_Model]':
    return new_class(f'_{typ.__name__}PolymorphicField', (_PolymorphicField[_T_Model],), None, lambda ns: ns.update(root=typ))


class _PolymorphicField(t.Generic[_T_Model]):

    __slots__ = 'index', 'alias', 'field', '_hash',

    root: type[_T_Model]
    alias: str
    name: str
    attname: str
    
    index: int
    field: 'Field'

    __by_root = fallback_default_dict[type[_T_Model], type['_PolymorphicField[_T_Model]']](_new_polymorphic_field_class)

    def __class_getitem__(cls, params):
        if isinstance(params, tuple):
            typ = params[0]
        else:
            typ = params
        
        if isinstance(typ, type):
            _cls = cls.__by_root[typ] 
            return super(cls, _cls).__class_getitem__(params)

        return super().__class_getitem__(params)

    def __new__(cls, field, index=None, alias=None) -> None:
        if field.__class__ is cls:
            field = field.field

        self = super().__new__(cls)
        self.field = field
        self.alias = alias or field.name
        self.index = index
        return self

    def value(self, v):
        # return _PolymorphicValue(self,  v.pk if self.is_relation and isinstance(v, m.Model) else v)
        return _PolymorphicValue(self,  v)

    def __eq__(self, o):
        typ = o.__class__
        if issubclass(typ, _PolymorphicField):
            return self.index.__eq__(o.index) \
                and (issubclass(o.root, self.root) or issubclass(self.root, o.root))
        elif typ is str:
            return self.alias.__eq__(o)
        elif typ is int:
            return self.index.__eq__(o)
        else:
            return (self.root, self.index).__eq__(o)

    def __reduce__(self):
        return self.__class__, (self.field, self.index, self.index)
    
    def __gt__(self, o) -> bool:
        typ = o.__class__
        if issubclass(typ, _PolymorphicField):
            return self.index.__gt__(o.index)
        elif typ is str:
            return self.alias.__gt__(o)
        else:
            return self.index.__gt__(o)
        # else:
        #     return (self.root._meta, self.index).__gt__(o)

        # return NotImplemented
    
    def __ge__(self, o):
        return self.__gt__(o) or self.__eq__(o)

    def __lt__(self, o) -> bool:
        typ = o.__class__
        if issubclass(typ, _PolymorphicField):
            return self.index.__lt__(o.index)
        elif typ is str:
            return self.alias.__lt__(o)
        else:
            return self.index.__lt__(o)
        # else:
        #     return (self.root, self.index).__lt__(o)

        # return NotImplemented
    
    def __le__(self, o):
        return self.__lt__(o) or self.__eq__(o)
    
    def __hash__(self) -> int:
        try:
            return self._hash
        except AttributeError:
            self._hash = hash((self.root, self.index))
            return self._hash
    
    def __getattr__(self, name):
        if name != '_hash':
            return getattr(self.field, name)
        raise AttributeError(name)
    
    def __int__(self) -> int:
        return self.index

    def __str__(self) -> str:
        return self.alias



if t.TYPE_CHECKING:
    class _PolymorphicField(Field, _PolymorphicField):
        ...



@export()
class ModelConfig(BaseMetadata[_T_Model]):

    is_prepared: bool = False
    is_polymorphic: bool = False

    __cached_properties: set[str]

    def __init_subclass__(cls) -> None:
        cls.__cached_properties = set()
        for k in dir(cls):
            if isinstance(getattr(cls, k, None), cached_property):
                cls.__cached_properties.add(k)
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

    @metafield
    def initial_kwargs(self, value, base=None) -> dict[str, t.Any]:
        # del self.the_inital_kwrags

        if 'initial_kwargs' in self.__fieldset__:
            val = self.initial_kwargs
        else:
            val = fallback_chain_dict(base)

        value and val.update(value)
        return val

    # @metafield
    # def default_kwargs(self, value, base=None) -> dict[str, t.Any]:
    #     if 'default_kwargs' in self.__fieldset__:
    #         val = self.default_kwargs
    #     else:
    #         val = fallback_chain_dict(base)

    #     value and val.update(value)
    #     return val

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
        return ContentType.objects.get_for_model(self.target, for_concrete_model=False)

    @cached_property
    def concrete_content_type(self):
        return ContentType.objects.get_for_model(self.target, for_concrete_model=True)


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

    # @cached_property
    # def the_default_kwrags(self) -> t.Optional[dict]:
    #     if self.initial_kwargs:
    #         return { k: result(v, self) for k,v in self.initial_kwargs.items() }

    @cached_property
    def the_inital_kwrags(self) -> t.Optional[dict]:
        debug(self.model, self.initial_kwargs)
        if self.initial_kwargs:
            return { k: result(v, self) for k,v in self.initial_kwargs.items() }
        return none_dict()

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
                f.run_validators(f.to_python(v))
        except (TypeError, ValueError, ValidationError):
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
            debug(initialize_queryset=qs.model, target=self.target, the_inital_query=q)
            qs = qs.filter(q) #.distinct()

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
        pass
    
    @property
    def _bases_(self):
        return tuple(c for b in self.target.__bases__ if isinstance((c := getattr(b, '__config__', None)), ModelConfig))



@lru_cache(512)
def _natural_key_q(self: ModelConfig, val, *, lookup='exact'):
    fields = self.which_natural_key_fields(val, strict=False)
    seq = (m.Q(**{f'{k}__{lookup}': v for k,v in kv }) for kv in fields)
    return reduce(or_, seq, m.Q())




@export()
class PolymorphicModelConfig(ModelConfig):

    is_polymorphic: bool = True

    # @metafield
    # def initial_kwargs(self, value, base=None) -> dict[str, t.Any]:
    #     if 'initial_kwargs' in self.__fieldset__:
    #         val = self.initial_kwargs
    #     elif base:
    #         val = fallback_chain_dict(base)
    #     else:
    #         val = fallback_chain_dict(self._get_polymorphic_inital_kwargs())

    #     value and val.update(value)
    #     return val

    @metafield
    def polymorphic_ctype_field_name(self, value, base=None):
        return value or base or 'polymorphic_ctype'

    @property
    def polymorphic_ctype_value(self):
        return self.content_type

    @metafield
    def polymorphic_on(self, value, base=None) -> t.Optional[fallback_chain_dict[str, t.Any]]:
        if not base:
            base = { self.polymorphic_ctype_field_name : lambda s: s.polymorphic_ctype_value }
        
        return fallback_chain_dict(base, value or ())

    @cached_property
    def polymorphic_values(self) -> dict[str, t.Any]:
        if not self.abstract:
            if raw := self.polymorphic_on:
                rv = { k: result(raw[k], self) for k in raw }
                return rv

    @cached_property
    def polymorphic_ctype_field(self):
        if fields := self.polymorphic_fields:
            if name := self.polymorphic_ctype_field_name:
                for field in fields:
                    if field.alias == name:
                        return field

    @cached_property[t.Optional['ModelConfig']]
    def polymorphic_base(self) -> t.Optional['ModelConfig']:
        if not self.abstract and self.is_polymorphic:
            if self.proxy:
                return self.parent and self.parent.polymorphic_base
            else:
                return self

    @cached_property[t.Optional['ModelConfig']]
    def polymorphic_root(self) -> t.Optional['ModelConfig']:
        if not self.abstract and self.is_polymorphic:
            if self.parent and self.parent.is_polymorphic:
                return self.parent.polymorphic_root
            else:
                return self

    @cached_property
    def polymorphic_descendants(self) -> int:
        count = 0
        for typ in self.polymorphic_types.values():
            if typ is not self.target:
                count += 1
        return count

    @cached_property
    def polymorphic_fields(self) -> t.Union[orderedset[_PolymorphicField], None]:
        if not self.abstract:
            if values := self.polymorphic_on:
                fields: list[_PolymorphicField] = []
                fieldset = [f.attname for f in self.modelmeta.concrete_fields]

                fcls = _PolymorphicField[self.polymorphic_root.target]

                for name in values:
                    field = self.get_field(name, None)
                    if field is None:
                        aka = self.get_alias_fields().get(name)
                        if aka and aka.lookup_path:
                            field = self.get_field(aka.lookup_path.lookup, None)
                    
                    if field is None:
                        raise ValueError(f'polymorphic field {name!r} does not exist in {self.target}')

                    fields.append(fcls(field, fieldset.index(field.attname), name))
                
                return orderedset(sorted(fields))

    @cached_property
    def polymorphic_key(self) -> t.Union[tuple[_PolymorphicValue], None]:
        if fields := self.polymorphic_fields:
            vals = self.polymorphic_values
            return tuple(f.value(v) for f in fields if (v := vals[f.alias]) is not ...) or None
    
    @cached_property
    def polymorphic_args(self) -> dict[tuple[int], dict[tuple[t.Any], type[_T_Model]]]:
        if self.polymorphic_descendants:
            if types := self.polymorphic_types:
                ct_field = self.polymorphic_ctype_field

                ctypes  = fallbackdict()

                for k in types:
                    if keys := tuple(f for f in k if f.field == ct_field):
                        kf = keys[0]
                        val = kf.value.pk if kf.field.is_relation and isinstance(kf.value, m.Model) else kf.value
                        ctypes[val] = types[k]
                    
                return ct_field.index, ctypes
        
    @cached_property
    def polymorphic_kwargs(self) -> dict[tuple[str], dict[tuple[t.Any], type[_T_Model]]]:
        if self.polymorphic_descendants:
            if types := self.polymorphic_types:
                kwargmaps  = fallback_default_dict(fallbackdict)
                ct_field = self.polymorphic_ctype_field

                ctypes = kwargmaps[(ct_field.alias,)]
                for k in types:
                    if keys := tuple(f for f in k if f.field == ct_field):
                        ctypes[keys[0].value] = types[k]

                skip = {ct_field, *(f.field for f in self.polymorphic_key or ())}
                
                for k in types:
                    if keys := tuple(f for f in k if f.field not in skip):
                        key = tuple(f.field.alias for f in keys)
                        val = tuple(f.value for f in keys)
                        kwargmaps[key][val] = types[k]

                return tuple(kwargmaps.items())
        
    @cached_property
    def polymorphic_types(self) -> t.Optional[dict[tuple[_PolymorphicValue], type[_T_Model]]]:
        if tree := self.polymorphic_tree:
            if self is self.polymorphic_root:
                val = tree
            else:
                val = {k : v for k,v in tree.items() if issubclass(v, self.target)}

            return { k:val[k] for k in sorted(val, key=lambda k: tuple([-len(k), *k])) }

    @cached_property
    def polymorphic_tree(self) -> t.Optional[dict[tuple[_PolymorphicValue], type[_T_Model]]]:
        if  self.polymorphic_fields:
            root = self.polymorphic_root
            key = self.polymorphic_key
            if root is self:
                tree = dict()
            else:
                tree = root.polymorphic_tree

            if key:
                tree[key] = self.target
                vals = self.polymorphic_values
                self.initial_kwargs = { k.field.alias:  vals[k.field.alias] for k in key }

            return tree

    # def _get_polymorphic_inital_kwargs(self):
    #     def _make():
    #         return { k: v
    #             for k, v in self.polymorphic_values.items()
    #                 if v is not ...
    #         }

    #     return _make()
    # @staticmethod
    # def _polymorphic_query(conf: 'ModelConfig'):
    #     return
    #     if types := conf.polymorphic_types:
    #         args = types
    #         if key := conf.polymorphic_key:
    #             args = (k for k in args if k == key)

    #         # else:
    #         #     args = types

    #         # debug(__self__=conf, __polymorphic_types__=conf.polymorphic_types)

    #         looks = fallback_default_dict(lambda k: orderedset())

    #         for keys in args:
    #             for key in keys:
    #                 looks[f'{key.field.alias}__in'].add(key.value)

    #         return m.Q(**looks)        

    #         # qset = orderedset(m.Q(**{p.field.alias: p.value for p in pt}) for pt in args)
    #         # return reduce(or_, (q & ~reduce(or_, qset-(q,), m.Q()) for q in qset), m.Q())

    #         # return reduce(or_, (m.Q(**{p.field.alias: p.value for p in pt}) for pt in args), m.Q())
    #         # return reduce(or_, (m.Q(**{p.field.alias: p.value for p in pt}) for pt in types), m.Q())

