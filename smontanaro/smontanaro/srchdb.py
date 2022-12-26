#!/usr/bin/env python

"""search index database bits for CR archive"""

import os
import sqlite3

from flask import current_app

from .dates import convert_ts_bytes

def ensure_search_db(sqldb):
    "make sure the database and its schema exist"
    create = not os.path.exists(sqldb) or os.path.getsize(sqldb) == 0
    sqlite3.register_converter("TIMESTAMP", convert_ts_bytes)
    conn = sqlite3.connect(sqldb, detect_types=(sqlite3.PARSE_DECLTYPES
                                                | sqlite3.PARSE_COLNAMES))
    if create:
        create_tables(conn)
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

def get_matches(term):
    "return list (filename, fragment) tuples matching term"
    app = current_app()
    conn = ensure_search_db(app.config["SRCHDB"])
    cur = conn.cursor()
    cur.execute("select filename, fragment from file_search, search_terms"
                "  where term = ?"
                "    and search_terms.term = file_search.reference",
                (term,))
    return cur.fetchall()
