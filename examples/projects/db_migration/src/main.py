import sqlite3
from contextlib import closing
with closing(sqlite3.connect(":memory:")) as db:
    version=db.execute("pragma user_version").fetchone()[0]
    if version<1:
        with db:
            db.execute("create table users(id integer,name text)")
            db.execute("pragma user_version=1")
    print(db.execute("pragma user_version").fetchone()[0])
