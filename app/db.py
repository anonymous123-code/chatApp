# import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite+pysqlite:///:memory:", echo=True, future=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# DB_PATH = "db.json"

# f = open(DB_PATH, "rt")
# db = json.loads(f.read())
# f.close()


# def setup(path):
#     global DB_PATH, db
#     DB_PATH = path
#     f = open(DB_PATH, "rt")
#     db = json.loads(f.read())
#     print(db)
#     f.close()
#
#
# def save():
#     f = open(DB_PATH, "wt")
#     f.write(json.dumps(db, indent=4))
#     f.close()
