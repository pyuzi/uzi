"""Handlers module."""

from sanic.request import Request
from sanic.response import HTTPResponse, json

from .services.search import SearchService
from .services.giphy import GiphyClient
from .di import inject



async def aindex(
        request: Request,
        search_service: SearchService,
        gf: GiphyClient
        # default_query: str = '',
        # default_limit: int = 10,
) -> HTTPResponse:
    # query = request.args.get("query", default_query)
    # limit = int(request.args.get("limit", default_limit))

    # print('RUNINIG APP')
    gifs = await search_service.asearch('qqq', 10)
    return json(
        {
            # "query": query,
            # "limit": limit,
            # "gifs": gifs,
        },
    )


def sindex(
        request: Request,
        search_service: SearchService,
        gf: GiphyClient
        # default_query: str = '',
        # default_limit: int = 10,
) -> HTTPResponse:
    # query = request.args.get("query", default_query)
    # limit = int(request.args.get("limit", default_limit))

    # print('RUNINIG APP')
    gifs = search_service.search('qqq', 10)
    return json(
        {
            # "query": query,
            # "limit": limit,
            # "gifs": gifs,
        },
    )
