# Key Concepts

Before we start, it would be good to introduce some core concepts used in `uzi` and  
across this documentation.


### Dependencies 

A dependency is an object which other objects require (depend on).  
In `uzi` a dependency is identified by it's `type`, a `TypeVar` or a `DependencyMarker`.

### Providers

Providers define how a dependency is resolved. We use them to determine what  
happens when a dependency is requested.  
For example, they determine whether...  
  - to create a new instance of dependency `x` for each request or to share one instance.
  - to uses a predefined constant or proxy another existing dependency and provide its value instead.
   
### Containers

Containers are mappings of dependencies to their providers. We use them to bind  
dependencies to their providers.  
To allow for better modularity, containers can also [include other containers]().
  
### Scopes

These are isolated dependency resolution contexts created from a set of containers.
Scopes assemble the dependency graphs of dependencies registered in their containers.

### Injectors

These are isolated dependency injection contexts for our scopes. 
They are responsible for assembling the object graphs of dependencies in a given scope.

