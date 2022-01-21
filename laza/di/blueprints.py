import typing as t


from laza.common.functools import export


from .common import Injectable, Depends, InjectionToken, InjectedLookup

from . import providers_new as p
from .container import IocContainer


@export()
class Blueprint(IocContainer):

    package: str
    provides: dict[Injectable, p.Provider]

    def __init__(self, *providers: p.Provider, package: str) -> None:
        self.package = package
        self.provides = dict()

    def get(self, key, default=None):
        return self.provides.get(key, default)

    def __contains__(self, key):
        return key in self.provides

    def __bool__(self):
        return len(self.provides)

    def __len__(self):
        return len(self.provides)

    def __iter__(self):
        return iter(self.provides)

    def __getitem__(self, key):
        return self.provides[key]

    def __setitem__(self, key, value):
        self.provides[key] = value


toke1 = InjectionToken[int]("toke1")
toke2 = InjectionToken[str]("toke2")

one = p.Function(toke1, lambda x: x + +2)
two = p.Alias(toke1)
tree = p.Type(Blueprint)

four = p.Dependency(Depends(Blueprint))

x2 = p.Object(toke2, "My foo bar is down")


bp = Blueprint(
    p.Function(toke1, lambda x: x + +2),
    p.Alias(toke1),
    p.Type(Blueprint),
    p.Dependency(Depends(Blueprint)),
    p.Object(toke2, "My foo bar is down"),
)

tokeaka1 = InjectionToken[int]("tokeaka1")


ioc = IocContainer()
    

ioc.function(toke1, lambda x: x + +2)
ioc.alias(tokeaka1, toke1)
ioc.type(Blueprint)
ioc.value(toke2, "My foo bar is down")
