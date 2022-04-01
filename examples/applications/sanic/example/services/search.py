"""Services module."""

from sanic import Request
from .giphy import GiphyClient



class SearchService:

    giphy_client: GiphyClient

    def __init__(self, giphy_client: GiphyClient):
        self.giphy_client = giphy_client
    
    @classmethod
    def make(cls, req: Request):
        return cls(GiphyClient())

    async def asearch(self, query, limit):
        """Search for gifs and return formatted data."""
        # if not query:
        #     return []

        result =  self.giphy_client.search(query, limit)

        return  result # [{"url": gif["url"]} for gif in result["data"]]

    def search(self, query, limit):
        """Search for gifs and return formatted data."""
        # if not query:
        #     return []

        result = self.giphy_client.search(query, limit)

        return  result # [{"url": gif["url"]} for gif in result["data"]]
