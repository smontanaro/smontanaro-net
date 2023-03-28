#!/usr/bin/env python3

"List or delete search cache entries"

import argparse
import os
import pickle
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--list", dest="list", default=False,
                        help="List cache keys", action="store_true")
    parser.add_argument("-d", "--delete", dest="keys", action="append",
                        help="Delete the given key")
    parser.add_argument("--dir", dest="dir", default="./search_cache",
                        help="Name the cache directory")
    args = parser.parse_args()

    with open(os.path.join(args.dir, "index.pkl"), "rb") as cache:
        index = pickle.load(cache)

    if args.list:
        print("Cache keys:")
        for key in sorted(index):
            print(" ", key)

    if args.keys is not None:
        delkeys = set()
        for key in args.keys:
            if key in index:
                print("delete", key)
                delkeys.add(key)
                try:
                    os.unlink(index[key])
                except FileNotFoundError:
                    pass
                del index[key]
        if delkeys:
            # modified, rewrite index file
            with open(os.path.join(args.dir, "index.pkl"), "wb") as cache:
                pickle.dump(index, cache)

if __name__ == "__main__":
    sys.exit(main())
