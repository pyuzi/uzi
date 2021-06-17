import logging
import typing as t

from django.core.handlers.wsgi import WSGIHandler
from djx.di import di

from .core import InjectorContextHandler


logger = logging.getLogger(__name__)



class WSGIHandler(InjectorContextHandler, WSGIHandler):

    def __call__(self, environ, start_response):
        with self.injector():
            rv = super().__call__(environ, start_response)
        
        return rv
