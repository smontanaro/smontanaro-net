#!/usr/bin/env python

"""search index database bits for CR archive"""

import os
import pickle                             # nosec
import sqlite3
import tempfile

from flask import current_app

from .dates import convert_ts_bytes
from .log import eprint

## TODO: This really cries out to be a class. It would allow persistent
## TODO: connections, measurement of (cached and non-cached) query performance,
## TODO: and simpler API (not always passing connections or cursors around).

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
    cached = read_from_cache(term)
    if not cached:
        cur = conn.cursor()
        filenames = set()
        for (filename, fragment) in cur.execute(
            "select distinct filename, fragment"
            "  from file_search fs, search_terms st"
            "  where (st.term like ? or st.term like ? or st.term = ?)"
            "    and st.rowid = fs.reference",
            (f"% {term}", f"{term} %", term,)):
            # with the more generous term matching we can get multiple
            # fragments per filename. Just return one, which isn't terribly
            # important.
            if filename not in filenames:
                filenames.add(filename)
                cached.append((filename, fragment))
        save_to_cache(term, cached)
    for (filename, fragment) in cached:
        yield (filename, fragment)


CACHE_DIR = os.path.join(os.environ.get("CRDIR", os.getcwd()),
                         "search_cache")
CACHE_INDEX = os.path.join(CACHE_DIR, "index.pkl")

def read_from_cache(term):
    "look up term in cache and return whatever is there"
    if not os.path.exists(CACHE_INDEX):
        eprint(f"cache miss (no index): {term!r}")
        return []
    with open(CACHE_INDEX, "rb") as fobj:
        index = pickle.load(fobj)         # nosec
    if term in index:
        try:
            with open(index[term], "rb") as fobj:
                eprint(f"cache hit: {term!r}")
                return pickle.load(fobj)   # nosec
        except OSError:
            # remove the offending term
            del index[term]
            with open(CACHE_INDEX, "wb") as fobj:
                pickle.dump(index, fobj)
    eprint(f"cache miss (missing term): {term!r}")
    return []

def save_to_cache(term, result):
    "save search result to cache"
    if not os.path.exists(CACHE_DIR):
        os.mkdir(CACHE_DIR)
    if not os.path.exists(CACHE_INDEX):
        index = {}
    else:
        with open(CACHE_INDEX, "rb") as fobj:
            index = pickle.load(fobj)     # nosec
    cache_file = index.get(term)
    if cache_file is None:
        (fd, cache_file) = tempfile.mkstemp(dir=CACHE_DIR)
        os.close(fd)
        index[term] = cache_file
    with open(cache_file, "wb") as fobj:
        pickle.dump(result, fobj)
    with open(CACHE_INDEX, "wb") as fobj:
        pickle.dump(index, fobj)


def have_term(term, cur=None):
    "return rowid if we already have term in the database, else zero"
    if cur is None:
        conn = ensure_search_db(current_app.config["SRCHDB"])
        cur = conn.cursor()
    else:
        conn = None
    try:
        count = cur.execute("select count(*) from search_terms"
                            "  where term = ?", (term,)).fetchone()[0]
        if not count:
            return 0
        rowid = cur.execute("select rowid from search_terms"
                            "  where term = ?", (term,)).fetchone()[0]
        return rowid
    finally:
        if conn is not None:
            conn.close()

def add_term(term, cur=None):
    "make sure term is in database, return its rowid"
    if cur is None:
        conn = ensure_search_db(current_app.config["SRCHDB"])
        cur = conn.cursor()
    else:
        conn = None
    try:
        if rowid := have_term(term, cur):
            return rowid
        cur.execute("insert into search_terms values (?)", (term,))
        return cur.lastrowid
    finally:
        if conn is not None:
            conn.close()
