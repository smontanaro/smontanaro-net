#!/usr/bin/env python

"generate date index similar to what MhonARC would do"

import argparse
import html
import itertools
import re
import sqlite3
import sys

from smontanaro import dates
from smontanaro.util import generate_link


def date_key(record):
    "groupby key func"
    return record["ts"].date()


def generate_index(records):
    "html fragment output"
    for (dt, chunk) in itertools.groupby(records, date_key):
        print(f'''<h2>{dt.strftime("%d %b %Y")}</h2>''')
        print('''<ul style="column-count: auto; column-width: 300px;" class="list-group-flush">''')
        for r in chunk:
            print(f"<li>{generate_link(r)}</li>")
        print("</ul>")

def main():
    "see __doc__"
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", dest="verbose", action="count",
                        default=0)
    parser.add_argument("-d", "--database", dest="sqldb",
                        help="SQLite3 database file", required=True)
    parser.add_argument("year", type=int)
    parser.add_argument("month", type=int)
    args = parser.parse_args()

    sqlite3.register_converter("TIMESTAMP", dates.convert_ts_bytes)
    conn = sqlite3.connect(args.sqldb, detect_types=(sqlite3.PARSE_DECLTYPES
                                                     | sqlite3.PARSE_COLNAMES))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    records = cur.execute("select m.*"
                          "  from messages m"
                          "  where m.year = ?"
                          "    and m.month = ?"
                          "  order by m.ts",
                          (args.year, args.month)).fetchall()

    generate_index(records)

    return 0

if __name__ == "__main__":
    sys.exit(main())
