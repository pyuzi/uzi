import os


from after import ApiClient, Service

from uzi import DepGraph, Container, Injector




def main(service: Service):
    service.do_something()



ioc = Container()

ioc.factory(Service)
ioc.singleton(ApiClient, ApiClient, os.getenv("API_URL"), os.getenv('API_KEY'))

scope = DepGraph(ioc)

if __name__ == "__main__":
    Injector(scope).make(main)
