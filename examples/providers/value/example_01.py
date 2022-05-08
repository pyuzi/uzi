from types import SimpleNamespace
import uzi

class Config(SimpleNamespace):
    debug: bool = False
    database: str

config = Config(debug=True, database=':memory:')

container = uzi.Container()

# a) using the helper method
container.value(Config, config) 
# or 
# b) manually creating and attaching the provider
container[Config] = uzi.providers.Value(config)


if __name__ == '__main__':
    injector = uzi.Injector(uzi.DepGraph(container))

    assert config == injector.make(Config)
    assert config is injector.make(Config)

