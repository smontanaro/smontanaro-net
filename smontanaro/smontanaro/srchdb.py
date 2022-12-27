#!/usr/bin/env python

"""search index database bits for CR archive"""

import os
import sqlite3

from .dates import convert_ts_bytes

def ensure_search_db(sqldb):
    "make sure the database and its schema exist"
    create = not os.path.exists(sqldb) or os.path.getsize(sqldb) == 0
    sqlite3.register_converter("TIMESTAMP", convert_ts_bytes)
    conn = sqlite3.connect(sqldb, detect_types=(sqlite3.PARSE_DECLTYPES
                                                | sqlite3.PARSE_COLNAMES))
    if create:
        create_tables(conn)
        ensure_indexes(conn)
    return conn

def create_tables(conn):
    cur = conn.cursor()
    cur.execute('''
        create table search_terms
          (
            term TEXT PRIMARY KEY
          )
    ''')
    cur.execute('''
        create table file_search
          (
            filename TEXT,
            fragment TEXT,
            reference TEXT,
            FOREIGN KEY(reference) REFERENCES search_terms(term)
          )
    ''')
    conn.commit()

def ensure_indexes(conn):
    cur = conn.cursor()
    cur.execute("create index if not exists filename_index"
                "  on file_search"
                "  (reference)")
    cur.execute("create index if not exists search_index"
                "  on search_terms"
                "  (term)")
    conn.commit()

def get_page_fragments(conn, term):
    "return list (filename, fragment) tuples matching term"
    cur = conn.cursor()
    for (filename, fragment) in cur.execute(
        "select filename, fragment from file_search fs, search_terms st"
        "  where st.term = ?"
        "    and st.rowid = fs.reference", (term,)):
        yield (filename, fragment)
