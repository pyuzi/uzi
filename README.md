# Uzi


[![PyPi version][pypi-image]][pypi-link]
[![Supported Python versions][pyversions-image]][pyversions-link]
[![Build status][ci-image]][ci-link]
[![Coverage status][codecov-image]][codecov-link]


`Uzi` is a [dependency injection](https://en.wikipedia.org/wiki/Dependency_injection) framework for Python.

## Install

Install from [PyPi](https://pypi.org/project/uzi/)

```
pip install uzi
```

## Features

- Async support: `uzi` will `await` for you.
- Lots of Providers to choose from. E.g.
[Value](https://pyuzi.github.io/uzi/basic/providers/value.html), 
[Alias](https://pyuzi.github.io/uzi/basic/providers/alias.html).
- Extensibility through `Container` inheritance.
- Multi scope support.
- Fast: minus the cost of an additional stack frame, `uzi` resolves dependencies 
nearly as efficiently as resolving them by hand.


## Links

- __[Documentation][docs-link]__
- __[API Reference][api-docs-link]__
- __[Installation][install-link]__
- __[Get Started][why-link]__
- __[Contributing][contributing-link]__



## Production

This package is currently under active development and is not recommended for production use.

Will be production ready from version `v1.0.0` onwards.



[docs-link]: https://pyuzi.github.io/uzi/
[api-docs-link]: https://pyuzi.github.io/uzi/api/
[install-link]: https://pyuzi.github.io/uzi/install.html
[why-link]: https://pyuzi.github.io/uzi/why.html
[contributing-link]: https://pyuzi.github.io/uzi/0.5.x/contributing.html
[pypi-image]: https://img.shields.io/pypi/v/uzi.svg?color=%233d85c6
[pypi-link]: https://pypi.python.org/pypi/uzi
[pyversions-image]: https://img.shields.io/pypi/pyversions/uzi.svg
[pyversions-link]: https://pypi.python.org/pypi/uzi
[ci-image]: https://github.com/pyuzi/uzi/actions/workflows/workflow.yaml/badge.svg?event=push&branch=master
[ci-link]: https://github.com/pyuzi/uzi/actions?query=workflow%3ACI%2FCD+event%3Apush+branch%3Amaster
[codecov-image]: https://codecov.io/gh/pyuzi/uzi/branch/master/graph/badge.svg
[codecov-link]: https://codecov.io/gh/pyuzi/uzi

