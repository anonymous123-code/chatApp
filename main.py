import random
import string
import time
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, status
import re

from fastapi.security import OAuth2PasswordRequestForm

from auth import get_password_hash, get_current_active_user, User, authenticate_user, ACCESS_TOKEN_EXPIRE_MINUTES, \
    create_access_token
import db
from defs import Token, PublicUser

app = FastAPI()


def check_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


def chat_exists(chat_id: str):
    return chat_id in db.db["chats"]


def user_in_chat(chat_id: str, username: str):
    return username in db.db["chats"][chat_id]["members"]


def message_exists(chat_id: str, message_id: int):
    return message_id < len(db.db["chats"][chat_id]["messages"])


def is_owner(chat_id: str, message_id: int, username: str):
    return db.db["chats"][chat_id]["messages"][message_id]["author"] == username


def only_allow_message_owner_edits(chat_id: str, message_id: int, username: string):
    if not chat_exists(chat_id) or not user_in_chat(chat_id, username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit chat")
    if not message_exists(chat_id, message_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message doesn't exist")
    if not is_owner(chat_id, message_id, username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the sender is able to edit")


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


@app.post("/users/register")
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
async def get_user(username, current_user=Depends(get_current_active_user)):
    return User(**db.db["users"][username]) if username == current_user.username else PublicUser(
        **db.db["users"][username]
    )


@app.get("/invite/{invite}")
def use_invite(invite, current_user: User = Depends(get_current_active_user)):
    if invite not in db.db["invites"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite")
    if current_user.username in db.db["chats"][db.db["invites"][invite]]["members"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Joined already")
    db.db["chats"][db.db["invites"][invite]]["members"].append(current_user.username)
    db.save()


@app.delete("/invite/{invite}")
def delete_invite(invite, current_user: User = Depends(get_current_active_user)):
    if invite not in db.db["invites"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite")
    if current_user.username not in db.db["chats"][db.db["invites"][invite]]["members"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Non-member user can't delete invite")
    db.db["invites"].pop(invite)
    db.save()


@app.post("/chats/{chat_id}/invite")
def generate_invite(chat_id: int, current_user: User = Depends(get_current_active_user)):
    chat_id = str(chat_id)
    if not chat_exists(chat_id) or not user_in_chat(chat_id, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Non-member user can't create invites")
    invite = generate_random_invite(10)
    while invite in db.db["invites"]:
        invite = generate_invite(10)
    db.db["invites"][invite] = chat_id
    db.save()
    return {
        "invite": invite
    }


@app.get("/chats/{chat_id}/invites")
def get_invites(chat_id: int, current_user: User = Depends(get_current_active_user)):
    chat_id = str(chat_id)
    if not chat_exists(chat_id) or not user_in_chat(chat_id, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view chat invites")
    return [invite for invite, chat in db.db["invites"].items() if chat == chat_id]


@app.get("/chats/{chat_id}/messages")
def get_messages(chat_id: int, current_user: User = Depends(get_current_active_user)):
    chat_id = str(chat_id)
    if not chat_exists(chat_id) or not user_in_chat(chat_id, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view chat")
    return db.db["chats"][chat_id]["messages"]


@app.post("/chats/{chat_id}/messages")
def send_message(chat_id: int, msg: str, current_user: User = Depends(get_current_active_user)):
    chat_id = str(chat_id)
    if not chat_exists(chat_id) or not user_in_chat(chat_id, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to send in chat")
    db.db["chats"][chat_id]["messages"].append({
        "msg": msg,
        "timestamp": time.time_ns(),
        "edited": False,
        "author": current_user.username
    })
    db.save()


@app.delete("/chats/{chat_id}/messages/{message_id}")
def delete_message(chat_id: int, message_id: int, current_user: User = Depends(get_current_active_user)):
    chat_id = str(chat_id)
    only_allow_message_owner_edits(chat_id, message_id, current_user.username)
    db.db["chats"][chat_id]["messages"].pop(message_id)
    db.save()


@app.post("/chats/{chat_id}/messages/{message_id}")
def edit_message(chat_id: int, message_id: int, message: str, current_user: User = Depends(get_current_active_user)):
    chat_id = str(chat_id)
    only_allow_message_owner_edits(chat_id, message_id, current_user.username)
    db.db["chats"][chat_id]["messages"][message_id]["msg"] = message
    db.db["chats"][chat_id]["messages"][message_id]["edited"] = True
    db.save()


@app.get("/chats/{chat_id}/members")
def get_members(chat_id: int, current_user: User = Depends(get_current_active_user)):
    chat_id = str(chat_id)
    if not chat_exists(chat_id) or not user_in_chat(chat_id, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    return db.db["chats"][chat_id]["members"]


@app.delete("/chats/{chat_id}/members/{member_name}")
def kick_member(chat_id: int, member_name: str, current_user: User = Depends(get_current_active_user)):
    chat_id = str(chat_id)
    if not chat_exists(chat_id) or not user_in_chat(chat_id, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit chat")
    if not user_in_chat(chat_id, member_name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    # FIXME pop braucht index, nicht element
    db.db["chats"][chat_id]["members"].pop(member_name)
    db.save()


@app.post("/chats/")
def create_chat(current_user: User = Depends(get_current_active_user)):
    def get_first_free_key():
        keys = db.db["chats"].keys()
        for i in range(len(keys)+1):
            if str(i) not in keys:
                return str(i)

    key = get_first_free_key()
    db.db["chats"][key] = {"messages": [], "members": [current_user.username]}
    db.save()
    return {
        "id": key
    }


@app.get("/chats/")
def get_chats(current_user: User = Depends(get_current_active_user)):
    return {i: chat for i, chat in db.db["chats"].items() if current_user.username in chat["members"]}


@app.delete("/chats/{chat_id}")
def delete_chat(chat_id: int, current_user: User = Depends(get_current_active_user)):
    chat_id = str(chat_id)
    if not chat_exists(chat_id) or not user_in_chat(chat_id, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit chat")
    db.db["chats"].pop(chat_id)
    db.save()
