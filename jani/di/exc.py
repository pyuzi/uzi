import typing as t 


from jani.common.functools import export



@export()
class InjectorKeyError(KeyError):
    pass




class ProviderNotFoundError(LookupError):
    
    def __init__(self, token, msg=None) -> None:
        self.token = token
        super().__init__(msg or f'{token=}')