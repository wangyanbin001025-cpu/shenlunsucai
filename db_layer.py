#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small compatibility layer: SQLite locally, PostgreSQL when DATABASE_URL is configured."""
from __future__ import annotations
import os
import re
import sqlite3
from pathlib import Path


def using_postgres() -> bool:
    return bool(os.environ.get('DATABASE_URL', '').strip())


class PostgresConnection:
    def __init__(self, dsn: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError('已配置 DATABASE_URL，但 PostgreSQL 驱动未安装；请重新部署最新代码。') from exc
        if dsn.startswith('postgres://'):
            dsn = 'postgresql://' + dsn[len('postgres://'):]
        if 'sslmode=' not in dsn:
            dsn += ('&' if '?' in dsn else '?') + 'sslmode=require'
        self._psycopg = psycopg
        self._conn = psycopg.connect(dsn, row_factory=dict_row, connect_timeout=15)

    @staticmethod
    def _sql(sql: str, params):
        if isinstance(params, dict):
            # Convert Python-style named parameters (:title) to psycopg's %(title)s.
            sql = re.sub(r'(?<!:):([A-Za-z_][A-Za-z0-9_]*)', r'%(\1)s', sql)
        elif params is not None:
            # This project only uses ? as positional SQL placeholders.
            sql = sql.replace('?', '%s')
        return sql

    def execute(self, sql, params=None):
        sql = (sql or '').strip()
        if sql.upper().startswith('PRAGMA '):
            # Foreign keys are always enforced by PostgreSQL; SQLite schema checks are handled separately.
            return _EmptyCursor()
        try:
            cur = self._conn.cursor()
            cur.execute(self._sql(sql, params), params if params is not None else ())
            return cur
        except self._psycopg.IntegrityError as exc:
            # Keep the existing API's user-friendly duplicate/constraint error handling.
            self._conn.rollback()
            raise sqlite3.IntegrityError(str(exc)) from exc

    def executescript(self, script):
        # Schema scripts contain plain CREATE statements separated by semicolons.
        for statement in script.split(';'):
            if statement.strip():
                self.execute(statement)

    def commit(self): self._conn.commit()
    def rollback(self): self._conn.rollback()
    def close(self): self._conn.close()


class _EmptyCursor:
    rowcount = -1
    lastrowid = None
    def fetchone(self): return None
    def fetchall(self): return []


def connect(db_path=None, timeout=15):
    """Return a DB-API-like connection. DATABASE_URL switches the app to PostgreSQL."""
    dsn = os.environ.get('DATABASE_URL', '').strip()
    if dsn:
        return PostgresConnection(dsn)
    if db_path is None:
        data_dir = Path(os.environ.get('SHENLUN_DATA_DIR', '.')).expanduser().resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / 'shenlun.db'
    conn = sqlite3.connect(str(db_path), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn
