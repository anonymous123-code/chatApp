from _pytest.fixtures import fixture
from fastapi.testclient import TestClient
from starlette import status


@fixture
def open_db():
    import db
    return db


@fixture
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


# FIXME not clean
@fixture()
def add_1_test_user(reset_db):
    if "test1" in reset_db.db["users"]:
        raise Exception("shouldnt be in state")
    reset_db.db["users"]["test1"] = {
        "username": "test1",
        "full_name": "full_name",
        "email": "a@a.a",
        # passwort: secret
        "hashed_password": "$2b$12$bKeVp1uTpiw6af1vUMK0w.FYaT.FtwhyFPsnrWdvrMduLq5OyCxFS",
        "disabled": False
    }
    reset_db.save()
    yield
    reset_db.db["users"].pop("test1")
    reset_db.save()


@fixture()
def add_2_test_user(reset_db, add_1_test_user):
    if "test2" in reset_db.db["users"]:
        raise Exception("shouldnt be in state")
    reset_db.db["users"]["test2"] = {
        "username": "test2",
        "full_name": "full_name",
        "email": "a@a.a",
        # passwort: secret
        "hashed_password": "$2b$12$bKeVp1uTpiw6af1vUMK0w.FYaT.FtwhyFPsnrWdvrMduLq5OyCxFS",
        "disabled": False
    }
    reset_db.save()
    yield
    reset_db.db["users"].pop("test2")
    reset_db.save()


@fixture()
def add_3_test_user(reset_db, add_2_test_user):
    if "test3" in reset_db.db["users"]:
        raise Exception("shouldnt be in state")
    reset_db.db["users"]["test3"] = {
        "username": "test3",
        "full_name": "full_name",
        "email": "a@a.a",
        # passwort: secret
        "hashed_password": "$2b$12$bKeVp1uTpiw6af1vUMK0w.FYaT.FtwhyFPsnrWdvrMduLq5OyCxFS",
        "disabled": False
    }
    reset_db.save()
    yield
    reset_db.db["users"].pop("test3")
    reset_db.save()


@fixture
def auth(reset_db):
    import auth
    return auth


@fixture
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


def test_register_user_double_username(test_client, add_1_test_user):
    data = test_client.post("/users/register?username=test1&password=secret&full_name=Hello&email=h%40h.h")
    assert data.status_code == status.HTTP_401_UNAUTHORIZED
    assert data.json()["detail"] == "username already registered"
