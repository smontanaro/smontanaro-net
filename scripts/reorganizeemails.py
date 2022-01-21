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
    source_files = scan_dir(src, "source", message_ids)
    dest_files = scan_dir(dst, "destination", message_ids)

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
    print("Found", dest_files, "destination messages")
    print("Found", len(message_ids), "distinct message ids")
    print(no_dst_mapping, "can't be mapped to existing source names")
    print(no_src_mapping, "can't be mapped to existing destination names")

    return message_ids

def scan_dir(dirname, which, message_ids):
    "scan dirname looking for message-ids and such to id duplicates."
    nfiles = 0
    assert which in ("source", "destination")
    for (dirpath, _dirnames, filenames) in os.walk(dirname):
        for filename in filenames:
            fname = os.path.join(dirpath, filename)
            with open(fname, "rb") as fobj:
                msg = email.message_from_bytes(fobj.read())
                if msg.defects:
                    print(f"defective message file {fname}: "
                          f"{msg.defects}. Skipping",
                          file=sys.stderr)
                    continue
            nfiles += 1
            message_id = msg["message-id"]
            if message_id not in message_ids:
                message_ids[message_id] = {
                    "source": {},
                    "destination": {},

                }
            dct = message_ids[message_id]
            if dct[which]:
                print(f"Already have a key for {message_id} ({dct}). "
                      "Skipping",
                      file=sys.stderr)
                continue
            dct[which]["filename"] = filename
            dct[which]["message"] = msg
    return nfiles

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
