# Basic Usage


**`XDI`** is a [dependency injection](https://en.wikipedia.org/wiki/Dependency_injection) library for Python.



## Installation

Install from [PyPi](https://pypi.org/project/xdi/)

```shell
pip install xdi
```

``` mermaid
graph LR
    A --> |A0| A;
    A --> |A1| B;
    A --> |A2| C;
    A --> |A3| H;
    A --> |A4| D;

    B --> |B0| B;
    B --> |B1| C;
    B --> |B2| D;
    B --> |B3| E;

    C --> |C0| C;
    C --> |C1| D;
    C --> |C2| F;
    C --> |C3| E;
    C --> |C4| G;

    D --> |D0| D;
    D --> |D1| G;

    E --> |E0| E;
    F --> |E0| F;
    G --> |G0| G;
    H --> |H0| H;

```

