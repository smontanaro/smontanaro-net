#!/usr/bin/env python

"associate email address with wooljersey.com URLS"

import csv
import email
import sys

from smontanaro.util import read_message

def main():
    writer = csv.DictWriter(sys.stdout, ["sender", "wjref"],
        quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for fname in sys.stdin:
        msg = read_message(fname.strip())
        sender = msg["From"].strip()
        for word in msg.extract_text().split():
            if "wooljersey.com" in word:
                writer.writerow({"sender": sender, "wjref": word})

if __name__ == "__main__":
    sys.exit(main())
