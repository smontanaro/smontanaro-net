#!/usr/bin/env python

"""
list email messages by their Date header, not their file timestamp.
"""

import email
import os
import sys

from smontanaro.util import parse_date

def main():
    fdir = sys.argv[1]
    pairs = []                  # (timestamp, filename)

    for (dirpath, _dirnames, filenames) in os.walk(fdir):
        for fname in filenames:
            if fname[-4:] != ".eml":
                continue
            fname = os.path.join(dirpath, fname)
            for encoding in ("utf-8", "latin-1"):
                with open(fname, encoding=encoding) as fobj:
                    try:
                        msg = email.message_from_file(fobj)
                    except (UnicodeDecodeError, email.errors.MessageError):
                        continue
                    else:
                        break
            if msg.defects:
                print(fname, msg.defects, file=sys.stderr)
                continue
            stamp = parse_date(msg["Date"])
            pairs.append((stamp, fname))
    for (stamp, fname) in sorted(pairs):
        print(stamp.strftime("%d %b %Y %T %z"), fname)

if __name__ == "__main__":
    sys.exit(main())
