import typing as t


from django.db import models as m
from djx.common.utils.data import result

from polymorphic.models import PolymorphicModel as BassePolymorphicModel
from polymorphic_tree.models import PolymorphicMPTTModel, PolymorphicTreeForeignKey


from djx.common.utils import (
    export, 
)



from ..base import ModelType, Model, Manager, QuerySet, MPTTModel, MPTTModelType
from .config import  PolymorphicModelConfig

from .managers import *


_T_Model = t.TypeVar('_T_Model', bound='Model', covariant=True)




class PolymorphicModelType(ModelType, type(BassePolymorphicModel)):


    __config__: PolymorphicModelConfig

    def __call__(self, *args, **kwds):
        conf = self.__config__
        if conf.polymorphic_loading:
            if args:
                index, argmap = conf.polymorphic_args
                new = (argmap[args[index]] or self)._create_from_args_(*args, **kwds)
            elif kwds:
                ln = len(kwds)
                kwd_maps = conf.polymorphic_kwargs
                new: _T_Model = None

                for k, d in kwd_maps:
                    try:                                    
                        if ln >= len(k) and (cls := d[tuple(kwds[i] for i in k)]):
                            new = cls._create_from_kwargs_(**kwds)
                            break
                    except KeyError:
                        pass
                
            if new is None:
                new = self._create_from_kwargs_(**kwds)
            
        elif args:
            new = self._create_from_args_(*args, **kwds)
        else:
            new = self._create_from_kwargs_(**kwds)
        
        new.push_state()
        return new



@export()
class PolymorphicModel(Model, BassePolymorphicModel, metaclass=PolymorphicModelType):

    __config_class__ = PolymorphicModelConfig
    __config__: PolymorphicModelConfig

    objects = PolymorphicManager()

    class Meta:
        abstract = True

    class Config:
        on_prepare = 'polymorphic_tree'
        
        
    def pre_save_polymorphic(self, using=...):
        """
        Make sure the ``polymorphic_ctype`` value is correctly set on this model.
        """
        # This function may be called manually in special use-cases. When the object
        # is saved for the first time, we store its real class in polymorphic_ctype.
        # When the object later is retrieved by PolymorphicQuerySet, it uses this
        # field to figure out the real class of this object
        # (used by PolymorphicQuerySet._get_real_instances)
        if not self.polymorphic_ctype_id:
            self.polymorphic_ctype = result(self.__config__.polymorphic_ctype, self)

    pre_save_polymorphic.alters_data = True






class PolymorphicMPTTModelType(PolymorphicModelType, MPTTModelType, type(PolymorphicMPTTModel)):
    ...



@export()
class PolymorphicMPTTModel(PolymorphicModel, PolymorphicMPTTModel, MPTTModel, metaclass=PolymorphicMPTTModelType):

    objects = PolymorphicMPTTModelManager()

    class Meta:
        abstract = True
    
    