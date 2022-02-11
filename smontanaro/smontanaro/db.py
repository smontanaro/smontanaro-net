#!/usr/bin/env python

"""database bits for CR archive"""

import os
import sqlite3

from .dates import convert_ts_bytes

def ensure_db(sqldb):
    "make sure the database and its schema exist"
    create = not os.path.exists(sqldb) or os.path.getsize(sqldb) == 0
    sqlite3.register_converter("TIMESTAMP", convert_ts_bytes)
    conn = sqlite3.connect(sqldb, detect_types=(sqlite3.PARSE_DECLTYPES
                                                | sqlite3.PARSE_COLNAMES))
    if create:
        create_main_tables(conn)
        create_topic_tables(conn)
    return conn

def ensure_indexes(conn):
    ensure_main_indexes(conn)
    ensure_topic_indexes(conn)

def create_main_tables(conn):
    cur = conn.cursor()
    cur.execute('''
        create table messages
          (
            messageid TEXT PRIMARY KEY,
            filename TEXT,
            sender TEXT,
            subject TEXT,
            year INTEGER,
            month INTEGER,
            seq INTEGER,
            is_root INTEGER,
            ts timestamp
          )
    ''')
    cur.execute('''
        create table msgrefs
          (
            messageid TEXT,
            reference TEXT,
            FOREIGN KEY(reference) REFERENCES messages(messageid)
          )
    ''')
    cur.execute('''
        create table msgreplies
          (
            messageid TEXT,
            parent TEXT,
            FOREIGN KEY(parent) REFERENCES messages(messageid)
          )
    ''')
    conn.commit()

def ensure_main_indexes(conn):
    cur = conn.cursor()
    cur.execute("create index if not exists msgid_index"
                "  on messages"
                "  (messageid)")
    cur.execute("create index if not exists msgrefs_index"
                "  on msgrefs"
                "  (reference)")
    cur.execute("create index if not exists msgreplies_index"
                "  on msgreplies"
                "  (parent)")
    conn.commit()

def create_topic_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        create table topics (
          topic TEXT,
          messageid TEXT,
          FOREIGN KEY(messageid) REFERENCES messages(messageid)
        )"""
    )
    conn.commit()

def ensure_topic_indexes(conn):
    cur = conn.cursor()
    cur.execute("create index if not exists topic_index"
                "  on topics"
                "  (topic, messageid)")
    conn.commit()
