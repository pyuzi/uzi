import typing as t


from django.db import models as m

from polymorphic.models import PolymorphicModel
from polymorphic.managers import PolymorphicManager, PolymorphicQuerySet
from polymorphic_tree.models import PolymorphicMPTTModel, PolymorphicTreeForeignKey
from polymorphic_tree.managers import PolymorphicMPTTModelManager, PolymorphicMPTTQuerySet


from djx.common.utils import (
    export, 
)


from .config import ModelConfig
from . import AppModel, aliased

from .base import ModelType, Model, Manager, QuerySet, MPTTModel, MPTTModelType
from .config import ModelConfig, PolymorphicModelConfig


_T_Model = t.TypeVar('_T_Model', bound='Model', covariant=True)
_T_Config = t.TypeVar('_T_Config', bound='ModelConfig', covariant=True)



class PolymorphicModelType(ModelType, type(PolymorphicModel)):


    __config__: PolymorphicModelConfig

    def __call__(self, *args, **kwds):
        conf = self.__config__
        if conf.polymorphic_descendants:
            new: _T_Model = None
            if args:
                index, argmap = conf.polymorphic_args

                # debug(
                #     __create_new__=self, 
                #     polymorphic_values=conf.polymorphic_values, 
                #     argset=argmap
                # )

                new = (argmap[args[index]] or self)._from_args(args, **kwds)
            elif kwds:
                ln = len(kwds)
                kwd_maps = conf.polymorphic_kwargs

                # debug(
                #     __create_new__=self, 
                #     polymorphic_values=conf.polymorphic_values , 
                #     kwargset=kwd_maps
                # )

                for k, d in kwd_maps:
                    try:                                    
                        if ln >= len(k) and (cls := d[tuple(kwds[i] for i in k)]):
                            new = cls._from_kwargs(**kwds)
                            break
                    except KeyError:
                        pass
            
            if new is None:
                new = self._from_kwargs(**kwds)
            
        elif args:
            new = self._from_args(args, **kwds)
        else:
            new = self._from_kwargs(**kwds)
        
        new._commit_values_()
        return new

            
        #     if args:
        #         index, argmap = conf.polymorphic_args

        #         # debug(
        #         #     __create_new__=self, 
        #         #     polymorphic_values=conf.polymorphic_values, 
        #         #     argset=argmap
        #         # )

        #         if cls := argmap[args[index]]:
        #             return super(type(cls), cls).__call__(*args, **kwds)
        #     elif kwds:
        #         ln = len(kwds)
        #         cls: type[_T_Model] = None
        #         kwd_maps = conf.polymorphic_kwargs


        #         # debug(
        #         #     __create_new__=self, 
        #         #     polymorphic_values=conf.polymorphic_values , 
        #         #     kwargset=kwd_maps
        #         # )


        #         for k, d in kwd_maps:
        #             try:                                    
        #                 if ln >= len(k) and (cls := d[tuple(kwds[i] for i in k)]):
        #                     return super(type(cls), cls).__call__(*args, **kwds)
        #             except KeyError:
        #                 pass

        # return super().__call__(*args, **kwds)


    # def _from_args(self, args, **kwds) -> _T_Model:
    #     index, argmap = self.__config__.polymorphic_args

    #     # debug(
    #     #     __create_new__=self, 
    #     #     polymorphic_values=conf.polymorphic_values, 
    #     #     argset=argmap
    #     # )

    #     if cls := argmap[args[index]]:
    #         return super(cls.__class__, cls).__call__(*args, **kwds)

    # def _from_kwargs(self, **kwds) -> _T_Model:
    #     index, argmap = self.__config__.polymorphic_args

    #     # debug(
    #     #     __create_new__=self, 
    #     #     polymorphic_values=conf.polymorphic_values, 
    #     #     argset=argmap
    #     # )

    #     if cls := argmap[args[index]]:
    #         return super(type(cls), cls).__call__(*args, **kwds)




@export()
class PolymorphicModel(Model, PolymorphicModel, metaclass=PolymorphicModelType):

    __config_class__ = PolymorphicModelConfig
    __config__: PolymorphicModelConfig

    class Meta:
        abstract = True

    class Config:
        on_prepare = 'polymorphic_tree'
        
        





class PolymorphicMPTTModelType(PolymorphicModelType, MPTTModelType, type(PolymorphicMPTTModel)):
    ...





@export()
class PolymorphicMPTTModel(PolymorphicModel, PolymorphicMPTTModel, MPTTModel, metaclass=PolymorphicMPTTModelType):

    class Meta:
        abstract = True
    
    