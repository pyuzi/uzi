import pytest


from statistics import median



@pytest.fixture(scope='session')
def ops_per_sec():
    def ops_per_sec(n, *vals):
        val = 1 / median(vals)
        return n * val
    return ops_per_sec