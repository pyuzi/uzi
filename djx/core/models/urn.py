from abc import ABCMeta
import logging
import typing as t

from weakref import ref
from cachetools.ttl import TTLCache
from cachetools.lfu import LFUCache
from functools import cache, partial
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db import models as m

from djx.common.collections import PriorityStack, fallbackdict

from djx.di import di, ordered_id
from djx.core import settings
from djx.common.imports import ImportRef
from djx.common.proxy import unproxy, proxy
from djx.common.utils import (
    export, text, getitem, class_property, cached_class_property, setdefault, 
    class_only_method
)


_T_Pk = t.TypeVar('_T_Pk')
_T_Model = t.TypeVar('_T_Model', bound=m.Model, covariant=True)
_T_Urn = t.TypeVar('_T_Urn', bound='ModelUrn', covariant=True)

_ModelType = type(m.Model)


logger = logging.getLogger(__name__)

_DEBUG = settings.DEBUG


if t.TYPE_CHECKING:
    from django.contrib.contenttypes.models import ContentType
else:
    ContentType = proxy(
            ImportRef('django.contrib.contenttypes.models', 'ContentType'), 
            cache=True
        ) 
    
_ctypes = proxy(lambda: ContentType.objects, cache=True) 


# def ctype_from_ns_s

@cache
def _get_ns_string(cls: type[_T_Urn]) -> t.Optional[str]:
    if model := cls.model:
        return getattr(cls.model, '__urn_namespace__', None) or str(cls.content_type.pk)

# namespace_model_map

@proxy(cache=True, callable=True)
def _namespace_map() -> fallbackdict[t.Any, type[_T_Model]]:
    nsmap: fallbackdict[t.Any, type[_T_Model]]

    def _fallback(key):
        if isinstance(key, int) or (isinstance(key, str) and key.isdigit()):
            try:
                model = _ctypes.get_for_id(int(key)).model_class()
            except ContentType.DoesNotExist as e:
                raise KeyError(key) from e
            else:
                return nsmap.setdefault(key, model)
        elif isinstance(key, str):
            try:
                model = apps.get_model(key)
            except LookupError as e:
                raise KeyError(key) from e
            else:
                return nsmap.setdefault(key, model)
        else:
            raise KeyError(key)
    

    nsmap = fallbackdict(_fallback)

    for m in apps.get_models():
        if ns := getattr(m, '__urn_namespace__', None):
            if ns in nsmap: # and not issubclass(m, nsmap[ns]):
                raise ImproperlyConfigured(
                    f'duplicate model urn namespace string {ns} in {nsmap[ns]} and {m}'
                )
            nsmap[ns] = m
    
    return nsmap


if t.TYPE_CHECKING:
    _namespace_map: fallbackdict[t.Any, type[_T_Model]] = fallbackdict()


def _clean_urn_object_cache(sig: str, sender, instance, created=False, **kwds):
    if not settings.IS_SETUP:
        if not created:
            try:
                if urn := ModelUrn._remove_from_cache(instance):
                    logger.info(f'{urn=!r} removed from cache on {sig!r} from {sender}. {instance=!r}.')
            except Exception as e:
                logger.exception(f'Error removing {instance} from cache', exc_info=1, stack_info=1)
                # raise e


m.signals.pre_save.connect(partial(_clean_urn_object_cache, 'pre_save'))
m.signals.pre_delete.connect(partial(_clean_urn_object_cache, 'pre_delete'))



@export()
class ModelUrnTypeError(TypeError):
    code = 'urn.model'
    msg_template = 'invalid urn type'


@export()
class ModelUrnValueError(ValueError):
    code = 'urn.model'
    msg_template = 'invalid urn.'
    
    


@di.injectable('main', cache=True, kwargs=dict(maxsize=1024, ttl=300))
class ModelUrnObjectCache(TTLCache):

    def __init__(self, **kwds) -> None:
        super().__init__(**kwds) 





@export()
class ModelUrn(str, t.Generic[_T_Model]):
    """Globally unique id for db models across the database.
    Usually defaults to `rec:{content_type_id}:{object_pk} and can be accessed 
    via the `gpk` or `gid` model attributes.
    """

    __slots__ = ()

    __cache: t.ClassVar[ModelUrnObjectCache] = di.InjectedClassVar(ModelUrnObjectCache)
    __type_map: t.ClassVar[PriorityStack[tuple, type['ModelUrn']]] = PriorityStack()
    _pos: t.ClassVar[int] = ordered_id()

    model: t.ClassVar[type[_T_Model]] = None
    fieldname: t.ClassVar[str] = 'pk'
    scheme: t.ClassVar[str] = 'rec'
    ns_string: t.ClassVar[str] = None

    def __init_subclass__(cls, *, model=None, fieldname=None, scheme=None) -> None:
        cls.scheme = scheme = cls.scheme if scheme is None else scheme
        cls.model = model = cls.model if model is None else model
        cls.fieldname = fieldname = cls.fieldname if fieldname is None else fieldname

        assert model is None or isinstance(model, _ModelType)
        assert fieldname is None or isinstance(fieldname, str)

        # cls._pos = ordered_id()
                
        if model is not None and model.__module__ == cls.__module__:
            if cls.__qualname__ == cls.__name__:
                setdefault(ImportRef(model.__module__)(), cls.__name__, cls)

        if model is not None and fieldname is not None:
            if fieldname in {'pk', model._meta.pk.name}:
                key = model
            else:
                key = model, fieldname

            ModelUrn.__type_map.append(key, cls)
            
        return super().__init_subclass__()

    def __class_getitem__(cls, params: t.Union[type[m.Model], tuple[type[m.Model], str]]):
        klass = ModelUrn.__type_map.get(params)
        if klass is None:

            if isinstance(params, tuple):
                if len(params) == 3:
                    key = '.'.join(params[:2]), params[2]
                elif len(params) == 1:
                    if cls.model is None:
                        key = params[0], cls.fieldname
                    else:
                        key = cls.model, params[0]
                else:
                    key = params
            else:
                key = params, cls.fieldname

            if isinstance(key[0], t.TypeVar):
                return super().__class_getitem__(params)

            if isinstance(key[0], str):
                key = _namespace_map[key[0]], key[1]

            model, fieldname = key
            if fieldname in {'pk', model._meta.pk.name}:
                fieldname = 'pk'
                key = model
            
            if not cls._is_related_model(model):
                raise ModelUrnTypeError(f'{cls} to {model}.')

            klass = ModelUrn.__type_map.get(key)
            if klass is None:
                base = getattr(cls, '__urn_class__', None) or cls
                assert issubclass(base, ModelUrn)
                klass = ModelUrn.__type_map.setdefault(key, type(
                    text.uppercamel(f'{model.__name__}{"" if fieldname == "pk" else f"_{fieldname}"}_urn'), 
                    (base,), dict(
                        __module__ = model.__module__,
                        model = model,
                        fieldname = fieldname
                    )
                ))

        elif not cls._is_related_type(klass):
            raise ModelUrnTypeError(f'{cls} to {klass}.')

        # elif _DEBUG:
        #     logger.info(f'ModelUrn[{params}] HIT')

        return klass

    def __new__(cls, val: t.Union[_T_Model, _T_Pk, str, 'ModelUrn']) -> 'ModelUrn':
        val = unproxy(val)
        if (typ := type(val)) is cls:
            return val

        obj = None
        if typ is str and val.startswith(cls.scheme):
            ns_str, key = val[len(cls.scheme)+1:].split(':', 1)
            try:
                model = _namespace_map[ns_str]
            except KeyError as e:
                raise ModelUrnValueError(f'{val!r}') from e
            else:
                cls = cls[model]  
        elif isinstance(typ, _ModelType):
            if cls.model is not typ:
                cls = cls[typ]

            obj = val
            key = cls._get_key_from_object(obj)     
        elif issubclass(typ, ModelUrn):
            if cls.model is None:
                return val
            elif cls._is_related_type(typ):
                if val.fieldname != cls.fieldname:
                    key = getitem(val.object(), cls.key_path)
                else:
                    key = val.key
            else:
                raise ModelUrnTypeError(f'{cls} is not compatible to {typ}')
            obj = ModelUrn.__cache.get(val)
        elif cls.model:
            if isinstance(val, (list, tuple)):
                key = '/'.join(map(str, val))
            elif val not in {'', None}:
                key = val
            else:
                raise ModelUrnValueError(f'invalid urn key')    
        else:
            raise ModelUrnValueError(f'invalid urn')

        rv = cls._new_(key)

        if obj is not None:
            ModelUrn.__cache[rv] = obj
        elif rv in ModelUrn.__cache:
            try:
                # touch the cached object if any.
                ModelUrn.__cache[rv]
            except KeyError:
                pass
        
        return rv

    @class_property
    def content_type(cls) -> ContentType:
        return cls.model and _ctypes.get_for_model(cls.model, for_concrete_model=True)

    @cached_class_property
    def key_path(cls) -> str:
        return cls.fieldname and cls.fieldname.replace('__', '.')

    @class_property
    def concrete_model(cls) -> type[m.Model]:
        return cls.model and cls.model._meta.concrete_model

    @cached_class_property
    def namespace(cls) -> str:
        if cls.model is not None:
            return _get_ns_string(cls)
        return None

    @class_property
    def origin(cls) -> str:
        return f'{cls.scheme}:{cls.namespace}'

    @property
    def key(self) -> str:
        return self[len(self.origin)+1:]

    @class_only_method
    def _is_related_type(cls, typ: type['ModelUrn']) -> bool:
        if typ is cls:
            return True
        elif typ.model is None:
            return issubclass(typ, cls)

        return cls._is_related_model(typ.model)

    @class_only_method
    # @cache
    def _is_related_model(cls, typ: type[m.Model]) -> bool:
        model = unproxy(cls.model)
        if model is None:
            return True
        elif issubclass((typ := unproxy(typ)), model) or issubclass(model, typ):
            return True
        return False

    @class_only_method
    def _get_key_from_object(cls, obj):
        key = getitem(obj, cls.key_path)
        if isinstance(key, (list, tuple)):
            key = '/'.join(map(str, key))
        return key

    @class_only_method
    def _new_(cls: type[_T_Urn], key, __new__: t.Callable[[type[_T_Urn], str], _T_Urn] = None) -> _T_Urn:
        return (__new__ or str.__new__)(cls, f'{cls.origin}:{key}')

    @class_only_method
    def _remove_from_cache(cls, obj: _T_Model, *, flush: bool = None) -> t.Optional[_T_Urn]:
        typ = type(obj)
        if cls.model is None:
            _cls = cls[typ]
        elif cls.model is not typ:
            _cls = cls[typ]
        else:
            _cls = cls
        
        flush is False or ModelUrn.__cache.expire()

        urn = _cls._new_(_cls._get_key_from_object(obj))
        if ModelUrn.__cache.pop(urn, None) is not None:
            return urn
        
    @classmethod
    def _get_object_queryset(cls) -> None:
        return cls.model._default_manager.get_queryset()
    
    def object(self, default=..., *, q: m.Q=None, fresh: bool=False) -> _T_Model:
        cache = ModelUrn.__cache
        ck = (self, q) if q else self

        if fresh:
            rv = cache.pop(ck, None) and None
        else:
            rv = cache.get(ck)
        
        if rv is None:
            try:
                rv = self.fetch_object(q=q)
            except self.model.DoesNotExist as e:
                if default is ...:
                    raise e
                rv = default
            else:
                cache[ck] = rv
        return rv

    def fetch_object(self, default=..., *, q: m.Q=None) -> _T_Model:
        try:
            qs = self._get_object_queryset()
            if q: qs = qs.filter(q) 
            if isinstance(qs, SupportsGetByUrn):
                return qs.get_by_urn(self)
            else:
                return qs.get(**{self.fieldname:self.key})       
        except self.model.DoesNotExist as e:
            if default is ...:
                raise e
            return default

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        return cls(v)

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, t.Any]) -> None:
        field_schema.update(type='string', example=f'{cls.scheme}:{cls.namespace or "type"}:123')




class SupportsGetByUrn(metaclass=ABCMeta):

    @classmethod
    def __subclasshook__(cls, C):
        if cls is SupportsGetByUrn:
            return hasattr(C, 'get_by_urn') and callable(C.get_by_urn)
        return NotImplemented
