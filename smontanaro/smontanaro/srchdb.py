#!/usr/bin/env python

"""search index database bits for CR archive"""

import os
import pickle                             # nosec
import sqlite3
import tempfile

from .dates import register_sqlite3_adapters as _RSA
_RSA()
del _RSA

# from .log import eprint

CACHE_DIR = os.path.join(os.environ.get("CRDIR", os.getcwd()),
                         "search_cache")

class SearchDB:
    "class representing the search database"
    def __init__(self):
        self.sqldb = None
        self.connection = None
        self.cache_index = None

    def set_database(self, sqldb):
        "set database file if not already set"
        # class init and database setting are separated more-or-less as a
        # side-effect of the way Flask works. The singleton SearchDB instance
        # is created below, while the database is set in views.init_search.
        if self.sqldb is not None and self.sqldb != sqldb:
            self.sqldb = None

        if self.sqldb is None:
            self.sqldb = sqldb
            sqldb_dir = os.path.dirname(sqldb)
            self.cache_index = os.path.join(sqldb_dir,
                "search_cache", "index.pkl")
            self.ensure_connection()

    def ensure_connection(self):
        "make sure the database and its schema exist"
        if self.connection is not None:
            self.connection.close()

        self.connection = sqlite3.connect(self.sqldb,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self._create_tables()
        self._ensure_indexes()

    def get_page_fragments(self, term):
        "return list (filename, fragment, subject, sender) tuples matching term"
        cached = self._read_from_cache(term)
        if cached is None:              # Have yet to search for this term
            cached = []
            cur = self.connection.cursor()
            filenames = set()
            for (filename, fragment, subject, sender) in cur.execute(
                "select distinct filename, fragment, subject, sender"
                "  from file_search fs, search_terms st"
                "  where st.term like ?"
                "    and st.rowid = fs.reference",
                (f"%{term}%",)):
                # with the more generous term matching we can get multiple
                # fragments per filename. Just return one, which isn't terribly
                # important.
                if filename not in filenames:
                    filenames.add(filename)
                    cached.append((filename, fragment, subject, sender))
            self._save_to_cache(term, cached)
        for record in cached:
            yield record

    def have_term(self, term):
        "return rowid if we already have term in the database, else zero"
        cur = self.connection.cursor()
        count = cur.execute("select count(*) from search_terms"
                            "  where term = ?", (term,)).fetchone()[0]
        if not count:
            return 0
        rowid = cur.execute("select rowid from search_terms"
                            "  where term = ?", (term,)).fetchone()[0]
        return rowid

    def _create_tables(self):
        cur = self.connection.cursor()
        cur.execute('''
            create table if not exists search_terms
              (
                term TEXT PRIMARY KEY
              )
        ''')
        cur.execute('''
            create table if not exists file_search
              (
                filename TEXT,
                fragment TEXT,
                subject TEXT,
                sender TEXT,
                reference INTEGER,
                FOREIGN KEY(reference) REFERENCES search_terms(rowid)
              )
        ''')
        self.connection.commit()

    def _ensure_indexes(self):
        cur = self.connection.cursor()
        cur.execute("create index if not exists filename_index"
                    "  on file_search"
                    "  (reference)")
        cur.execute("create index if not exists search_index"
                    "  on search_terms"
                    "  (term)")
        self.connection.commit()

    def _read_from_cache(self, term):
        "look up term in cache and return whatever is there"
        # None return value means we haven't seen this search term before. In
        # contrast, a completed search with no results would return an empty
        # list.
        if not os.path.exists(self.cache_index):
            # eprint(f"cache miss (no index): {term!r}")
            return None
        with open(self.cache_index, "rb") as fobj:
            index = pickle.load(fobj)         # nosec
        if term in index:
            try:
                with open(index[term], "rb") as fobj:
                    # eprint(f"cache hit: {term!r}")
                    return pickle.load(fobj)   # nosec
            except OSError:
                # remove the offending term
                del index[term]
                with open(self.cache_index, "wb") as fobj:
                    pickle.dump(index, fobj)
        # eprint(f"cache miss (missing term): {term!r}")
        return None

    def _save_to_cache(self, term, result):
        "save search result to cache"
        if not os.path.exists(CACHE_DIR):
            os.mkdir(CACHE_DIR)
        if not os.path.exists(self.cache_index):
            index = {}
        else:
            with open(self.cache_index, "rb") as fobj:
                index = pickle.load(fobj)     # nosec
        cache_file = index.get(term)
        if cache_file is None:
            (fd, cache_file) = tempfile.mkstemp(dir=CACHE_DIR)
            os.close(fd)
            index[term] = cache_file
        with open(cache_file, "wb") as fobj:
            pickle.dump(result, fobj)
        with open(self.cache_index, "wb") as fobj:
            pickle.dump(index, fobj)

    def __getattr__(self, attr):
        return getattr(self.connection, attr)

SRCHDB = SearchDB()
