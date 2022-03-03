import os



class ApiClient:

    def __init__(self):
        self.api_url = os.getenv("API_URL")  # a dependency
        self.api_key = os.getenv("API_KEY")  # a dependency



class Service:

    def __init__(self):
        self.api_client = ApiClient()  # a dependency

    def do_something(self):
        print("serivce doing something")



def main() -> None:
    service = Service()  # a dependency
    service.do_something()


if __name__ == "__main__":
    main()
