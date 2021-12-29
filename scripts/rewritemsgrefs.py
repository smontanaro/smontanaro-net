#!/usr/bin/env python

"Rewrite MHonARC msgNNNNN.html hrefs with MMMM, where MMMM == NNNN + 1."

import argparse
import os
import re
import sys

def read_file(filename):
    "open and read filename's contents, trying utf-8 or latin-1."
    encodings = ("utf-8", "latin-1")
    for encoding in encodings:
        try:
            with open(filename, encoding=encoding) as fobj:
                return fobj.read()
        except UnicodeDecodeError:
            pass
    raise UnicodeDecodeError(f"{filename} unreadable with these encodings: {encodings}")

def main():
    "see __doc__"
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--dry-run", dest="dryrun", action="store_true",
                        default=False)
    parser.add_argument("top")
    args = parser.parse_args()

    for (dirpath, _dirnames, filenames) in os.walk(args.top):
        for filename in filenames:
            if not filename.endswith(".html"):
                continue
            fullpath = os.path.join(dirpath, filename)
            print(fullpath, end="")
            if args.dryrun:
                print()
                continue
            raw = read_file(fullpath)
            split = re.split(r'''href="msg([0-9]+)[.]html"''', raw)
            repls = 0
            for (indx, num) in enumerate(split):
                if indx % 2:
                    split[indx] = f'''href="{(int(num, 10) + 1):04d}"'''
                    repls += 1
            cooked = "".join(split)
            if not os.path.exists(f"{fullpath}.orig"):
                os.rename(fullpath, f"{fullpath}.orig")
            with open(fullpath, "w", encoding="utf-8") as fobj:
                fobj.write(cooked)
            print(" replaced", repls, "occurrences")
if __name__ == "__main__":
    sys.exit(main())
