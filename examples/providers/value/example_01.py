from types import SimpleNamespace
import xdi

class Config(SimpleNamespace):
    debug: bool = False
    database: str

config = Config(debug=True, database=':memory:')

container = xdi.Container()

# a) using the helper method
container.value(Config, config) 
# or 
# b) manually creating and attaching the provider
container[Config] = xdi.providers.Value(config)


if __name__ == '__main__':
    injector = xdi.Injector(xdi.DepGraph(container))

    assert config == injector.make(Config)
    assert config is injector.make(Config)

