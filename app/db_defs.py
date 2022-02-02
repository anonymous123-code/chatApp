import sqlalchemy
from sqlalchemy import Integer, Column, String, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

chat_association_table = Table(
    'chat_association',
    Base.metadata,
    Column('user_id', ForeignKey('users.username')),
    Column('chat_id', ForeignKey('chats.id'))
)


class User(Base):
    __tablename__ = "users"

    username = Column(String(30), nullable=False, primary_key=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    disabled = Column(Boolean, nullable=False, default=True)
    messages = relationship("Message", back_populates="author")
    chats = relationship(
        "Chat",
        secondary=chat_association_table,
        back_populates="members"
    )

    def __repr__(self):
        return f"User(name={self.username!r}, full_name={self.full_name!r}, email={self.email!r}, " \
               f"hashed_password={self.hashed_password!r}, disabled={self.disabled!r})"


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    invites = relationship("Invite", back_populates="chat", cascade="all, delete-orphan")
    members = relationship(
        "User",
        secondary=chat_association_table,
        back_populates="chats"
    )

    def __repr__(self):
        return f"Chat(id={self.id!r}, messages={self.messages!r}, members={self.members!r}, invites={self.invites!r})"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    content = Column(String, nullable=False)
    timestamp = Column(sqlalchemy.BigInteger, nullable=False)
    edited = Column(Boolean, nullable=False, default=False)
    author_id = Column(Integer, ForeignKey('users.username'))
    author = relationship("User", back_populates="messages")
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    chat = relationship("Chat", back_populates="messages")

    def __repr__(self):
        return f"Message(id={self.id!r}, content={self.content!r}, author={self.author!r}, " \
               f"timestamp={self.timestamp!r}, chat_id={self.chat_id})"


class Invite(Base):
    __tablename__ = "invites"

    id = Column(String, primary_key=True, nullable=False)

    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    chat = relationship("Chat", back_populates="invites")

    def __repr__(self):
        return f"Invite(id={self.id!r}, chat_id={self.chat_id!r})"
