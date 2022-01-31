import sqlalchemy
from sqlalchemy import Integer, Column, String, Boolean, ForeignKey, Table
from sqlalchemy.orm import registry, relationship

mapper_registry = registry()
Base = mapper_registry.generate_base()

chat_association_table = Table(
    'chat_association',
    Base.metadata,
    Column('user_id', ForeignKey('users.id')),
    Column('chat_id', ForeignKey('chats.id'))
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(30), nullable=False)
    fullname = Column(String, nullable=False)
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
        return f"User(id={self.id!r}, name={self.name!r}, fullname={self.fullname!r}, email={self.email!r}, " \
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
    author_id = Column(Integer, ForeignKey('users.id'))
    author = relationship("User", back_populates="messages")
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    chat = relationship("Chat", back_populates="messages")

    def __repr__(self):
        return f"Message(id={self.id!r}, content={self.content!r}, author={self.author!r}, " \
               f"timestamp={self.timestamp!r}, chat_id={self.chat_id})"


class Invite(Base):
    ___tablename__ = "invites"

    id = Column(String, primary_key=True, nullable=False)

    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    chat = relationship("Chat", back_populates="invites")

    def __repr__(self):
        return f"Invite(id={self.id!r}, chat_id={self.chat_id!r})"
