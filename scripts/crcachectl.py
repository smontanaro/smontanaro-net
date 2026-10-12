#!/usr/bin/env python3

"List or delete search cache entries"

import argparse
import csv
import datetime
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
        writer = csv.DictWriter(sys.stdout, fieldnames=["date", "status", "key", "file"])
        writer.writeheader()
        if index:
            for key in sorted(index):
                path = relpath(index[key], args.dir)
                status = "okay"
                if not os.path.exists(path):
                    status = "missing"
                    dt = datetime.datetime.fromtimestamp(0)
                else:
                    stamp = os.path.getmtime(path)
                    dt = datetime.datetime.fromtimestamp(stamp)
                    with open(path, "rb") as fp:
                        if not pickle.load(fp): # nosec
                            status = "empty"
                writer.writerow({
                    "date": dt,
                    "key": key,
                    "file": index[key],
                    "status": status
                    })
            return 0

    delkeys = set()
    if args.empty:
        for key in index:
            path = relpath(path, args.dir)
            if not os.path.exists(path):
                delkeys.add(key)
            else:
                with open(relpath(path, args.dir), "rb") as fp:
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
        if not os.path.exists(path):
            print("missing", repr(key), path)
            if not args.quiet:
                print("delete", repr(key), path)
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        del index[key]
        del path
    if delkeys:
        with open(relpath("index.pkl", args.dir), "wb") as cache:
            pickle.dump(index, cache)

    return 0

def relpath(path, basedir):
    """map path to basedir"""
    return os.path.join(basedir, os.path.basename(path))

if __name__ == "__main__":
    sys.exit(main())
