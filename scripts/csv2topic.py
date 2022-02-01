#!/usr/bin/env python

"""
extract topic and message-id fields from input csv, then generate insert statements
for topics table. CSV file is read from stdin. SQL statements go to stdout.
"""

import csv
import sys

TEMPLATE = """INSERT INTO topics VALUES('{topic}','{msgid}');"""

def main():
    "see __doc__"
    rdr = csv.DictReader(sys.stdin)
    for row in rdr:
        msgid = row["message-id"]
        for topic in row["topic"].split(","):
            print(TEMPLATE.format(topic=topic.strip(), msgid=msgid))

if __name__ == "__main__":
    sys.exit(main())
