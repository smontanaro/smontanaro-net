#!/usr/bin/env python

"generate thread index similar to what MhonARC would do"

import argparse
import html
import re
import sqlite3
import sys

from smontanaro import dates

def thread_key(record):
    "groupby key func"
    return record["messageid"]

def generate_link(r):
    "HTML for a single message"
    root = "" # "(T)&nbsp;" if r['is_root'] else ""
    sub = re.sub(r"\s+", " ", r["Subject"])
    return (f'''<a name="{r['seq']:04d}">'''
            f'''{root}'''
            f'''<a href="/CR/{r['year']}/{r['month']:02d}/{r['seq']:04d}">'''
            f'''{html.escape(sub)}</a></a>'''
            f''' {html.escape(r["sender"])}''')

class IndexGenerator:
    "generate thread index, trying to avoid duplicates"
    def __init__(self):
        self.seen = set()
        print('''\t\t\t\t\t\t<!-- -*-web-*- -->''')

    def generate_index(self, records, cur, level):
        "html fragment output"
        ul_ind = "  " * level
        records = [r for r in records if r["messageid"] not in self.seen]
        if records:
            print(f'''{ul_ind}'''
                  '''<ul style="column-count: auto; column-width: 500px"'''
                  ''' class="no-bullets">''')
            self.generate_list(records, cur, level)
            print(f"{ul_ind}</ul>")

    def generate_list(self, records, cur, level):
        li_ind = "  " * (level + 1)
        for r in records:
            self.seen.add(r["messageid"])
            print(f'''{li_ind}<li>''', end="")
            print(generate_link(r), end="")
            # find any references where this message is the parent
            refs = self.get_refs(cur, r["messageid"])
            if refs:
                print()
                self.generate_index(refs, cur, level + 2)
            print(f'''{li_ind}</li>''')

    def get_refs(self, cur, msgid):
        return cur.execute("select distinct m.messageid, m.subject,"
                           " m.sender, m.year, m.month, m.seq, m.is_root"
                           "  from messages m"
                           "  join msgrefs r"
                           "  on r.messageid = m.messageid"
                           "  where r.reference = ?"
                           "order by m.ts",
                           (msgid,)).fetchall()

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

    gen = IndexGenerator()
    gen.generate_index(records, cur, 0)

    return 0

if __name__ == "__main__":
    sys.exit(main())
