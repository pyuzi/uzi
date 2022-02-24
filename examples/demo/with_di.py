import os


from after import ApiClient, Service

from laza.di.injectors import Injector
from laza.di.common import Depends


ioc = Injector()

ioc.factory(ApiClient)\
    .singleton()\
    .args(
        Depends(on=os.getenv, args=('API_KEY',)), 
        Depends(on=os.getenv, args=('TIMEOUT',))
    )
ioc.factory(Service)


@ioc.inject
def main(service: Service):
    print(f"Got serivce {service=!r}")


if __name__ == "__main__":

    with ioc.make():
        main()
