import sqlite3
from contextlib import closing
with closing(sqlite3.connect(":memory:")) as db:
    db.execute("create table items(id integer primary key,name text)")
    db.execute("insert into items(name) values(?)",("old",))
    db.execute("update items set name=? where id=?",("new",1))
    print(db.execute("select * from items").fetchall())
    db.execute("delete from items where id=?",(1,))
    print(db.execute("select count(*) from items").fetchone()[0])
