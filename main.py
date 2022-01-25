# This is a sample Python script.

# Press Umschalt+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import random
import string
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, status
import re

from fastapi.security import OAuth2PasswordRequestForm

from auth import get_password_hash, get_current_active_user, User, authenticate_user, ACCESS_TOKEN_EXPIRE_MINUTES, \
    create_access_token
import db
from defs import Token

app = FastAPI()


def check_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


def generate_random_invite(length: int):
    charset = string.ascii_letters + string.digits
    return ''.join(random.SystemRandom().choice(charset) for _ in range(length))


def add_user(user_db, username, password, full_name, email, disabled=False):
    user_db[username] = {
        "username": username,
        "full_name": full_name,
        "email": email,
        "hashed_password": get_password_hash(password),
        "disabled": disabled
    }


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(db.db["users"], form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.put("/users/register")
async def register(username, password, full_name, email):
    if not check_email(email):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="email is invalid")
    if username in db.db["users"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="username already registered")
    add_user(db.db["users"], username, password, full_name, email)
    db.save()


@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@app.get("/users/{username}", response_model=User)
async def get_user(username):
    return db.db["users"][username]


@app.get("/invite/{invite}")
def use_invite(invite, current_user: User = Depends(get_current_active_user)):
    if invite not in db.db["invites"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite")
    if current_user.username in db.db["chats"][db.db["invites"][invite]]["participating_users"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Joined already")
    db.db["chats"][db.db["invites"][invite]]["participating_users"].append(current_user.username)
    db.save()


@app.delete("/invite/{invite}")
def delete_invite(invite, current_user: User = Depends(get_current_active_user)):
    if invite not in db.db["invites"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite")
    if current_user.username not in db.db["chats"][db.db["invites"][invite]]["participating_users"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Non-member user can't delete invite")
    db.db["invites"].pop(invite)
    db.save()


@app.get("/chat/{chat_id}/invite")
def generate_invite(chat_id: int, current_user: User = Depends(get_current_active_user)):
    if current_user.username not in db.db["chats"][chat_id]["participating_users"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Non-member user can't create invites")
    invite = generate_random_invite(10)
    while invite in db.db["invites"]:
        invite = generate_invite(10)
    db.db["invites"][invite] = chat_id
    db.save()
    return {
        "invite": invite
    }


@app.get("/chat/{chat_id}/messages")
def get_messages(chat_id: int, current_user: User = Depends(get_current_active_user)):
    if chat_id >= len(db.db["chats"]) or current_user.username not in db.db["chats"][chat_id]["participating_users"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view chat")
    return db.db["chats"][chat_id]["messages"]


@app.put("/chat/{chat_id}/messages")
def root(chat_id: int, msg: str, current_user: User = Depends(get_current_active_user)):
    if chat_id >= len(db.db["chats"]) or current_user.username not in db.db["chats"][chat_id]["participating_users"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to send in chat")
    db.db["chats"][chat_id]["messages"].append({"msg": msg})
    db.save()
