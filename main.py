# This is a sample Python script.

# Press Umschalt+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import random
import string

from fastapi import Depends, FastAPI, HTTPException, status
import re

from auth import get_password_hash, get_current_active_user, User
from db import db

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


@app.put("/users/register")
async def register(username, password, full_name, email):
    if not check_email(email):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="email is invalid")
    if username in db["users"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="username already registered")
    add_user(db["users"], username, password, full_name, email)


@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@app.get("/users/{username}", response_model=User)
async def get_user(username):
    return db["users"][username]


@app.get("/invite/{invite}")
def use_invite(invite, current_user: User = Depends(get_current_active_user)):
    if invite not in db["invites"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite")
    if current_user.username in db["chats"][db["invites"][invite]]["participating_users"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Joined already")
    db["chats"][db["invites"][invite]]["participating_users"].append(current_user.username)


@app.delete("/invite/{invite}")
def delete_invite(invite, current_user: User = Depends(get_current_active_user)):
    if invite not in db["invites"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite")
    if current_user.username not in db["chats"][db["invites"][invite]]["participating_users"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Non-member user can't delete invite")
    db["invites"].pop(invite)


@app.get("/chat/{chat_id}/invite")
def generate_invite(chat_id: int, current_user: User = Depends(get_current_active_user)):
    if current_user.username not in db["chats"][chat_id]["participating_users"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Non-member user can't create invites")
    invite = generate_random_invite(10)
    while invite in db["invites"]:
        invite = generate_invite(10)
    db["invites"][invite] = chat_id
    return {
        "invite": invite
    }


@app.get("/chat/{chat_id}/messages")
def get_messages(chat_id: int, current_user: User = Depends(get_current_active_user)):
    if chat_id not in db["chats"] or current_user.username not in db["chats"][chat_id]["participating_users"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view chat")
    return db["chats"][chat_id]["messages"]


@app.put("/chat/{chat_id}/messages")
def root(chat_id: int, msg: str, current_user: User = Depends(get_current_active_user)):
    if chat_id not in db["chats"]:
        db["chats"][chat_id] = {"messages": [], "participating_users": [current_user.username]}
    if current_user.username not in db["chats"][chat_id]["participating_users"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to send in chat")
    db["chats"][chat_id]["messages"].append({"msg": msg})
