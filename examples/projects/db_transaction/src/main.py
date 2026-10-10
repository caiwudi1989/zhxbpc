import sqlite3
from contextlib import closing
with closing(sqlite3.connect(":memory:")) as db:
    db.execute("create table items(id integer)")
    try:
        with db:
            db.execute("insert into items values(1)")
            raise ValueError("rollback")
    except ValueError:
        pass
    print(db.execute("select count(*) from items").fetchone()[0])
