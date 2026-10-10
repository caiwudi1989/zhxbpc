import sqlite3
from contextlib import closing
with closing(sqlite3.connect(":memory:")) as db:
    db.execute("create table notes(text)")
    db.execute("insert into notes values(?)",("a'b",))
    print(db.execute("select text from notes").fetchone()[0])
