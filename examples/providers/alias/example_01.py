import typing as t
import uzi

_Ta = t.TypeVar('_Ta') 
_Tb = t.TypeVar('_Tb') 

container = uzi.Container()

# a) using the helper method
container.alias(_Tb, _Ta)
# or 
# b) manually creating and attaching the provider
container[_Ta] = uzi.providers.Alias(_Ta)

obj = object()
# bind `_Ta` to a constant `obj`
container.value(_Ta, obj) 

if __name__ == '__main__':
    injector = uzi.Injector(uzi.DepGraph(container))

    assert obj is injector.make(_Ta) is injector.make(_Tb)
