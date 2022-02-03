import os


from after import ApiClient, Service

from laza.di.injectors import MainScope
from laza.di.common import Depends


ioc = MainScope()

ioc.type(ApiClient, shared=True, deps=dict(
    api_key=Depends(on=os.getenv, args=('API_KEY',)), 
    timeout=Depends(on=os.getenv, args=('TIMEOUT',)),
))
ioc.type(Service)


@ioc.inject
def main(service: Service):
    print(f"Got serivce {service=!r}")


if __name__ == "__main__":

    with ioc.make():
        main()
