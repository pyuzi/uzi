
from typing import ClassVar, Generic, Type, TypeVar
from django.db import models
from django.db.models import Manager, Model

from jani.common.utils import export

from rest_framework.generics import GenericAPIView as BaseGenericAPIView
from rest_framework.views import APIView as BaseAPIView



from .base import View

M = TypeVar('M', bound=Model)


@export()
class ModelView(View, Generic[M]):
    """GenericView Object"""

    manager: Manager

    @property
    def model(self) -> Type[M]:
        return self.manager.model

    def get_queryset(self):
        pass

    def get_object(self):
        pass

    def get_query(self):
        pass
