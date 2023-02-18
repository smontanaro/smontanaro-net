#!/usr/bin/env python

"associate email address with wooljersey.com URLS"

import csv
import email
import sys

def main():
    writer = csv.DictWriter(sys.stdout, ["sender", "wjref"], quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for fname in sys.stdin:
        with open(fname.strip(), "rb") as fbytes:
            msg = email.message_from_bytes(fbytes.read())
            sender = msg["From"].strip()
            try:
                for word in msg.get_payload(decode=False).split():
                    if "wooljersey.com/gallery" in word:
                        writer.writerow({"sender": sender, "wjref": word})
            except AttributeError:
                print(fname, "multipart?", file=sys.stderr)

if __name__ == "__main__":
    sys.exit(main())
