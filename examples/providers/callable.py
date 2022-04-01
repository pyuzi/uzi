"""`Callable` provider example."""

import passlib.hash

from laza.di import Injector, context


hash_password = passlib.hash.sha256_crypt.hash
verify_password = passlib.hash.sha256_crypt.verify


injector = Injector()
injector.callable(verify_password)
injector.callable(hash_password, salt_size=16, rounds=10000)

if __name__ == '__main__':
    with context(injector) as ctx:
        hashed_pass = ctx.make(hash_password)('my-secret')
        assert ctx.make(verify_password)('my-secret', hashed_pass)

