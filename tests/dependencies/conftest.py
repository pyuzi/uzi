from unittest.mock import MagicMock, Mock, NonCallableMagicMock
import pytest
import typing as t






@pytest.fixture
def new_args(abstract, new_args):
    return (abstract, *new_args)

@pytest.fixture
def new_kwargs(new_kwargs, concrete, mock_scope, mock_provider):
    return new_kwargs | dict(scope=mock_scope, provider=mock_provider, concrete=concrete)



