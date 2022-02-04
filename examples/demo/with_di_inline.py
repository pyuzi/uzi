import os

from laza.di.injectors import MainInjector
from laza.di.common import Depends as Dep



ioc = MainInjector()


@ioc.type(shared=True)\
    .args(1,2,3)\
    .kwargs(api_key='KEY')\
    .singleton()\
    .using()
class ApiClient:

    def __init__(self, 
                api_key: str = Dep(..., os.getenv, 'API_KEY'), 
                timeout: int = Dep(..., os.getenv, 'TIMEOUT')):
        self.api_key = api_key  # <-- dependency is injected
        self.timeout = timeout  # <-- dependency is injected


@ioc.type
class Service:

    def __init__(self, api_client: ApiClient):
        self.api_client = api_client  # <-- dependency is injected


@ioc.inject
def main(service: Service):
    print(f"Got serivce {service=!r}")


if __name__ == "__main__":

    with ioc.make():
        main()
