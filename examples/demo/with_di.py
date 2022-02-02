import os


from after import ApiClient, Service

from laza.di.scopes import MainScope
from laza.di.common import InjectionToken, Depends, InjectedLookup


ioc = MainScope()

ENV = InjectionToken("ENV")


ioc.function(os.getenv, ENV)


ioc.type(ApiClient, deps=dict(
    api_key=Depends(on=ENV, args=('API_KEY',)), 
    timeout=Depends(on=ENV, args=('TIMEOUT',)),
))
ioc.type(Service)


@ioc.inject
def main(service: Service):
    print(f"Got serivce")


if __name__ == "__main__":

    with ioc.make() as inj:
        main()
