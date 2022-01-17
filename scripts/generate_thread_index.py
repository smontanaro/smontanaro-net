#!/usr/bin/env python

"generate thread index similar to what MhonARC would do"

import argparse
import html
import sqlite3
import sys

from smontanaro import util

def thread_key(record):
    "groupby key func"
    return record["messageid"]

def generate_link(r, ind):
    "HTML for a single message"
    root = "(T)&nbsp;" if r['is_root'] else ""
    return (f'''{ind}<a name="{r['seq']:05d}">'''
            f'''{root}'''
            f'''<a href="/CR/{r['year']}/{r['month']:02d}/{r['seq']:05d}">'''
            f'''{html.escape(r['subject'])}</a></a>'''
            f''' {html.escape(r["sender"])}''')

def generate_index(records, cur, level):
    "html fragment output"

    ul_ind = "  " * level
    li_ind = "  " * (level + 1)
    print(f'''{ul_ind}<ul style="column-count: 1" class="no-bullets">''')
    for r in records:
        print(f'''{li_ind}<li>''')
        print(generate_link(r, li_ind + "  "))
        # Find any references where this message is the parent
        refs = cur.execute("select distinct m.messageid, m.subject,"
                           " m.sender, m.year, m.month, m.seq, m.is_root"
                           "  from messages m"
                           "  join msgrefs r"
                           "  on r.messageid = m.messageid"
                           "  where r.reference = ?"
                           "order by m.ts",
                           (r["messageid"],)).fetchall()
        if refs:
            generate_index(refs, cur, level + 1)
        print(f'''{li_ind}</li>''')
    print(f"{ul_ind}</ul>")

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

    sqlite3.register_converter("TIMESTAMP", util.convert_ts_bytes)
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

    generate_index(records, cur, 0)

    return 0

if __name__ == "__main__":
    sys.exit(main())
