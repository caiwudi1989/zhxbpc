"""Database designer contract and SQLite CRUD generation."""
from __future__ import annotations

import re
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

class DatabaseError(ValueError):
    pass

@dataclass(frozen=True)
class Column:
    name: str
    type: str = "TEXT"
    nullable: bool = True
    primary_key: bool = False
    default: str | None = None

@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    indexes: tuple[str, ...] = ()


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
_TYPES = {"TEXT", "INTEGER", "REAL", "BLOB", "NUMERIC"}


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise DatabaseError(f"{label}非法")
    return value

def validate_schema(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("tables"), list):
        raise DatabaseError("数据库 schema 必须使用 version 1")
    tables, seen = [], set()
    allowed = _TYPES
    if len(value["tables"]) > 500:
        raise DatabaseError("表数量不能超过 500")
    for raw in value["tables"]:
        if not isinstance(raw, dict):
            raise DatabaseError("表必须是对象")
        name = _identifier(raw.get("name", ""), "表名")
        if name in seen:
            raise DatabaseError("表名非法或重复")
        seen.add(name)
        columns, column_names = [], set()
        if not isinstance(raw.get("columns"), list):
            raise DatabaseError("字段必须是数组")
        if len(raw["columns"]) > 256:
            raise DatabaseError("字段数量不能超过 256")
        primary_keys = 0
        for item in raw.get("columns", []):
            if not isinstance(item, dict):
                raise DatabaseError("字段必须是对象")
            nullable = item.get("nullable", True)
            primary_key = item.get("primary_key", False)
            if type(nullable) is not bool or type(primary_key) is not bool:
                raise DatabaseError("字段 nullable/primary_key 必须是布尔值")
            col = Column(str(item.get("name", "")), str(item.get("type", "TEXT")).upper(), nullable, primary_key, item.get("default"))
            if not _IDENTIFIER.fullmatch(col.name) or col.name in column_names or col.type not in allowed:
                raise DatabaseError("字段名或类型非法")
            if col.primary_key:
                primary_keys += 1
            if col.default is not None and not isinstance(col.default, (str, int, float, bool)):
                raise DatabaseError("默认值只能是文本、数字或布尔值")
            if isinstance(col.default, str) and len(col.default) > 256:
                raise DatabaseError("默认值不能超过 256 字符")
            if isinstance(col.default, float) and not math.isfinite(col.default):
                raise DatabaseError("默认值必须是有限数")
            column_names.add(col.name); columns.append(col)
        if not columns:
            raise DatabaseError("表至少需要一个字段")
        if primary_keys > 1:
            raise DatabaseError("当前 SQLite 合同只允许一个主键字段")
        indexes = raw.get("indexes", [])
        if not isinstance(indexes, list) or len(indexes) > 256 or len({str(index) for index in indexes}) != len(indexes) or any(not _IDENTIFIER.fullmatch(str(index)) or str(index) not in column_names for index in indexes):
            raise DatabaseError("索引字段非法")
        tables.append({"name": name, "columns": [c.__dict__ for c in columns], "indexes": list(indexes)})
    return {"version": 1, "tables": tables}

def create_schema(connection: sqlite3.Connection, schema: dict[str, Any]) -> None:
    normalized = validate_schema(schema)
    for table in normalized["tables"]:
        fields = []
        for col in table["columns"]:
            definition = f"[{col['name']}] {col['type']}"
            if col["primary_key"]: definition += " PRIMARY KEY"
            if not col["nullable"]: definition += " NOT NULL"
            if col["default"] is not None:
                default = col["default"]
                if isinstance(default, bool):
                    definition += " DEFAULT " + ("1" if default else "0")
                elif isinstance(default, (int, float)):
                    definition += " DEFAULT " + str(default)
                elif isinstance(default, str) and len(default) <= 256:
                    definition += " DEFAULT '" + default.replace("'", "''") + "'"
                else:
                    raise DatabaseError("默认值非法")
            fields.append(definition)
        connection.execute(f"CREATE TABLE IF NOT EXISTS [{table['name']}] ({', '.join(fields)})")
        for index in table.get("indexes", []):
            connection.execute(f"CREATE INDEX IF NOT EXISTS [{table['name']}_{index}] ON [{table['name']}] ([{index}])")
    connection.commit()

def generate_crud(table: Table) -> dict[str, str]:
    _identifier(table.name, "表名")
    if not table.columns:
        raise DatabaseError("表至少需要一个字段")
    for column in table.columns:
        _identifier(column.name, "字段名")
        if column.type.upper() not in _TYPES:
            raise DatabaseError("字段类型非法")
    fields = ", ".join(c.name for c in table.columns)
    placeholders = ", ".join("?" for _ in table.columns)
    primary = next((c.name for c in table.columns if c.primary_key), table.columns[0].name)
    updates = ", ".join(f"{c.name} = ?" for c in table.columns if c.name != primary) or f"{primary} = {primary}"
    return {"create": f"INSERT INTO {table.name} ({fields}) VALUES ({placeholders})", "read": f"SELECT {fields} FROM {table.name} WHERE {primary} = ?", "update": f"UPDATE {table.name} SET {updates} WHERE {primary} = ?", "delete": f"DELETE FROM {table.name} WHERE {primary} = ?", "list": f"SELECT {fields} FROM {table.name} ORDER BY {primary}"}


def generate_python_module(schema: dict[str, Any]) -> str:
    """Generate importable Python metadata and CRUD helpers for the IDE.

    The designer used to write bare JSON into a ``.py`` file, which made the
    next build fail while compiling generated sources.  Keep the generated
    module deliberately small and data-only so it is safe to import in a
    project runtime and easy for other providers to consume.
    """
    normalized = validate_schema(schema)
    tables: dict[str, dict[str, str]] = {}
    for table in normalized["tables"]:
        obj = Table(table["name"], tuple(Column(**column) for column in table["columns"]), tuple(table["indexes"]))
        tables[obj.name] = generate_crud(obj)
    import pprint
    return "# generated by PCIDE database designer\nCRUD = " + pprint.pformat(tables, sort_dicts=True, width=120) + "\n"
