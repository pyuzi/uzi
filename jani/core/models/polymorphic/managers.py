import typing as t


from django.db import models as m
from jani.common.data import result


from polymorphic.managers import (
    PolymorphicManager as BasePolymorphicManager, 
    PolymorphicQuerySet as BasePolymorphicQuerySet
)
from polymorphic_tree.managers import (
    PolymorphicMPTTModelManager as BasePolymorphicMPTTModelManager, 
    PolymorphicMPTTQuerySet as BasePolymorphicMPTTQuerySet
)


from jani.common.functools import (
    export, 
)



from ..base import ModelType, Model, Manager, QuerySet, MPTTModel, MPTTModelType
from .config import  PolymorphicModelConfig


_T_Model = t.TypeVar('_T_Model', bound='Model', covariant=True)


@export()
class PolymorphicQuerySet(BasePolymorphicQuerySet):
    ...

    # def instance_of(self, *args):
    #     """Filter the queryset to only include the classes in args (and their subclasses)."""
    #     # Implementation in _translate_polymorphic_filter_defnition.
    #     return self.filter(instance_of=args)

    # def not_instance_of(self, *args):
    #     """Filter the queryset to exclude the classes in args (and their subclasses)."""
    #     # Implementation in _translate_polymorphic_filter_defnition."""
    #     return self.filter(not_instance_of=args)

    
@export()
class PolymorphicManager(BasePolymorphicManager.from_queryset(PolymorphicQuerySet), Manager):
    
    def _real_get_queryset(self):
        model = self.model
        qs = self.queryset_class(model, using=self._db, hints=self._hints)
        if model._meta.proxy:
            qs = qs.instance_of(model.__config__.polymorphic_concrete)
        return qs



@export()
class PolymorphicMPTTQuerySet(BasePolymorphicMPTTQuerySet, PolymorphicQuerySet):
    ...

    

@export()
class PolymorphicMPTTModelManager(BasePolymorphicMPTTModelManager.from_queryset(PolymorphicMPTTQuerySet), PolymorphicManager):
    ...