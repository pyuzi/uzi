# XDI


[![PyPi version][pypi-image]][pypi-link]
[![Supported Python versions][pyversions-image]][pyversions-link]
[![Build status][ci-image]][ci-link]
[![Coverage status][codecov-image]][codecov-link]


`XDI` is a [dependency injection](https://en.wikipedia.org/wiki/Dependency_injection) framework for Python.

## Install

Install from [PyPi](https://pypi.org/project/xdi/)

```
pip install xdi
```

## Features

- Async support: `xdi` will `await` for you.
- Lots of Providers to choose from. E.g. [Value](basic/providers/value.md), 
[Alias](basic/providers/alias.md).
- Extensibility through `Container` inheritance.
- Multi scope support.
- Fast: minus the cost of an additional stack frame, `xdi` resolves dependencies 
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



[docs-link]: https://pyxdi.github.io/xdi/
[api-docs-link]: https://pyxdi.github.io/xdi/api/
[install-link]: https://pyxdi.github.io/xdi/install.html
[why-link]: https://pyxdi.github.io/xdi/why.html
[contributing-link]: https://pyxdi.github.io/xdi/0.5.x/contributing.html
[pypi-image]: https://img.shields.io/pypi/v/xdi.svg?color=%233d85c6
[pypi-link]: https://pypi.python.org/pypi/xdi
[pyversions-image]: https://img.shields.io/pypi/pyversions/xdi.svg
[pyversions-link]: https://pypi.python.org/pypi/xdi
[ci-image]: https://github.com/pyxdi/xdi/actions/workflows/workflow.yaml/badge.svg?event=push&branch=master
[ci-link]: https://github.com/pyxdi/xdi/actions?query=workflow%3ACI%2FCD+event%3Apush+branch%3Amaster
[codecov-image]: https://codecov.io/gh/pyxdi/xdi/branch/master/graph/badge.svg
[codecov-link]: https://codecov.io/gh/pyxdi/xdi

