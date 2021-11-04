from collections.abc import Callable
from functools import cache
from itertools import chain
from types import MappingProxyType
import typing as t


from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models as m
from django.db.models.fields.reverse_related import ForeignObjectRel

from mptt.models import MPTTModel, MPTTModelBase, TreeManager

from django.db.models.base import ModelBase, ModelState, DEFERRED
from djx.common.collections import fallbackdict, frozendict, orderedset

from djx.common.metadata import get_metadata_class
from djx.common.moment import Moment
from djx.common.proxy import proxy


from djx.common.utils import (
    export, class_property, cached_class_property
)

from .urn import ModelUrn


from .config import ModelConfig
from . import AppModel, aliased


_T_Model = t.TypeVar('_T_Model', bound='Model', covariant=True)
_T_Config = t.TypeVar('_T_Config', bound='ModelConfig', covariant=True)





if t.TYPE_CHECKING:
    
    class ModelState(ModelState):
        original: dict[str, t.Any]
        saving: bool

    @export()
    class QuerySet(m.QuerySet[_T_Model], t.Generic[_T_Model]):

        model: type[_T_Model]

        def get(self, *args, **kwds) -> _T_Model:
            ...
    
    @export()
    class Manager(m.Manager[_T_Model], t.Generic[_T_Model]):

        model: type[_T_Model]
    
        def get(self, *args, **kwds) -> _T_Model:
            ...

        def get_queryset(self) -> m.QuerySet[_T_Model]:
            ...

        def get_by_natural_key(self, key) -> _T_Model:
            ...
else:
    QuerySet = export(m.QuerySet)
    Manager = export(m.Manager)



_pending_models = orderedset()


def _prepare_pending_models():
    global _pending_models
    
    pending = _pending_models
    if apps.models_ready:
        _pending_models = None

    for model in pending:
        if not model.__config__.is_prepared:
            model.__config__._prepare_()



def _prepare_model(model: type['Model']):
    global _pending_models

    if apps.models_ready or _pending_models is None:
        if not model.__config__.is_prepared:
            model.__config__._prepare_()
    else:
        _pending_models.add(model)
    




class ModelType(ModelBase):

    __config__: 'ModelConfig'
    __create_new__: t.Union[Callable[[type[_T_Model], tuple, dict], _T_Model], bool]


    def __new__(mcls, name, bases, attrs):
        attrs.update(__config__=None)
        cls = super().__new__(mcls, name, bases, attrs)
        cls._setup_model_config_()
        _prepare_model(cls)
        return cls

    def _setup_model_config_(self) -> 'ModelConfig':
        if self.__config__ is None:
            conf_cls = get_metadata_class(self, '__config_class__', base=ModelConfig, name='Config')
            self.__config__ = conf_cls(self, '__config__', self.__dict__.get('Config'))
        return self.__config__

    def __call__(self, *args, **kwds):
        if args:
            rec = self._create_from_args_(*args, **kwds)
        else:
            rec = self._create_from_kwargs_(**kwds)
        rec.push_state()
        return rec

    if t.TYPE_CHECKING:
        def _create_from_args_(self, *args, **kwds) -> _T_Model:
            ...
            
    _create_from_args_ = ModelBase.__call__

    def _create_from_kwargs_(self, **kwds) -> _T_Model:
        if init := self.__config__.the_inital_kwrags:
            kwds = dict(init, **kwds)

        # vardump(_create_from_kwargs_=self, the_inital_kwrags=init, kwds=kwds)

        return ModelBase.__call__(self, **kwds)

    def _from_db(self: type[_T_Model], db, field_names, values) -> _T_Model:
        concrete_fields = self._meta.concrete_fields
        if len(values) != len(concrete_fields):
            values_iter = iter(values)
            values = (
                next(values_iter) if f.attname in field_names else DEFERRED
                for f in concrete_fields
            )
        
        new = self.__call__(*values)
        new._state.adding = False
        new._state.db = db
        return new




class _originals(frozendict):

    __slots__ = ()

    def __missing__(self, k):
        if isinstance(k, str):
            return ...
        raise KeyError(k)




@export()
class Model(m.Model, metaclass=ModelType):
    class Config:
        ...
    class Meta:
        abstract = True

    if t.TYPE_CHECKING:
        __config_class__: t.ClassVar[type[_T_Config]]
        __config__: t.ClassVar[ModelConfig]
        objects: t.ClassVar[Manager]
        _default_manager: t.ClassVar[Manager]
        _base_manager: t.ClassVar[Manager]
    
        created_at: Moment
        updated_at: Moment
        deleted_at: Moment

        is_deleted: bool
        will_delete: bool
        
        _state: 'ModelState'

    @classmethod
    def from_db(cls: type[_T_Model], db, field_names, values):
        return cls._from_db(db, field_names, values)

    @class_property
    def Urn(cls) -> type[ModelUrn]:
        return ModelUrn[cls]

    @property
    def urn(self) -> ModelUrn:
        return self.Urn(self)

    if t.TYPE_CHECKING:
        Urn: t.ClassVar[type[ModelUrn]]

# __init__
    # def __init__(self, *args, **kwargs):
    #     # Alias some things as locals to avoid repeat global lookups
    #     cls = self.__class__
    #     opts = self._meta
    #     _setattr = setattr
    #     _DEFERRED = DEFERRED
    #     if opts.abstract:
    #         raise TypeError('Abstract models cannot be instantiated.')

    #     m.signals.pre_init.send(sender=cls, args=args, kwargs=kwargs)

    #     # Set up the storage for instance state
    #     self._state = ModelState()

    #     # There is a rather weird disparity here; if kwargs, it's set, then args
    #     # overrides it. It should be one or the other; don't duplicate the work
    #     # The reason for the kwargs check is that standard iterator passes in by
    #     # args, and instantiation for iteration is 33% faster.
    #     if len(args) > len(opts.concrete_fields):
    #         # Daft, but matches old exception sans the err msg.
    #         raise IndexError("Number of args exceeds number of fields")

    #     if not kwargs:
    #         fields_iter = iter(opts.concrete_fields)
    #         # The ordering of the zip calls matter - zip throws StopIteration
    #         # when an iter throws it. So if the first iter throws it, the second
    #         # is *not* consumed. We rely on this, so don't change the order
    #         # without changing the logic.
    #         for val, field in zip(args, fields_iter):
    #             if val is _DEFERRED:
    #                 continue
    #             _setattr(self, field.attname, val)
    #     else:
    #         # Slower, kwargs-ready version.
    #         fields_iter = iter(opts.fields)
    #         for val, field in zip(args, fields_iter):
    #             if val is _DEFERRED:
    #                 continue
    #             _setattr(self, field.attname, val)
    #             kwargs.pop(field.name, None)

    #     # Now we're left with the unprocessed fields that *must* come from
    #     # keywords, or default.

    #     for field in fields_iter:
    #         is_related_object = False
    #         # Virtual field
    #         if field.attname not in kwargs and field.column is None:
    #             continue
    #         if kwargs:
    #             if isinstance(field.remote_field, ForeignObjectRel):
    #                 try:
    #                     # Assume object instance was passed in.
    #                     rel_obj = kwargs.pop(field.name)
    #                     is_related_object = True
    #                 except KeyError:
    #                     try:
    #                         # Object instance wasn't passed in -- must be an ID.
    #                         val = kwargs.pop(field.attname)
    #                     except KeyError:
    #                         val = field.get_default()
    #             else:
    #                 try:
    #                     val = kwargs.pop(field.attname)
    #                 except KeyError:
    #                     # This is done with an exception rather than the
    #                     # default argument on pop because we don't want
    #                     # get_default() to be evaluated, and then not used.
    #                     # Refs #12057.
    #                     val = field.get_default()
    #         else:
    #             val = field.get_default()

    #         if is_related_object:
    #             # If we are passed a related instance, set it using the
    #             # field.name instead of field.attname (e.g. "user" instead of
    #             # "user_id") so that the object gets properly cached (and type
    #             # checked) by the RelatedObjectDescriptor.
    #             if rel_obj is not _DEFERRED:
    #                 _setattr(self, field.name, rel_obj)
    #         else:
    #             if val is not _DEFERRED:
    #                 _setattr(self, field.attname, val)

    #     if kwargs:
    #         property_names = opts._property_names

    #         vardump(property_names)

    #         for prop in tuple(kwargs):
    #             try:
    #                 # Any remaining kwargs must correspond to properties or
    #                 # virtual fields.
    #                 if prop in property_names or opts.get_field(prop):
    #                     if kwargs[prop] is not _DEFERRED:
    #                         _setattr(self, prop, kwargs[prop])
    #                     del kwargs[prop]
    #             except (AttributeError, FieldDoesNotExist) as e:
    #                 vardump(prop, property_names, e)
                
    #                 pass
            
    #         # vardump(kwargs, property_names)

    #         for kwarg in kwargs:
    #             raise TypeError("%s() got an unexpected keyword argument '%s'" % (cls.__name__, kwarg))

    #     # super().__init__()
        
    #     m.signals.post_init.send(sender=cls, instance=self)
#

    def save(self, *args, **kwds):
        state = self._state
        state.saving = True
        try:
            super().save(*args, **kwds)
        except:
            raise
        else:
            self.push_state()
        finally:
            state.saving = False

    def is_dirty(self, *keys):
        return any(self.get_dirty(*keys))

    def get_original(self, key: str=..., default=...):
        if key is ...:
            return self._state.original

        val = self._state.original[key]
        if val is ... is (val := default):
            raise KeyError(key)
        return val

    def get_dirty(self, *keys: str):
        dct = self.__dict__
        get = dct.get
        get_orig = self._state.original.__getitem__
        track = self.__config__.tracked_attrs

        if keys:
            track = track & keys 

        for key in track:
            if get(key, ...) != get_orig(key):
                yield key

    def push_state(self):
        dct = self.__dict__
        track = self.__config__.tracked_attrs
        
        state = self._state
        state.saving = False
        state.original = _originals((k, dct.get(k, ...)) for k in track)
        return self

    def __getstate__(self):
        """Hook to allow choosing the attributes to pickle."""
        state = super().__getstate__()
        delattr(state['_state'], 'original')
        return state

    def __setstate__(self, state):
        super().__setstate__(state)
        self.push_state()
    


        
        
@export()
class MPTTModelType(ModelType, MPTTModelBase):
    pass


class MPTTModel(Model, MPTTModel, metaclass=MPTTModelType):

    class Config:
        ...

    class Meta:
        abstract = True




from .polymorphic import PolymorphicModel, PolymorphicMPTTModel, PolymorphicModelConfig
from . import _patch as __
