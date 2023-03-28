#!/usr/bin/env python3

"List or delete search cache entries"

import argparse
import os
import pickle
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", dest="verbose", default=False,
                        help="Noisier list output", action="store_true")
    parser.add_argument("-l", "--list", dest="list", default=False,
                        help="List cache keys", action="store_true")
    parser.add_argument("-d", "--delete", dest="keys", action="append",
                        help="Delete the given key")
    parser.add_argument("--delete-all", dest="delete_all", action="store_true",
                        default=False, help="Delete all keys")
    parser.add_argument("--dir", dest="dir", default="./search_cache",
                        help="Name the cache directory")
    args = parser.parse_args()

    with open(os.path.join(args.dir, "index.pkl"), "rb") as cache:
        index = pickle.load(cache)

    if args.list:
        if index:
            print("Cache keys:")
            for key in sorted(index):
                print(" ", key, end="")
                if args.verbose:
                    print(f" ({index[key]})", end="")
                print()
        else:
            print("Empty cache")
            return 0

    if args.keys is not None or args.delete_all:
        delfnames = set()
        dkeys = args.keys if not args.delete_all else set(index)
        for key in dkeys:
            if key in index:
                # Despite abs path in the index, only remove files relative to
                # the cache dir.  This is marginally safer and makes testing
                # easier.
                fname = os.path.join(args.dir, os.path.basename(index[key]))
                print("delete", key, fname)
                delfnames.add(fname)
                try:
                    os.unlink(fname)
                except FileNotFoundError:
                    pass
                del index[key]
        if delfnames:
            # modified, rewrite index file
            with open(os.path.join(args.dir, "index.pkl"), "wb") as cache:
                pickle.dump(index, cache)

    return 0

if __name__ == "__main__":
    sys.exit(main())
