import os


from after import ApiClient, Service

from laza.di.injectors import MainInjector
from laza.di.common import Depends


ioc = MainInjector()

ioc.type(ApiClient)\
    .singleton()\
    .args(
        Depends(on=os.getenv, args=('API_KEY',)), 
        Depends(on=os.getenv, args=('TIMEOUT',))
    )
ioc.type(Service)


@ioc.inject
def main(service: Service):
    print(f"Got serivce {service=!r}")


if __name__ == "__main__":

    with ioc.make():
        main()
