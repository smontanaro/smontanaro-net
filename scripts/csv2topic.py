#!/usr/bin/env python

"""
extract topic and message-id fields from input csv, then generate insert statements
for topics table. CSV file is read from stdin. SQL statements go to stdout.
"""

import csv
import sys

from smontanaro.util import get_message_bits, get_topic
from smontanaro.refdb import ensure_db

TEMPLATE = """INSERT INTO topics VALUES('{topic}','{message-id}'); -- {topic!r}, {ip}"""
URL = """https://www.smontanaro.net/{yr:4d}/{mo:02d}/{seq:04d}"""

def main():
    "see __doc__"
    conn = ensure_db(sys.argv[1])
    rdr = csv.DictReader(sys.stdin)
    yms = "yr mo seq".split()
    for row in rdr:
        existing = set((yr, mo, seq)
            for (yr, mo, seq, *rest) in get_topic(row["topic"], conn))
        if existing:
            print("--", existing)
        bits = get_message_bits(row["message-id"], conn)
        for part in bits:
            row.update(dict(zip(yms, part)))
            print("--", URL.format(**row), end=" ")
            if part in existing:
                print("(KNOWN)", end="")
            print()
        if not bits:
            print("--", end=" ")
        print(TEMPLATE.format(**row))

if __name__ == "__main__":
    sys.exit(main())
