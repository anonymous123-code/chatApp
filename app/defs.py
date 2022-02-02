from typing import Optional, List, Dict

import pydantic


class BaseModel(pydantic.BaseModel):
    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class PublicUser(BaseModel):
    username: str


class User(PublicUser):
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


class UserInDB(User):
    hashed_password: str


class Message(BaseModel):
    id: int
    content: str
    timestamp: str
    edited: bool = False
    author: PublicUser


class Chat(BaseModel):
    id: int
    messages: List[Message]
    members: List[PublicUser]


class Invite(BaseModel):
    invite: str


class UserList(BaseModel):
    __root__: List[PublicUser]


class MessageList(BaseModel):
    __root__: List[Message]


class ChatList(BaseModel):
    __root__: List[Chat]


class StrList(BaseModel):
    __root__: List[str]
