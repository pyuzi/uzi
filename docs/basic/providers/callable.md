
# Callable Provider


Provides a partial callable to a function, class, method or any other callable type

```python linenums="1" hl_lines="20 21 22 23 24 25 27 28 29 30 31 32 33"
import typing as t
from xdi import Container, providers


_T_PasswordHasher = t.TypeVar("_T_PasswordHasher", bound=t.Callable[[str], str])


def hash_password(
    password: str,
    salt: str,
    rounds: int = 5000,
    algo: t.Literal["sha256", "sha512", "md5"] = "md5",
):
    return "hashed_password"


container = Container()


container[_T_PasswordHasher] = providers.Callable(
    hash_password, 
    salt="my-secret", 
    rounds=1000, 
    algo="sha256"
)
# or use the helper method
container.callable(
    _T_PasswordHasher, 
    hash_password, 
    salt="my-secret", 
    rounds=1000, 
    algo="sha256"
)
```