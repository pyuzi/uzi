"""Giphy client module."""

from datetime import datetime
from . import T_HttpClient



class GiphyClient:

    API_URL = "https://api.giphy.com/v1"
    
    # _http_client: T_HttpClient

    def __init__(self):
        # self._http_client = http_client 
        self.ts = datetime.now()

    def search(self, query, limit):
        """Make search API call and return result."""
        url = f"{self.API_URL}/gifs/search"
        params = {
            "q": query,
            "time": self.ts.isoformat(' ', 'seconds'),
            # "api_key": self._api_key,
            "limit": limit,
        }
        
        return params
        # async with ClientSession(timeout=5) as session:
        #     async with session.get(url, params=params) as response:
        #         if response.status != 200:
        #             response.raise_for_status()
        #         return await response.json()

        #     print('XXXXXXXXXXXXXXXXXSXXXXXX')