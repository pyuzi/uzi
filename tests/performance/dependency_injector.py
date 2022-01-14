"""Dependency Injector Factory providers benchmark."""

import time

from dependency_injector import providers
from dependency_injector import containers
from dependency_injector import wiring

from laza.di import ioc


N = int(5e4)


@ioc.injectable()
class A(object):
    pass
    # def __init__(self):
    #     self.a = a


@ioc.injectable(cache=True)
class B(object):
    pass



@ioc.injectable(cache=True)
class C(object):
    def __init__(self, a: A, b: B):
        self.a = a
        self.b = b


@ioc.injectable()
class Service(object):
    def __init__(self, a: A, b: B, c: C):
        self.a = a
        self.b = b
        self.c = c


class Container(containers.DeclarativeContainer):
    
    wiring_config = containers.WiringConfiguration(modules=[__name__])

    a = providers.Factory(A)
    b = providers.Singleton(B)
    c = providers.Singleton(C, a, b)

    service = providers.Factory(
        Service,
        a, b, c
    )


@wiring.inject
def dinj_client(service: Service=wiring.Provide['service']):
    sev = service
        


@ioc.wrap()
@ioc.injectable()
def ioc_client(service: Service):
    sev = service
        
inj = ioc.injector

service_maker = lambda: inj[Service]

def simple_service_provider():
    return Service(a=A(), b=B(), c=C())


container = Container()
container.wiring_config

class Test:

    def test_performace(self, speed_profiler):
        profile = speed_profiler(N, labels=('DIJ', 'IOC'))
        profile(Container.service, service_maker, 'Simple')
        profile(dinj_client, ioc_client, 'Inject')
        print('--')

        profile = speed_profiler(N, labels=('IOC', 'DIJ'))
        profile(service_maker, Container.service, 'Simple')
        profile(ioc_client, dinj_client, 'Inject')

        assert 0



# Testing simple analog

# ------
# Result
# ------
#
# Python 2.7
#
# $ python tests/performance/factory_benchmark_1.py
# 0.87456202507
# 0.879760980606
#
# $ python tests/performance/factory_benchmark_1.py
# 0.949290990829
# 0.853044986725
#
# $ python tests/performance/factory_benchmark_1.py
# 0.964688062668
# 0.857432842255
#
# Python 3.7.0
#
# $ python tests/performance/factory_benchmark_1.py
# 1.1037120819091797
# 0.999565839767456
#
# $ python tests/performance/factory_benchmark_1.py
# 1.0855588912963867
# 1.0008318424224854
#
# $ python tests/performance/factory_benchmark_1.py
# 1.0706679821014404
# 1.0106139183044434
