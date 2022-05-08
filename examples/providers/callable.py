"""`Callable` provider example."""

import passlib.hash

from uzi import DepGraph, Container, Injector


hash_password = passlib.hash.sha256_crypt.hash
verify_password = passlib.hash.sha256_crypt.verify


ioc = Container()
ioc.callable(verify_password)
ioc.callable(hash_password, salt_size=16, rounds=10000)

scope = DepGraph(ioc)

if __name__ == '__main__':
    inj = Injector(scope)
    hashed_pass = inj.make(hash_password, 'my-secret')
    assert inj.make(verify_password, 'my-secret', hashed_pass)

