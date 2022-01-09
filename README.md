# JANI Common

A Python Development Toolkit



## Install

Basic install
```
    pip install [pkg]
```

Full install. Installs all optional dependencies.
```
    pip install Jani-Common[all]
```


#### Optional Dependencies


The following features/modules have additional dependecies that you might need to install:-

- `json` which requires `orjson`
    ```
    pip install Jani-Common[json]
    ```
- `locale` which requires `babel`
    ```
    pip install Jani-Common[locale]
    ```
- `moment` which requires `arrow`
    ```
    pip install Jani-Common[moment]
    ```
- `money` which requires `py-moneyed`
    ```
    pip install Jani-Common[money]
    ```
- `networks` which requires `pydantic[email]`
    ```
    pip install Jani-Common[networks]
    ```
- `phone` which requires `phonenumbers`
    ```
    pip install Jani-Common[phone]
    ```

or you can pick a set
```
pip install Jani-Common[phone,json,money]
```


- `money` : install `pip install Jani-Common[money]`
- `networks` : install `pip install Jani-Common[networks]`
- `phone` : install `pip install Jani-Common[phone]`
- or install all: `pip install Jani-Common[all]`



[pkg]: Jani-Common
