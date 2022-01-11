#!/usr/bin/env python

"generate thread index similar to what MhonARC would do"

import argparse
import datetime
import html
import sqlite3
import sys

def convert_ts_bytes(stamp):
    "SQLite3 converter for tz-aware datetime objects"
    stamp = stamp.decode("utf-8")
    return datetime.datetime.fromisoformat(stamp)

def thread_key(record):
    "groupby key func"
    return record["messageid"]

def generate_link(r):
    "HTML for a single message"
    return (f'''<a name="{r['seq']:05d}">'''
            f'''<a href="/CR/{r['year']}/{r['month']}/{r['seq']:05d}">'''
            f'''{html.escape(r['subject'])}</a></a>'''
            f''' {html.escape(r["sender"])}''')

def generate_index(records, cur, level):
    "html fragment output"
    print(f'''<ul class="no-bullets">''')
    for r in records:
        print(f'''<li>''')
        print(generate_link(r))
        # Find any direct references to this message.
        refs = cur.execute("select distinct m.messageid, m.subject,"
                           " m.sender, m.year, m.month, m.seq"
                           "  from messageids m"
                           "  join msgrefs r"
                           "  on r.messageid = m.messageid"
                           "  where r.reference = ?"
                           "order by m.ts",
                           (r["messageid"],)).fetchall()
        if refs:
            generate_index(refs, cur, level + 1)
            # print(f'''<ul>''')
            # for ref in refs:
            #     print(f'''<li>''')
            #     print(generate_link(ref))
            #     print(f'''</li>''')
            # print(f'''</ul>''')
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

    # # Yikes! SQLite doesn's support right joins or full outer joins. I
    # # didn't come up with this query. Stack Overflow to the rescue:
    # #
    # # https://stackoverflow.com/questions/1923259/full-outer-join-with-sqlite
    # records = cur.execute("select distinct m.year, m.month, m.seq,"
    #                       "    m.messageid, r.reference"
    #                       "  from messageids m"
    #                       "  left join msgrefs r"
    #                       "    on m.messageid = r.reference"
    #                       "  where m.year = ?"
    #                       "    and m.month = ?"
    #                       "union all"
    #                       "select distinct m.year, m.month, m.seq,"
    #                       "    m.messageid, null"
    #                       "  from msgrefs r"
    #                       "  left join messageids m"
    #                       "    on r.reference = m.messageid"
    #                       "  where r.reference is null"
    #                       "    and m.year = ?"
    #                       "    and m.month = ?"
    #                       "order by m.messageid, m.ts",
    #                       (args.year, args.month, args.year, args.month).fetchall())

    records = cur.execute("select distinct m.messageid, m.subject,"
                          " m.sender, m.year, m.month, m.seq"
                          "  from messageids m"
                          "  where m.year = ?"
                          "    and m.month = ?"
                          "order by m.ts",
                          (args.year, args.month)).fetchall()

    generate_index(records, cur, 0)

    return 0

if __name__ == "__main__":
    sys.exit(main())
