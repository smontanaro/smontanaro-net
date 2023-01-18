#!/usr/bin/env python

"""
Process References: headers in email files from emaildir, adding to sqldb
(which might first need to be created).
"""

import argparse
import datetime
import os
import re
import sqlite3
import sys
import tempfile

import arrow.parser
import dateutil.parser
import dateutil.tz

from smontanaro.dates import parse_date
from smontanaro.log import eprint
from smontanaro.refdb import ensure_db, ensure_indexes
from smontanaro.util import clean_msgid, read_message

ONE_SEC = datetime.timedelta(seconds=1)

def decompose_filename(filename):
    "Extract year, month and sequence number from filename."

    # Filename looks like this:
    #    CR/2004-01/eml-files/classicrendezvous.10401.0368.eml
    # Trust the year and month in the subdirectory, then take the last
    # number (0368, in this case) minus one as the sequence number.

    try:
        seq = int(os.path.split(filename)[1].split(".")[-2], 10)
    except (ValueError, IndexError):
        eprint(f"Error decomposing {filename}")
        raise
    (year, month) = [int(x)
                     for x in
                     os.path.split(filename)[0].split("/")[1].split("-")]
    return (year, month, seq)

def insert_references(message, conn, filename):
    "extract reference bits from message and insert in db"
    nrecs = 0
    msgid = clean_msgid(message["Message-ID"])
    # Sometimes these aren't actually strings, but email.header.Header
    # objects (which SQLite can't handle), so stringify them.
    datestr = str(message["Date"])
    sender = str(message["From"])
    subject = str(message["Subject"])
    if not msgid:
        return nrecs

    try:
        (year, month, seq) = decompose_filename(filename)
    except ValueError as exc:
        eprint(exc)
        return 0
    try:
        stamp = parse_date(datestr)
    except arrow.parser.ParserError as exc:
        conn.execute("select max(timestamp) from messages"
                     "  where year <= ? and month <= ?",
                     (year, month))
        stamp = dateutil.parser.parse(conn.fetchone()[0]) + ONE_SEC
        eprint(f"date parsing error for {datestr} ({exc}) - fall back to {stamp}")

    if stamp.tzinfo is None:
        # force UTC
        stamp = stamp.replace(tzinfo=dateutil.tz.UTC)

    try:
        conn.execute("insert into messages"
                     "  values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (msgid, filename, sender, subject, year, month, seq,
                      0, stamp))
    except sqlite3.IntegrityError:
        eprint(f"dup: {msgid} {filename}")
        return nrecs
    nrecs += 1

    ref_list = []
    if message["References"] is not None:
        ref_list = [clean_msgid(ref) for ref in
                        re.findall(r"<[^>]+>", message["References"])]
    if message["In-Reply-To"] is not None:
        # I've discovered some bizarro In-Reply-To fields, so treat it
        # similar to the References field. Example:
        #    CR/2006-01/eml-files/classicrendezvous.10601.1817.eml
        # where we find:
        #     In-Reply-To: <s3d77aca.005@GW16.hofstra.edu> (Edward Albert's message of "Wed,
        #          25 Jan 2006 13:18:40 -0500")
        reply_list = [clean_msgid(ref) for ref in
                          re.findall(r"<[^>]+>", message["In-Reply-To"])]
        for in_reply_to in reply_list:
            if in_reply_to not in ref_list:
                ref_list.append(in_reply_to)

    with conn:
        for (parent, child) in zip(ref_list[:-1], ref_list[1:]):
            conn.execute("insert into msgreplies"
                         " values (?, ?)",
                         (child, parent))

        for reference in ref_list:
            conn.execute("insert into msgrefs"
                         "  values (?, ?)",
                         (msgid, reference))
            nrecs += 1

    return nrecs

def process_one_file(filename, conn):
    "handle a single file"
    message = read_message(filename)
    if message.defects:
        raise ValueError(f"message parse errors {message.defects} in {filename}")
    return insert_references(message, conn, filename)

def mark_thread_roots(conn):
    "identify those messages which start threads."
    # messages which are parents but don't themselves have parents are roots
    conn.execute("update messages"
                 "  set is_root = 1"
                 "  where messageid in"
                 "   (select r.parent"
                 "      from msgreplies r"
                 "      where r.parent not in"
                 "        (select messageid from msgreplies))")

def parse_args():
    "command line argument eating"
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--create", dest="createdb", action="store_true",
                        default=False)
    parser.add_argument("-o", "--one", dest="one", help="Process a single email file",
                        default=None)
    parser.add_argument("-d", "--database", dest="sqldb",
                        help="SQLite3 database file", required=True)
    parser.add_argument("top", help="directory containing email files to process",
                        default=None, nargs="?")
    return parser.parse_args()


def process_files(top, conn):
    "find and process files, starting at top"
    records = nfiles = 0
    for (dirpath, dirs, filenames) in os.walk(top):
        dirs.sort()
        files_read = 0
        if "eml-files" not in dirpath:
            continue
        print(f"{dirpath}", end=' ')
        start = datetime.datetime.now()
        for fname in filenames:
            if not fname.endswith(".eml"):
                continue
            files_read += 1
            if files_read % 100 == 0:
                print(".", end="")
                sys.stdout.flush()
            path = os.path.join(dirpath, fname)
            try:
                nrecs = process_one_file(path, conn)
            except ValueError:
                eprint(f"failed to process file {path}")
                continue
            nfiles += 1
            records += nrecs
        dt = datetime.datetime.now() - start
        if files_read:
            print(f" {files_read} {(files_read / dt.total_seconds()):.02f}/s")

def main():
    "see __doc__"
    args = parse_args()

    if args.one and args.top:
        eprint("Only a top level directory or a single filename may be given")
        return 1

    if args.createdb and os.path.exists(args.sqldb):
        os.remove(args.sqldb)

    # create db in memory, dump and write to db file at the very end
    conn = ensure_db(":memory:")

    if args.one:
        try:
            process_one_file(args.one, conn)
        except ValueError:
            eprint(f"failed to process message {args.one}")
            return 1
        return 0

    process_files(args.top, conn)

    mark_thread_roots(conn)
    ensure_indexes(conn)
    (tmpfd, tmpf) = tempfile.mkstemp()
    with open(tmpf, "w", encoding="utf-8") as fobj:
        for line in conn.iterdump():
            fobj.write(f"{line}\n")
    conn.commit()
    if os.path.exists(args.sqldb):
        os.unlink(args.sqldb)
    os.system(f"sqlite3 {args.sqldb} < {tmpf}") # nosec
    os.close(tmpfd)
    os.unlink(tmpf)

    return 0

if __name__ == "__main__":
    sys.exit(main())
