from collections.abc import Callable
from functools import cache
from itertools import chain
import typing as t


from django.apps import apps
from django.db import models as m

from mptt.models import MPTTModel, MPTTModelBase, TreeManager

from django.db.models.base import ModelBase, ModelState, DEFERRED
from djx.common.collections import orderedset

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


from . import _patch as __



if t.TYPE_CHECKING:
    
    class ModelState(ModelState):
        orig: dict[str, t.Any]

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

        debug(
            __create_new__=self, 
            argset=args[:4]
        )

        if args:
            rec = self._from_args(args, **kwds)
        else:
            rec = self._from_kwargs(**kwds)
        rec._commit_values_()
        return rec

        # if not args:
        #     if _kw := self.__config__.the_inital_kwrags:
        #         kwds = {**_kw, **kwds}
        
        # # debug(_create_new_=self, inital_kwargs=self.__config__.the_inital_kwrags, args=args and args[:2], kwds=kwds)
        # rec: _T_Model = super().__call__(*args, **kwds)
        # return rec


    def _from_args(self, args, **kwds) -> _T_Model:
        return super().__call__(*args, **kwds)

    def _from_kwargs(self, **kwds) -> _T_Model:
        
        # debug(
        #     __create_new__=self, 
        #     polymorphic_values=conf.polymorphic_values, 
        #     argset=argmap
        # )

        if init := self.__config__.the_inital_kwrags:
            kwds = dict(init, **kwds)

        return super().__call__(**kwds)

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

    def save(self, *args, **kwds):
        if hasattr(self, '_on_polymorphic_save_'):
            self._on_polymorphic_save_()
        super().save(*args, **kwds)
        self._commit_values_()

    def is_dirty(self, *keys):
        return next(self._dirty(*keys), False) is not False

    def dirty(self, *keys: str):
        return self._dirty(*keys)

    def _dirty(self, *keys: str):
        dct = self.__dict__
        orig = self._state.orig
        for key in (keys or (k for k in dct if k[:1] != '_')):
            if key in dct:
                if key in orig:
                    if dct[key] != orig[key]:
                        yield key
                else:
                    yield key
            elif key in orig:
                yield key

    def _commit_values_(self, *keys):
        dct = self.__dict__
        self._state.orig = {k: dct[k] for k in dct if k[:1] != '_'}

    def __getstate__(self):
        """Hook to allow choosing the attributes to pickle."""
        state = super().__getstate__()
        state['_state'].orig = None
        return state

    def __setstate__(self, state):
        super().__setstate__(state)
        self._commit_values_()
    


        
        
@export()
class MPTTModelType(ModelType, MPTTModelBase):
    pass


class MPTTModel(Model, MPTTModel, metaclass=MPTTModelType):

    class Config:
        ...

    class Meta:
        abstract = True




from .polymorphic import PolymorphicModel, PolymorphicMPTTModel, PolymorphicModelConfig