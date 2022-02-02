import random
import re
import string
import time
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import db_defs
from app.auth import get_password_hash, get_current_active_user, authenticate_user, ACCESS_TOKEN_EXPIRE_MINUTES, \
    create_access_token
from app.db import get_db, engine
from app.defs import Token, PublicUser, Invite, StrList, MessageList, UserList, User, ChatDict

db_defs.Base.metadata.create_all(bind=engine)

app = FastAPI()


def check_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


def get_chat(db: Session, chat_id: int):
    return db.query(db_defs.Chat).filter_by(id=chat_id).scalar()


def user_exists(db: Session, username: str):
    return db.query(db_defs.User.username).filter_by(username=username).scalar() is not None


def user_in_chat(chat: db_defs.Chat, username: str):
    return chat is not None and len([user for user in chat.members if user.username == username])


def get_message(chat: db_defs.Chat, message_id: int):
    return None if chat is None else [message for message in chat.messages if message.id == message_id][0]


def is_owner(message: db_defs.Message, username: str):
    return False if message is None else message.author.username == username


def only_allow_message_owner_edits(chat: db_defs.Chat, message_id: int, username: string):
    if chat is None or not user_in_chat(chat, username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit chat")
    message = get_message(chat, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message doesn't exist")
    if not is_owner(message, username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the sender is able to edit")
    return message


def generate_random_invite(length: int):
    charset = string.ascii_letters + string.digits
    return ''.join(random.SystemRandom().choice(charset) for _ in range(length))


def add_user(db, username, password, full_name, email, disabled=False):
    db.add(db_defs.User(
        username=username,
        full_name=full_name,
        email=email,
        hashed_password=get_password_hash(password),
        disabled=disabled
    ))


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
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
async def register(username: str, password: str, full_name: str, email: str, db: Session = Depends(get_db)):
    if not check_email(email):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="email is invalid")

    if user_exists(db, username):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="username already registered")
    add_user(db, username, password, full_name, email)
    db.commit()


@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: db_defs.User = Depends(get_current_active_user)):
    return User.from_orm(current_user)


@app.get("/users/{username}", response_model=User)
async def get_user(username, current_user: db_defs.User = Depends(get_current_active_user),
                   db: Session = Depends(get_db)):
    user = db.query(db_defs.User).filter_by(username=username).scalar()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return User.from_orm(user) if username == current_user.username else PublicUser.from_orm(user)


@app.get("/invite/{invite}")
def use_invite(invite, current_user: db_defs.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    invite = db.query(db_defs.Invite).filter_by(id=invite).scalar()
    if invite is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite")
    if user_in_chat(invite.chat, current_user.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Joined already")
    invite.chat.members.add(current_user)
    db.commit()


@app.delete("/invite/{invite}")
def delete_invite(invite, current_user: db_defs.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    invite = db.query(db_defs.Invite).filter_by(id=invite).scalar()
    if invite is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite")
    if not user_in_chat(invite.chat, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Non-member user can't delete invite")
    db.delete(invite)
    db.commit()


@app.post("/chats/{chat_id}/invite", response_model=Invite)
def generate_invite(chat_id: int, current_user: db_defs.User = Depends(get_current_active_user),
                    db: Session = Depends(get_db)):
    chat = get_chat(db, chat_id)
    if chat is None or not user_in_chat(chat, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Non-member user can't create invites")
    invite = generate_random_invite(10)
    invites = db.query(db_defs.Invite)
    while invites.filter_by(id=invite).scalar() is not None:
        invite = generate_random_invite(10)
    db.add(db_defs.Invite(id=invite, chat=chat))
    db.commit()
    return {
        "invite": invite
    }


@app.get("/chats/{chat_id}/invites", response_model=StrList)
def get_invites(chat_id: int, current_user: db_defs.User = Depends(get_current_active_user),
                db: Session = Depends(get_db)):
    chat = get_chat(db, chat_id)
    if chat is None or not user_in_chat(chat, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view chat invites")
    return StrList.from_orm([invite.id for invite in chat.invites])


@app.get("/chats/{chat_id}/messages", response_model=MessageList)
def get_messages(chat_id: int, current_user: db_defs.User = Depends(get_current_active_user),
                 db: Session = Depends(get_db)):
    chat = get_chat(db, chat_id)
    if chat is None or not user_in_chat(chat, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view chat")
    return MessageList.from_orm(chat.messages)


@app.post("/chats/{chat_id}/messages")
def send_message(chat_id: int, msg: str, current_user: db_defs.User = Depends(get_current_active_user),
                 db: Session = Depends(get_db)):
    chat = get_chat(db, chat_id)
    if chat is None or not user_in_chat(chat, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to send in chat")
    db.add(db_defs.Message(chat=chat, content=msg, author=current_user, timestamp=time.time_ns()))
    db.commit()


@app.delete("/chats/{chat_id}/messages/{message_id}")
def delete_message(chat_id: int, message_id: int, current_user: db_defs.User = Depends(get_current_active_user),
                   db: Session = Depends(get_db)):
    chat = get_chat(db, chat_id)
    message = only_allow_message_owner_edits(chat, message_id, current_user.username)
    db.delete(message)
    db.commit()


@app.post("/chats/{chat_id}/messages/{message_id}")
def edit_message(chat_id: int, message_id: int, message: str,
                 current_user: db_defs.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    chat = get_chat(db, chat_id)
    msg = only_allow_message_owner_edits(chat, message_id, current_user.username)
    msg.content = message
    msg.edited = True
    db.commit()


@app.get("/chats/{chat_id}/members", response_model=UserList)
def get_members(chat_id: int, current_user: db_defs.User = Depends(get_current_active_user),
                db: Session = Depends(get_db)):
    chat = get_chat(db, chat_id)
    if chat is None or not user_in_chat(chat, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    return UserList.from_orm(chat.members)


@app.delete("/chats/{chat_id}/members/{member_name}")
def kick_member(chat_id: int, member_name: str, current_user: db_defs.User = Depends(get_current_active_user),
                db: Session = Depends(get_db)):
    chat = get_chat(db, chat_id)
    if chat is None or not user_in_chat(chat, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit chat")
    if not user_in_chat(chat, member_name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    chat.members.pop(chat.members.index(db.query(db_defs.User).filter_by(username=member_name).scalar()))
    db.commit()


@app.post("/chats/")
def create_chat(current_user: db_defs.User = Depends(get_current_active_user),
                db: Session = Depends(get_db)):
    chat = db_defs.Chat()
    chat.members.append(current_user)
    db.add(chat)
    db.commit()
    return {
        "id": chat.id
    }


@app.get("/chats/", response_model=ChatDict)
def get_chats(current_user: db_defs.User = Depends(get_current_active_user)):
    return {chat.id: chat for chat in current_user.chats}


@app.delete("/chats/{chat_id}")
def delete_chat(chat_id: int, current_user: db_defs.User = Depends(get_current_active_user),
                db: Session = Depends(get_db)):
    chat = get_chat(db, chat_id)
    if chat is None or not user_in_chat(chat, current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit chat")
    db.delete(chat)
    db.commit()
