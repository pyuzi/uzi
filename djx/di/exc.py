


class ProviderNotFoundError(LookupError):
    
    def __init__(self, token, msg=None) -> None:
        self.token = token
        super().__init__(msg or f'{token=}')