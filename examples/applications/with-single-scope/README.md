
# Single Injector Application Example


Create virtual env:

```shell
poetry shell
```

Install requirements:


```shell
poetry install
```

Run:

```shell
python -m example user@example.com password photo.jpg
```

You should see:


```shell
[2020-10-06 15:32:33,195] [DEBUG] [example.services.UserService]: User user@example.com has been found in database
[2020-10-06 15:32:33,195] [DEBUG] [example.services.AuthService]: User user@example.com has been successfully authenticated
[2020-10-06 15:32:33,195] [DEBUG] [example.services.PhotoService]: Photo photo.jpg has been successfully uploaded by user user@example.com
```