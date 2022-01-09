import logging
import typing as t

from django.core.handlers.asgi import ASGIHandler
from jani.di import ioc

from .core import InjectorContextHandler


logger = logging.getLogger(__name__)


class ASGIHandler(InjectorContextHandler, ASGIHandler):

    async def __call__(self, scope, receive, send) -> None:
        with self.ioc.use(self.di_scope):
            await super().__call__(scope, receive, send)
