#!/usr/bin/env python

"Rewrite MHonARC msg0NNNN.html hrefs with NNNN"

import argparse
import os
import re
import sys
import tempfile

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

def make_edits(fullpath):
    "do the msg0NNNN.html -> NNNN+1 dance"
    raw = read_file(fullpath)
    split = re.split(r'''href="msg([0-9]+)[.]html"''', raw)
    for (indx, num) in enumerate(split):
        if indx % 2:
            split[indx] = f'''href="{(int(num, 10)+1):04d}"'''
    return "".join(split)

def main():
    "see __doc__"
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--diff", dest="diff", action="store_true",
                        default=False, help="just display diffs")
    parser.add_argument("top")
    args = parser.parse_args()

    for (dirpath, _dirnames, filenames) in os.walk(args.top):
        for filename in filenames:
            if not filename.endswith(".html"):
                continue
            fullpath = os.path.join(dirpath, filename)
            print(fullpath)

            cooked = make_edits(fullpath)

            # set up for temporary or permanent output
            if args.diff:
                fd, outf = tempfile.mkstemp()
                with os.fdopen(fd, "w", encoding="utf-8") as fobj:
                    fobj.write(cooked)
            else:
                if not os.path.exists(f"{fullpath}.orig"):
                    os.rename(fullpath, f"{fullpath}.orig")
                outf = fullpath
                with open(fullpath, "w", encoding="utf-8") as fobj:
                    fobj.write(cooked)

            # if changes are temporary, diff them against the original, then discard
            if args.diff:
                os.system(f"diff -u {fullpath} {outf}") # nosec
                os.unlink(outf)

if __name__ == "__main__":
    sys.exit(main())
