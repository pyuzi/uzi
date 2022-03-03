import os


class ApiClient:

    def __init__(self, api_url: str, api_key: str):
        self.api_key = api_key  # <-- dependency will be injected
        self.api_url = api_url  # <-- dependency will be injected


class Service:

    def __init__(self, api_client: ApiClient):
        self.api_client = api_client  # <-- dependency will be injected

    def do_something(self):
        print("serivce doing something")


def main(service: Service):  # <-- dependency will be injected
    service.do_something()
    


if __name__ == "__main__":
    main(
        service=Service(
            api_client=ApiClient(
                api_key=os.getenv("API_KEY"),
                api_url=os.getenv("TIMEOUT"),
            ),
        ),
    )
