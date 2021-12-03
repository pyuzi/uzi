"""
Basic building blocks for generic class based views.

We don't bind behaviour to http method handlers yet,
which allows mixin classes to be composed in interesting ways.
"""
import typing as t
from rest_framework import status
from collections.abc import Hashable, Iterable
from django.http import HttpRequest as Request, HttpResponse as Response

from djx.schemas import Schema
from djx.common.utils import export, assign
from djx.core.models import base as m

from .core import View, action
from .config import GenericViewConfig
from ..types import ContentShape, HttpStatus 

from .actions import action

_T_Model = t.TypeVar('_T_Model', m.Model, t.Any, covariant=True)


@export()
class GenericView(View[_T_Model]):
    """ResourceManager Object"""
    
    __slots__ = '_params', '_obj', '_objs', '_qs',

    # _data: t.Final[_T_Data]
    _params: t.Final[t.Any]

    _obj: t.Final[_T_Model]
    _objs: t.Final[t.Union[m.QuerySet[_T_Model], Iterable[_T_Model]]]

    # Model: type[_T_Model] = _config_lookup('model')

    __config_class__ = GenericViewConfig
    
    config: GenericViewConfig  # type: ignore

    __config__: GenericViewConfig # type: ignore

    @property
    def objects(self) -> m.QuerySet[_T_Model]:
        """
        The list of filtered items for this view.
        
        This must be an iterable, and may be a queryset.
        Override `self._get_objects()`.

        """
        try:
            return self._objs
        except AttributeError:
            self._objs = self._get_objects().all()
            return self._objs

    @objects.setter
    def objects(self, val):
        self._objs = val

    @property
    def object(self) -> _T_Model:
        """
        The current object for this request.
        
        This must be an iterable, and may be a queryset.
        Override `self._get_objects()`.

        """
        try:
            return self._obj
        except AttributeError:
            self._obj = self._get_object()
            return self._obj
            
    @object.setter
    def object(self, val):
        self._obj = val

    @property
    def params(self):
        """
        Get the list of items for this view.
        This must be an iterable, and may be a queryset.
        Defaults to using `self.queryset`.

        Override `self._get_queryset()` if you need to provide different
        querysets depending on the incoming request.
        """
        try:
            return self._params
        except AttributeError:
            self._params = self.parse_params()
            return self._params

    def filter_queryset(self, queryset: m.QuerySet[_T_Model]):
        """
        Given a queryset, filter it with whichever filter backend is in use.

        You are unlikely to want to override this method, although you may need
        to call it either from a list view, or from a custom `get_object`
        method if you want to apply the configured filtering backend to the
        default queryset.
        """

        req = self.request
        for pp in self.config.filter_pipeline:
            queryset = pp.filter_queryset(req, queryset, self)
        return queryset

    def get_queryset(self) -> m.QuerySet[_T_Model]:
        """
        Create the list of items for this view.
        This must be an iterable, and may be a queryset.
        Defaults to using `self.config.queryset`.

        You may want to override this if you need to provide different
        querysets depending on the incoming request.

        (Eg. return a list of items that is specific to the user)
        """
        
        queryset = self.config.queryset
        if isinstance(queryset, m.QuerySet):
            # Ensure queryset is re-evaluated on each request.
            queryset = queryset.all()
        return queryset

    def _get_objects(self) -> m.QuerySet[_T_Model]:
        """
        Returns the sequence of filtered objects for this request.
        Must be an iterable, and may be a queryset.
        Defaults to using filtered `self.queryset`.

        You may want to override this if you need to provide non-standard iterables.
        """
        return self.filter_queryset(self.get_queryset())

    def _get_object(self):
        """
        Returns the object the view is displaying.

        You may want to override this if you need to provide non-standard
        queryset lookups.  Eg if objects are referenced using multiple
        keyword arguments in the url conf.
        """
        conf = self.config
        return self.objects.get(**{ conf.lookup_field: self.kwargs[conf.lookup_url_kwarg or conf.lookup_field]})





@export()
class CreateModelView(GenericView[_T_Model]):
    """
    Create a model instance.
    """
    __slots__ = ()
    class Config:
        abstract = True

    @action(outline=True, status=HttpStatus.CREATED_201, shape=ContentShape.blank)
    def post(self, *args, **kwds):
        self.object = self.perform_create(self.parse_body())
    
    def perform_create(self, data: Schema):
        return self.get_queryset().create(**data.dict())



@export()
class ListModelView(GenericView[_T_Model]):
    """
    List a queryset.
    """

    __slots__ = ()
    class Config:
        abstract = True

    @action(outline=True)
    def get(self, *args, **kwds):
        return list(self.objects)



@export()
class RetrieveModelView(GenericView[_T_Model]):
    """
    Retrieve a model instance.
    """
    
    __slots__ = ()
    class Config:
        abstract = True

    @action(detail=True)
    def get(self, *args, **kwds):
        return self.object



@export()
class ReadModelView(GenericView[_T_Model]):
    """
    Retrieve a model instance.
    """
    
    __slots__ = ()
    class Config:
        abstract = True

    @action(detail=True, outline=True)
    def get(self, *args, **kwds):
        if self.config.detail:
            return self.object
        else:
            return list(self.objects)



@export()
class UpdateModelView(GenericView[_T_Model]):
    """
    Update a model instance.
    """
    
    __slots__ = ()
    class Config:
        abstract = True

    @action(detail=True)
    def put(self,  *args, **kwds):
        self.perform_update(self.object, self.parse_body())
        
    @action(detail=True)
    def patch(self, *args, **kwds):
        self.perform_update(self.object, self.parse_body(partial=True))
    
    def perform_update(self, obj: _T_Model, data: Schema):
        obj = assign(obj, data.dict(exclude_unset=True))
        return obj


@export()
class DestroyModelView(GenericView[_T_Model]):
    """
    Destroy a model instance.
    """
    
    __slots__ = ()
    class Config:
        abstract = True
    
    @action(status=HttpStatus.NO_CONTENT_204, detail=True)
    def delete(self, *args, **kwds):
        self.perform_destroy(self.object)
        return Response(status=204)

    def perform_destroy(self, obj: _T_Model):
        return obj.delete()



@export()
class WriteModelView(CreateModelView[_T_Model], 
                    UpdateModelView[_T_Model],
                    DestroyModelView[_T_Model]):
    
    __slots__ = ()

    class Config:
        abstract = True
    


@export()
class ReadWriteModelView(ReadModelView[_T_Model], WriteModelView[_T_Model]):
    __slots__ = ()
    class Config:
        abstract = True
    
