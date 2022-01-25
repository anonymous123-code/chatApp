import json

DB_PATH = "./db.json"

f = open(DB_PATH, "rt")
db = json.loads(f.read())
print(db)
f.close()


def save():
    f = open(DB_PATH, "wt")
    f.write(json.dumps(db))
    f.close()
