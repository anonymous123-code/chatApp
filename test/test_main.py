import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from jose.utils import base64url_decode
from starlette import status

from defs import UserInDB, User


@pytest.fixture
def open_db():
    import db
    return db


@pytest.fixture
def reset_db(open_db):
    old_users = open_db.db["users"]
    old_invites = open_db.db["invites"]
    old_chats = open_db.db["chats"]
    open_db.db["users"] = {}
    open_db.db["invites"] = {}
    open_db.db["chats"] = {}
    open_db.save()
    yield open_db
    open_db.db["users"] = old_users
    open_db.db["invites"] = old_invites
    open_db.db["chats"] = old_chats
    open_db.save()


@pytest.fixture
def auth(reset_db):
    import auth
    return auth


@pytest.fixture
def add_test_users(reset_db, auth, request):
    # Example data:
    # [{"username":"test1","full_name": "full_name","email": "a@a.a","password":"secret","disabled":False}]
    # Minimum data: []
    # Minimum user data: {}
    # default user data:
    # {"username":"test{INDEX}","full_name": "test{INDEX} Test","email": "test@test.test","password":"secret","disabled":False}
    marker = request.node.get_closest_marker("test_users")
    users = marker.args[0] if marker else []

    def fill_user_with_default_values(i, u):
        if "username" not in u:
            u["username"] = "test" + str(i)
        if "full_name" not in u:
            u["full_name"] = f"test{str(i)} Test"
        if "email" not in u:
            u["email"] = "test@test.test"
        if "password" not in u:
            u["password"] = "secret"
        if "disabled" not in u:
            u["disabled"] = False
        return u

    generated_users = []
    for index, user in enumerate(users):
        user = fill_user_with_default_values(index, user)
        if user["username"] in reset_db.db["users"]:
            raise Exception("shouldnt be in state")
        reset_db.db["users"][user["username"]] = {
            "username": user["username"],
            "full_name": user["full_name"],
            "email": user["email"],
            "hashed_password": auth.get_password_hash(user["password"]),
            "disabled": user["disabled"]
        }
        generated_users.append(reset_db.db["users"][user["username"]])
        generated_users[len(generated_users) - 1]["password"] = user["password"]
        reset_db.save()
    yield generated_users.copy()
    for user in generated_users:
        try:
            reset_db.db["users"].pop(user["username"])
        except KeyError:
            pass


@pytest.fixture
def token(add_test_users, auth, request):
    marker = request.node.get_closest_marker("token_test_user_index")
    index = int(marker.args[0] if marker else 0)
    if len(add_test_users) <= index:
        raise KeyError("Index invalid")
    return auth.create_access_token({"sub": add_test_users[index]["username"]})


@pytest.fixture
def test_client(reset_db, auth):
    from main import app
    return TestClient(app)


def test_register_user(test_client, reset_db, auth):
    data = test_client.post("/users/register?username=hi&password=secret&full_name=Hello&email=h%40h.h")
    assert data.status_code == status.HTTP_200_OK
    assert "hi" in reset_db.db["users"]
    assert User(**reset_db.db["users"]["hi"]) == User(username="hi", full_name="Hello", email="h@h.h", disabled=False)
    assert auth.verify_password("secret", reset_db.db["users"]["hi"]["hashed_password"])


@pytest.mark.test_users([{}])
def test_register_user_double_username(test_client, add_test_users, reset_db):
    old_reset_db = reset_db.db.copy()
    data = test_client.post(f"/users/register?username={add_test_users[0]['username']}&password=secret&full_name"
                            f"=Hello&email=h%40h.h")
    assert data.status_code == status.HTTP_401_UNAUTHORIZED
    assert data.json()["detail"] == "username already registered"
    assert old_reset_db == reset_db.db


def test_register_user_invalid_email(test_client):
    data = test_client.post("/users/register?username=test1&password=secret&full_name=Hello&email=hh.h")
    assert data.status_code == status.HTTP_401_UNAUTHORIZED
    assert data.json()["detail"] == "email is invalid"


@pytest.mark.test_users([{}])
def test_register_user_double_username_invalid_email(test_client, add_test_users, reset_db):
    data = test_client.post(f"/users/register?username={add_test_users[0]['username']}&password=secret&full_name"
                            f"=Hello&email=h%40hh")
    assert data.status_code == status.HTTP_401_UNAUTHORIZED
    assert data.json()["detail"] == "email is invalid"


@pytest.mark.test_users([{}])
def test_receive_token(test_client, add_test_users, auth):
    data = test_client.post(f"/token", data={
        "username": add_test_users[0]["username"],
        "password": add_test_users[0]["password"]
    })

    assert data.status_code == 200
    assert data.json()["token_type"] == "bearer"
    token = data.json()["access_token"]
    token_parts = token.split(".")
    assert len(token_parts) == 3

    def base64to_string(i):
        return base64url_decode(i.encode("utf-8")).decode("utf-8")

    assert base64to_string(token_parts[0]) == "{\"alg\":\"HS256\",\"typ\":\"JWT\"}"
    assert json.loads(base64to_string(token_parts[1]))["sub"] == add_test_users[0]["username"]
    current_user = asyncio.run(auth.get_current_user(token))
    assert current_user == UserInDB(**add_test_users[0])


@pytest.mark.test_users([{}])
def test_receive_token_wrong_username(test_client, add_test_users, auth):
    data = test_client.post(f"/token", data={
        "username": add_test_users[0]["username"] + "ThisIsANonExistingUsername",
        "password": add_test_users[0]["password"]
    })
    assert data.status_code == status.HTTP_401_UNAUTHORIZED
    assert data.json()["detail"] == "Incorrect username or password"


@pytest.mark.test_users([{}])
def test_receive_token_wrong_password(test_client, add_test_users, auth):
    data = test_client.post(f"/token", data={
        "username": add_test_users[0]["username"],
        "password": add_test_users[0]["password"] + "WrongPassword"
    })
    assert data.status_code == status.HTTP_401_UNAUTHORIZED
    assert data.json()["detail"] == "Incorrect username or password"