#!/usr/bin/env python3

"List or delete search cache entries"

import argparse
import os
import pickle                           # nosec
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", dest="verbose", default=False,
                        help="Noisier list output", action="store_true")
    parser.add_argument("-q", "--quiet", dest="quiet", default=False,
                        help="Quieter list output", action="store_true")
    parser.add_argument("-l", "--list", dest="list", default=False,
                        help="List cache keys", action="store_true")
    parser.add_argument("-d", "--delete", dest="keys", action="append",
                        help="Delete the given key")
    parser.add_argument("-e", "--empty", dest="empty", action="store_true",
                        help="Delete all empty keys")
    parser.add_argument("--delete-all", dest="delete_all", action="store_true",
                        default=False, help="Delete all keys")
    parser.add_argument("--dir", dest="dir", default="./search_cache",
                        help="Name the cache directory")
    args = parser.parse_args()

    if args.quiet and args.verbose:
        print("Can't be both quiet and verbose!", file=sys.stderr)
        return 1

    with open(relpath("index.pkl", args.dir), "rb") as cache:
        index = pickle.load(cache)      # nosec

    if args.list:
        if index:
            if not args.quiet:
                print("Cache keys:")
            for key in sorted(index):
                if not args.quiet:
                    print(" ", key, end="")
                if args.verbose:
                    print(f" ({index[key]})", end="")
                    path = relpath(index[key], args.dir)
                    if not os.path.exists(path):
                        print(" missing", end="")
                    else:
                        with open(path, "rb") as fp:
                            if not pickle.load(fp): # nosec
                                print(" empty", end="")
                if not args.quiet:
                    print()
        else:
            if not args.quiet:
                print("Empty cache")
            return 0

    delkeys = set()
    if args.empty:
        for key in index:
            path = relpath(index[key], args.dir)
            if not os.path.exists(path):
                delkeys.add(key)
            else:
                with open(relpath(index[key], args.dir), "rb") as fp:
                    if not pickle.load(fp): # nosec
                        delkeys.add(key)
    elif args.keys is not None:
        delkeys = set(args.keys)
    elif args.delete_all:
        # convert keys to set() to allow deletion in the loop
        delkeys = set(index)
    for key in delkeys:
        # Despite abs path in the index, only remove files relative to
        # the cache dir.  This is marginally safer and makes testing
        # easier.
        path = relpath(index[key], args.dir)
        if os.path.exists(path):
            if not args.quiet:
                print("delete", repr(key), path)
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        del index[key]
    if delkeys:
        with open(relpath("index.pkl", args.dir), "wb") as cache:
            pickle.dump(index, cache)

    return 0

def relpath(path, basedir):
    """map path to basedir"""
    return os.path.join(basedir, os.path.basename(path))

if __name__ == "__main__":
    sys.exit(main())
