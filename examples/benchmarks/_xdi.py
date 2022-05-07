
import xdi


from _bench import ALL_DEPS, SINGLETON_DEPS

LABEL = 'xdi'


ioc = xdi.Container() 

for cls in ALL_DEPS:
    if cls in SINGLETON_DEPS:
        ioc.singleton(cls)
    else:
        ioc.factory(cls)


scope = xdi.Scope[xdi.Injector](ioc)

injector = scope.injector()


def get_runner(cls):
    return injector.bound(cls)

