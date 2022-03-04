import os


from after import ApiClient, Service

from laza.di.injectors import Injector, inject, context



@inject
def main(service: Service):
    service.do_something()



injector = Injector()

injector.factory(Service)
injector.factory(ApiClient, os.getenv("API_URL"), os.getenv('API_KEY')).singleton()



if __name__ == "__main__":

    with context(injector):
        main()
