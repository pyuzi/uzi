"""
Basic building blocks for generic class based views.

We don't bind behaviour to http method handlers yet,
which allows mixin classes to be composed in interesting ways.
"""
import typing as t
from rest_framework import status

from django.http import HttpRequest as Request, HttpResponse as Response

from djx.schemas import Schema
from djx.common.utils import export, assign

from .generic import GenericView, _T_Model
from ..types import HttpMethod 
from .actions import action




@export()
class CreateModelMixin(GenericView[_T_Model]):
    """
    Create a model instance.
    """
    __slots__ = ()
    class Config:
        abstract = True

    # @action(http_methods=HttpMethod.POST)
    # def create(self):
    #     obj = self.perform_create(self.parse_body())
    #     payload = self.get_payload(obj)
    #     return Response(payload.json(), content_type='application/json')

    # def perform_create(self, data: Schema):
    #     return self.get_queryset().create(**data.dict())



@export()
class ListModelMixin(GenericView[_T_Model]):
    """
    List a queryset.
    """

    __slots__ = ()
    class Config:
        abstract = True

    @action(HttpMethod.GET, detail=False)
    def list(self):
        payload = self.get_payload(list(self.objects))
        return Response(payload.json(), content_type = 'application/json')



@export()
class RetrieveModelMixin(GenericView[_T_Model]):
    """
    Retrieve a model instance.
    """
    
    __slots__ = ()
    class Config:
        abstract = True


    # @action(http_methods=HttpMethod.GET)
    # def retrieve(self):
    #     obj = self.object
    #     payload = self.get_payload(obj)
    #     return Response(payload.json(), content_type='application/json')



@export()
class UpdateModelMixin(GenericView[_T_Model]):
    """
    Update a model instance.
    """
    
    __slots__ = ()
    class Config:
        abstract = True

    
    # @action(http_methods=HttpMethod.PUT | HttpMethod.PATCH)
    # def update(self, partial=None):
    #     if partial is None:
    #         partial = self.request.method == 'PATCH'
            
    #     self.perform_update(self.object, self.parse_body(partial=partial))
    #     payload = self.get_payload(self.object)
    #     return Response(payload.json(), content_type='application/json')

    # @action(http_methods=HttpMethod.PUT | HttpMethod.PATCH)
    # def partial_update(self):
    #     return self.update(partial=True)

    # def perform_update(self, obj: _T_Model, data: Schema):
    #     obj = assign(obj, data.dict(exclude_unset=True))
    #     obj.save()
    #     return obj


@export()
class DestroyModelMixin(GenericView[_T_Model]):
    """
    Destroy a model instance.
    """
    
    __slots__ = ()
    class Config:
        abstract = True
    
    # @action(http_methods=HttpMethod.DELETE | HttpMethod.POST)
    # def destroy(self):
    #     self.perform_destroy(self.object)
    #     return Response(status=204)

    # def perform_destroy(self, obj: _T_Model):
    #     return obj.delete()



@export()
class CrudModelMixin(CreateModelMixin[_T_Model], 
                    ListModelMixin[_T_Model],
                    RetrieveModelMixin[_T_Model], 
                    UpdateModelMixin[_T_Model],
                    DestroyModelMixin[_T_Model]):
    __slots__ = ()

    class Config:
        abstract = True
    
