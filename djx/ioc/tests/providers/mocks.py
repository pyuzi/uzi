import typing as t
from dataclasses import dataclass


import pytest

from ...providers import (
    alias, provide, injectable
)
from ... import symbol, Depends, Scope
from ...symbols import _ordered_id


user_str = 'test-str'
user_symb = symbol('test-import')
noop_symb = symbol('noop-symbol')


class AbcScope(Scope):

    class Config:
        name = Scope.MAIN
        aliases = [
            'abc'
        ]

        

@injectable(cache=False)
class Foo:
    
    def __init__(self, name: Depends[str, 'foo.name'], user: Depends[str, user_str]) -> None:
        self.name = f'{name}  -> #{_ordered_id()}'
        self.user = user
    
    def __repr__(self):
        return f'Foo({self.name!r} u={self.user!r})'
    
    def __str__(self):
        return f'Foo({self.name!r} u={self.user!r})'


provide('foo.name', value='My Name Is Foo!!')

@injectable(scope='abc')
def user_func_injectable():
    return f'user_func_injectable -> #{_ordered_id()}'


@injectable(cache=True, scope='abc')
class Bar:

    def __init__(self, foo: Foo, user: Depends[user_func_injectable]) -> None:
        self.foo = foo
        self.user = user
 
    def __repr__(self):
        return f'Bar(foo={self.foo!r}, user={self.user!r})'
    
    def __str__(self):
        return f'Bar(foo={self.foo!r}, user={self.user!r})'
    
alias(Bar, Foo)

def user_func_symb():
    return f'user_func_symb {user_symb} -> #{_ordered_id()}'
    

provide(user_symb, factory=user_func_symb, cache=True)


@injectable(abstract=user_str)
def user_func_str():
    return f'user_func_str {user_str} -> #{_ordered_id()}'
    

