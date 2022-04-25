import typing as t
import xdi

_Ta = t.TypeVar('_Ta') 
_Tb = t.TypeVar('_Tb') 

container = xdi.Container()

# a) using the helper method
container.alias(_Tb, _Ta)
# or 
# b) manually creating and attaching the provider
container[_Ta] = xdi.providers.Alias(_Ta)

obj = object()
# bind `_Ta` to a constant `obj`
container.value(_Ta, obj) 

if __name__ == '__main__':
    injector = xdi.Injector(xdi.Scope(container))

    assert obj is injector.make(_Ta) is injector.make(_Tb)
