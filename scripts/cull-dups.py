#!/usr/bin/env python

"""
Cull duplicate email messages. This is prompted by looking at the
2004-09/eml-files directory where there are tons of duplicates where
many aren't named in the normal classicrendezvous.10409.NNNN.eml
form.
"""

import hashlib
import os
import sys

def main():
    fdir = sys.argv[1]
    pairs = {}
    to_delete = set()

    for (dirpath, _dirnames, filenames) in os.walk(fdir):
        for fname in filenames:
            if not fname.endswith(".eml"):
                continue
            with open(os.path.join(dirpath, fname), mode="rb") as fobj:
                digest = hashlib.md5(fobj.read()).hexdigest()
            if digest not in pairs:
                pairs[digest] = fname
                continue
            first = pairs[digest]
            if (first.startswith("classicrendezvous") and
                not fname.startswith("classicrendezvous")):
                delete = fname
            elif (fname.startswith("classicrendezvous") and
                  not first.startswith("classicrendezvous")):
                delete = first
                pairs[digest] = fname
            else:
                print("Hmmm...", first, fname, file=sys.stderr)
                continue
            delete = os.path.join(dirpath, delete)
            print("will delete", delete)
            to_delete.add(delete)

    dbase = os.path.split(fdir)[-1]
    dst_dir = f"to_delete/{dbase}"
    if not os.path.exists(dst_dir):
        os.mkdir(dst_dir)
    for fname in to_delete:
        os.rename(fname, os.path.join(dst_dir, os.path.split(fname)[-1]))

if __name__ == "__main__":
    sys.exit(main())
