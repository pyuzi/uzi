"""Dependency Injector Factory providers benchmark."""

from dependency_injector import containers, providers, wiring, resources

from _bench import ALL_DEPS, SINGLETON_DEPS

LABEL = 'dep_injector'


container = containers.DynamicContainer()



def get_runner(cls):
    return getattr(container, cls.__name__)


for cls, deps in ALL_DEPS.items():
    pro_cls = (providers.Singleton if cls in SINGLETON_DEPS else providers.Factory)
    setattr(container, cls.__name__, pro_cls(cls, *(get_runner(d) for d in deps)))



