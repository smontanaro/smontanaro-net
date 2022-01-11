#!/usr/bin/env python

"generate date index similar to what MhonARC would do"

import argparse
import datetime
import html
import itertools
import sqlite3
import sys

def convert_ts_bytes(stamp):
    "SQLite3 converter for tz-aware datetime objects"
    stamp = stamp.decode("utf-8")
    return datetime.datetime.fromisoformat(stamp)

def date_key(record):
    "groupby key func"
    return record["ts"].date()

def generate_link(r):
    "HTML for a single message"
    return (f'''<a name="{r['seq']:05d}">'''
            f'''<a href="/CR/{r['year']}/{r['month']}/{r['seq']:05d}">'''
            f'''{html.escape(r['subject'])}</a></a>'''
            f''' {html.escape(r["sender"])}''')

def generate_index(records):
    "html fragment output"
    for (dt, chunk) in itertools.groupby(records, date_key):
        print(f'''<h2>{dt.strftime("%d %b %Y")}</h2>''')
        # print(f'''<a href="#top">Top</a>''')
        print(f'''<ul class="no-bullets">''')
        for r in chunk:
            print(f'''<li>''')
            print(generate_link(r))
            print(f'''</li>''')
        print("</ul>")

def main():
    "see __doc__"
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", dest="verbose", action="count",
                        default=0)
    parser.add_argument("-d", "--database", dest="sqldb", help="SQLite3 database file",
                        required=True)
    parser.add_argument("year", type=int)
    parser.add_argument("month", type=int)
    args = parser.parse_args()

    sqlite3.register_converter("TIMESTAMP", convert_ts_bytes)
    conn = sqlite3.connect(args.sqldb, detect_types=(sqlite3.PARSE_DECLTYPES
                                                     | sqlite3.PARSE_COLNAMES))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    records = cur.execute("select m.*"
                          "  from messageids m"
                          "  where m.year = ?"
                          "    and m.month = ?"
                          "  order by m.ts",
                          (args.year, args.month)).fetchall()

    generate_index(records)

    return 0

if __name__ == "__main__":
    sys.exit(main())
