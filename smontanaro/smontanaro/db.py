#!/usr/bin/env python

"""database bits for CR archive"""

import os
import random
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

def ensure_filter_cache(cachedb):
    if os.path.exists(cachedb):
        return sqlite3.connect(cachedb)

    cache_dir = os.path.dirname(cachedb)
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)
    file_cache = sqlite3.connect(cachedb)
    file_cache.execute("""
    create table filter_cache
      (
        pattern TEXT,
        in_out TEXT,
        filename TEXT
      )
    """)
    file_cache.execute("""
      create index if not exists filter_index
        on filter_cache
        (pattern, in_out)
    """)
    return file_cache

def get_topics_for(msgid, sqldb):
    "return list of topics associated with msgid"
    conn = ensure_db(sqldb)
    cur = conn.cursor()
    cur.execute("""
    select distinct topic from topics
      where messageid = ?
      order by topic
    """, (msgid,))
    return [t[0] for t in cur.fetchall()]

def get_random_topic(sqldb):
    "return list of all topics"
    conn = ensure_db(sqldb)
    cur = conn.cursor()
    cur.execute("select distinct topic from topics")
    all_topics = set(t[0] for t in cur.fetchall())

    # Now run through all topics and add their parents, etc
    new_topics = set()
    for topic in all_topics:
        while ":" in topic:
            topic = ":".join(topic.split(":")[0:-1])
            new_topics.add(topic)
    all_topics |= new_topics
    return random.choice(list(all_topics))
