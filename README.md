# JANI Common

A Python Development Toolkit



## Install

Basic install
```
    pip install laza-di
```

Full install. Installs all optional dependencies.
```
    pip install laza-di[all]
```

What describes a good DI container#
A good DI container:

* __must not__ be a Service Locator, and that’s easier to get as one might think, just go back to my previous post about this topic
* __must not__ be configurable globally (as a globally available instance), because it introduces problems with the reconfiguration
* __must support__ shared dependencies, so we wouldn’t need to exploit the Singleton Pattern
* __must support__ use of profiles, so we can configure it accordingly on different environments
* __should support__ the Decorator Pattern


## Modularity
The ability to isolate deps within their modules/packages
