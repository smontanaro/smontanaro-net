#!/usr/bin/env python3

"""
trivial little script to check buildindex.py-generated keys
"""

import sqlite3
import sys

if __name__ == "__main__":
    conn = sqlite3.connect(sys.argv[1])
    cur = conn.cursor()
    ones = twos = total = 0
    for (term, count) in cur.execute("select st.term, count(fs.fragment)"
                                     " from search_terms st, file_search fs"
                                     "  where fs.reference = st.rowid"
                                     "  group by fs.reference"
                                     "  order by st.term"):
        total += 1
        if count == 1:
            ones += 1
        elif count == 2:
            twos += 1
        else:
            print(f"{term}: {count}")

    print(f"{ones} terms with just one ref.")
    print(f"{twos} terms with just two refs.")
    print(f"{total} total terms.")
