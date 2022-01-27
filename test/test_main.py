import pytest
from fastapi.testclient import TestClient
from starlette import status


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
def add_test_users(reset_db, auth, request):
    # Example data:
    # [{"username":"test1","full_name": "full_name","email": "a@a.a","password":"secret","disabled":False}]
    # Minimum data: []
    # Minimum user data: {}
    # default user data:
    # {"username":"test{INDEX}","full_name": "test{INDEX} Test","email": "test@test.test","password":"secret","disabled":False}
    users = request.node.get_closest_marker("test_users", []).args[0]

    def fill_user_with_default_values(i, u):
        if "username" not in u:
            u["username"] = "test" + str(i)
        if "full_name" not in u:
            u["full_name"] = "test" + str(i) + " Test"
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
        reset_db.save()
    yield generated_users.copy()
    for user in generated_users:
        try:
            reset_db.db["users"].pop(user["username"])
        except KeyError:
            pass


@pytest.fixture
def auth(reset_db):
    import auth
    return auth


@pytest.fixture
def test_client(reset_db, auth):
    from main import app
    return TestClient(app)


def test_register_user(test_client, reset_db, auth):
    data = test_client.post("/users/register?username=hi&password=secret&full_name=Hello&email=h%40h.h")
    assert data.status_code == status.HTTP_200_OK
    assert "hi" in reset_db.db["users"]
    assert reset_db.db["users"]["hi"]["full_name"] == "Hello"
    assert reset_db.db["users"]["hi"]["email"] == "h@h.h"
    assert auth.verify_password("secret", reset_db.db["users"]["hi"]["hashed_password"])
    assert reset_db.db["users"]["hi"]["username"] == "hi"
    assert not reset_db.db["users"]["hi"]["disabled"]


@pytest.mark.test_users([{"username": "test1"}])
def test_register_user_double_username(test_client, add_test_users):
    data = test_client.post("/users/register?username=test1&password=secret&full_name=Hello&email=h%40h.h")
    assert data.status_code == status.HTTP_401_UNAUTHORIZED
    assert data.json()["detail"] == "username already registered"
