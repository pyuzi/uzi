"""Containers module."""

from collections.abc import Callable
from functools import partial, update_wrapper, wraps
from xdi import Container, providers
from xdi.adapters.sanic import inject
from sanic import Request

from .services import search, giphy



ioc = Container()

# injector.factory(T_HttpClient).using(ClientSession, timeout=10)#.awaitable()

ioc.provide(
    giphy.GiphyClient,
    search.SearchService
)


