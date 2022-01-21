#!/usr/bin/env python

"""Given source and destination directories containing email files,
rename the files in the destination to match the source as closely as
possible. Messages in the directories are compared by Message-ID.
"""

import argparse
import email
import os
import sys

from smontanaro.util import parse_date

def map_emails(src, dst):
    "pair up emails in src and dst directories by message-id."

    message_ids = {}
    source_files = 0
    for (dirpath, _dirnames, filenames) in os.walk(src):
        for filename in filenames:
            fname = os.path.join(dirpath, filename)
            with open(fname, "rb") as fobj:
                msg = email.message_from_bytes(fobj.read())
                if msg.defects:
                    print(f"defective message file {fname}: {msg.defects}. Skipping",
                          file=sys.stderr)
                    continue
            source_files += 1
            message_id = msg["message-id"]
            if message_id not in message_ids:
                message_ids[message_id] = {
                    "source": {
                        "filename": filename,
                        "message": msg,
                        },
                    "destination": {},
                }
            else:
                print(f"unexpected key: {message_id} -> {message_ids[message_id]}. Skipping",
                      file=sys.stderr)
                continue

    dest_files = 0
    dups = 0
    for (dirpath, _dirnames, filenames) in os.walk(dst):
        for filename in filenames:
            fname = os.path.join(dirpath, filename)
            with open(fname, "rb") as fobj:
                msg = email.message_from_bytes(fobj.read())
                if msg.defects:
                    print(f"defective message file {fname}: {msg.defects}. Skipping",
                          file=sys.stderr)
                    continue
            dest_files += 1
            message_id = msg["message-id"]
            if message_id in message_ids:
                dstd = message_ids[message_id]["destination"]
                if dstd:
                    dups += 1
                    print("duplicate", message_id, filename, "and", dstd["filename"],
                          file=sys.stderr)
                else:
                    dstd["filename"] = filename
                    dstd["message"] = msg
            else:
                message_ids[message_id] = {
                    "source": {},
                    "destination": {
                        "filename": filename,
                        "message": msg,
                        },
                }

    no_dst_mapping = 0
    no_src_mapping = 0
    for (key, dct) in message_ids.items():
        dfile = dct["destination"]["filename"] if dct["destination"] else None
        sfile = dct["source"]["filename"] if dct["source"] else None
        print(key, dfile, "->", sfile)
        if sfile is None:
            no_dst_mapping += 1
        if dfile is None:
            no_src_mapping += 1

    print("Found", source_files, "source messages")
    print("Found", dest_files, "destination messages", dups, "duplicates")
    print("Found", len(message_ids), "distinct message ids")
    print(no_dst_mapping, "can't be mapped to existing source names")
    print(no_src_mapping, "can't be mapped to existing destination names")

    return message_ids

def map_extras(message_ids, dst):
    "map dest files which have no corresponding source files"
    source_names = []
    for dct in message_ids.values():
        if dct["source"]:
            source_names.append(dct["source"]["filename"])

    max_source = max(source_names)
    parts = max_source.split(".")
    max_seq = int(parts[-2], 10)
    parts[-2] = "%04d"
    pattern = ".".join(parts)

    # Revisit the dest messages, sort by date and assign filenames
    # based on pattern and max_seq.
    msgs_to_map = []
    for (_msgid, dct) in message_ids.items():
        if not dct["source"]:
            msg = dct["destination"]["message"]
            filename = dct["destination"]["filename"]
            try:
                date = parse_date(msg["date"])
            except AttributeError:
                print("no date!", filename, file=sys.stderr)
            else:
                msgs_to_map.append((date, filename, msg))

    msgs_to_map.sort()
    seq = max_seq + 1
    print("==" * 25)
    for (date, filename, msg) in msgs_to_map:
        print("mv -n", os.path.join(dst, filename),
              os.path.join(dst, (pattern % seq)),
              "#", msg["message-id"].strip())
        seq += 1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--source", dest="source", required=True)
    parser.add_argument("-d", "--destination", dest="destination", required=True)
    args = parser.parse_args()

    message_ids = map_emails(args.source, args.destination)
    map_extras(message_ids, args.destination)

    return 0

if __name__ == "__main__":
    sys.exit(main())
