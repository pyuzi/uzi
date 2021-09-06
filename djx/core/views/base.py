import logging
from functools import update_wrapper

from typing import Any, ClassVar, FrozenSet, Generic, Mapping, Optional, Sequence, Set, final
from django.views import View
from django.http import HttpRequest, HttpResponse
from django import http


from djx.core.http import HttpMethod

from djx.common.utils import export, cached_class_property, class_only_method
from djx.common.metadata import metafield, BaseMetadata, get_metadata_class



__all__ = [

]


logger = logging.getLogger('djx.request')



@export()
class ViewConfig(BaseMetadata['View']):

    is_abstract = metafield('abstract', default=False, inherit=False)

    @metafield(inherit=True)
    def actions(self, value, base=None) -> None:
        pass
    
    # @metafield(inherit=True)
    # def alt_methods(self, value, base=None) -> dict:
    #     rv = dict(base or())
    #     value and rv.update(value)
    #     if 'head' not i
    


@export()
class ViewType(type):

    def __new__(mcls, name, bases, dct):

        raw_conf = dct.get('Config')
                
        meta_use_cls = raw_conf and getattr(raw_conf, '__use_class__', None)
        meta_use_cls and dct.update(__config_class__=meta_use_cls)

        cls = super().__new__(mcls, name, bases, dct)

        conf_cls = get_metadata_class(cls, '__config_class__')
        cls._conf = conf_cls(cls, '_conf', raw_conf)

        return cls





@export()
class View(View, metaclass=ViewType):

    request: HttpRequest
    args: Sequence[Any]
    kwargs: Mapping[str, Any]

    class Config:
        __use_class__ = ViewConfig
        abstract = True

    @cached_class_property
    @final
    def allowed_methods(cls):
        return cls.get_allowed_http_methods()

    @class_only_method
    def as_view(cls, **initkwargs):
        """Main entry point for a request-response process."""
        for key in initkwargs:
            if key.upper() in cls.allowed_methods:
                raise TypeError(
                    'The method name %s is not accepted as a keyword argument '
                    'to %s().' % (key, cls.__name__)
                )
            if not hasattr(cls, key):
                raise TypeError("%s() received an invalid keyword %r. as_view "
                                "only accepts arguments that are already "
                                "attributes of the class." % (cls.__name__, key))

        def view(req, *args, **kwds):
            self: View = cls(**initkwargs)
            self.setup(req, *args, **kwds)
            if not hasattr(self, 'request'):
                raise AttributeError(
                    "%s instance has no 'request' attribute. Did you override "
                    "setup() and forget to call super()?" % cls.__name__
                )
            return self.teardown(res := self.dispatch(req, *args, **kwds)) or res

        view.view_class = cls
        view.view_initkwargs = initkwargs

        # take name and docstring from class
        update_wrapper(view, cls, updated=())

        # and possible attributes set by decorators
        # like csrf_exempt from dispatch
        update_wrapper(view, cls.dispatch, assigned=())
        return view

    @classmethod
    def get_allowed_http_methods(cls):
        rv = {m: m.lower() for m in HttpMethod if hasattr(cls, m.lower())}
        HttpMethod.GET in rv and rv.setdefault(HttpMethod.HEAD, 'get')
        return rv
    
    def setup(self, request, *args, **kwargs):
        """Initialize attributes shared by all view methods."""
        self.request = request
        self.args = args
        self.kwargs = kwargs

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        # Try to dispatch to the right method; if a method doesn't exist,
        # defer to the error handler. Also defer to the error handler if the
        # request method isn't on the approved list.
        if action := self.allowed_methods.get(request.method):
            handler = getattr(self, action, self.http_method_not_allowed)
        else:
            handler = self.http_method_not_allowed

        try:
            return handler(request, *args, **kwargs)
        except Exception as e:
            return self.handle_exception(e)
            
    def handle_exception(self, exc):
        raise exc
   
    def teardown(self, response) -> Optional[HttpResponse]:
        return response

    def http_method_not_allowed(self, request, *args, **kwargs) -> HttpResponse:
        logger.warning(
            'Method Not Allowed (%s): %s', request.method, request.path,
            extra={'status_code': 405, 'request': request}
        )
        return http.HttpResponseNotAllowed(self.allowed_methods)

    def options(self, request, *args, **kwargs):
        """Handle responding to requests for the OPTIONS HTTP verb."""
        response = HttpResponse()
        response['Allow'] = ', '.join(self.allowed_methods)
        response['Content-Length'] = '0'
        return response

