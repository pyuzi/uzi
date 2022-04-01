"""Containers module."""

from collections.abc import Callable
from functools import partial, update_wrapper, wraps
from aiohttp import ClientSession
from laza.di import Injector, providers
from sanic import Request

from .services import search, giphy, T_HttpClient



injector = Injector()

# injector.factory(T_HttpClient).using(ClientSession, timeout=10)#.awaitable()

injector.provide(
    giphy.GiphyClient,
    search.SearchService
)


def inject(handler: Callable):
    if isinstance(handler, partial):
        func = handler.func
    else:
        func = handler      

    if hasattr(func, '__dependency__'):
        return handler

    provider = providers.Callable(func)

    def wrapper(req: Request, *a, **kw):
        nonlocal provider
        return req.ctx.injector_context[provider]()(req, *a, **kw)
    
    update_wrapper(wrapper, func)
    wrapper.__dependency__ = provider

    return wrapper


