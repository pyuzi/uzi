import pytest


from statistics import median, median_high



@pytest.fixture(scope='session')
def ops_per_sec():
    def ops_per_sec(n, *vals):
        val = median_high(vals)
        return n * (1/val), val
    return ops_per_sec