#!/usr/bin/env python

"generate date index similar to what MhonARC would do"

import argparse
import html
import itertools
import sqlite3
import sys

from smontanaro import dates

def date_key(record):
    "groupby key func"
    return record["ts"].date()

def generate_link(r):
    "HTML for a single message"
    root = "(T)&nbsp;" if r['is_root'] else ""
    return (f'''<a name="{r['seq']:05d}">'''
            f'''{root}'''
            f'''<a href="/CR/{r['year']}/{r['month']:02d}/{r['seq']:05d}">'''
            f'''{html.escape(r['subject'])}</a></a>'''
            f''' {html.escape(r["sender"])}''')

def generate_index(records):
    "html fragment output"

    print('<p>')
    print('"(T)" is part of an incomplete attempt to allow browsing a complete thread.')
    print("As you can probably tell, it's not exactly working yet.")
    print('</p>')

    for (dt, chunk) in itertools.groupby(records, date_key):
        print(f'''<h2>{dt.strftime("%d %b %Y")}</h2>''')
        print('''<ul style="column-count: auto; column-width: 300px;" class="no-bullets">''')
        for r in chunk:
            print('''<li>''')
            print(generate_link(r))
            print('''</li>''')
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
