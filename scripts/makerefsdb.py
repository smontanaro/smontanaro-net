#!/usr/bin/env python

"""
Process References: headers in email files from emaildir, adding to sqldb
(which might first need to be created).
"""

import argparse
import datetime
import email.errors
import os
import re
import sqlite3
import sys

import arrow
import dateutil.parser
import dateutil.tz

def convert_ts_bytes(stamp):
    "SQLite3 converter for tz-aware datetime objects"
    stamp = stamp.decode("utf-8")
    return datetime.datetime.fromisoformat(stamp)

def ensure_db(sqldb):
    "make sure the database and its schema exist"
    create = not os.path.exists(sqldb)
    sqlite3.register_converter("TIMESTAMP", convert_ts_bytes)
    conn = sqlite3.connect(sqldb, detect_types=(sqlite3.PARSE_DECLTYPES
                                                | sqlite3.PARSE_COLNAMES))
    if create:
        cur = conn.cursor()
        cur.execute('''
            create table messages
              (
                messageid TEXT PRIMARY KEY,
                filename TEXT,
                sender TEXT,
                subject TEXT,
                year INTEGER,
                month INTEGER,
                seq INTEGER,
                is_root INTEGER,
                ts timestamp
              )
        ''')
        cur.execute('''
            create table msgrefs
              (
                messageid TEXT,
                reference TEXT,
                FOREIGN KEY(reference) REFERENCES messages(messageid)
              )
        ''')
        cur.execute('''
            create table msgreplies
              (
                messageid TEXT,
                parent TEXT,
                FOREIGN KEY(parent) REFERENCES messages(messageid)
              )
        ''')
        cur.execute("create index msgid_index"
                    "  on messages"
                    "  (messageid)")
        cur.execute("create index msgrefs_index"
                    "  on msgrefs"
                    "  (reference)")
        cur.execute("create index msgreplies_index"
                    "  on msgreplies"
                    "  (parent)")
        conn.commit()
    return conn

TZMAP = {
    # dumb heuristics - keep these first
    "+0000 GMT": "UTC",
    " 0 (GMT)": " UTC",
    " -800": " -0800",
    # more typical mappings (leading space to avoid stuff like "(EST)")
    " EST": " America/New_York",
    " EDT": " America/New_York",
    " CST": " America/Chicago",
    " CDT": " America/Chicago",
    " MST": " America/Denver",
    " MDT": " America/Denver",
    " PST": " America/Los_Angeles",
    " PDT": " America/Los_Angeles",
    " Pacific Daylight Time": " America/Los_Angeles",
}

TZINFOS = {
    "EST": dateutil.tz.gettz("America/New_York"),
    "EDT": dateutil.tz.gettz("America/New_York"),
    "CST": dateutil.tz.gettz("America/Chicago"),
    "CDT": dateutil.tz.gettz("America/Chicago"),
    "MST": dateutil.tz.gettz("America/Denver"),
    "MDT": dateutil.tz.gettz("America/Denver"),
    "PST": dateutil.tz.gettz("America/Los_Angeles"),
    "PDT": dateutil.tz.gettz("America/Los_Angeles"),
    "SGT": dateutil.tz.gettz("Asia/Singapore"),
    "UT": dateutil.tz.UTC,
}

ARROW_FORMATS = [
    "YYYY/MM/DD ddd A hh:mm:ss ZZZ",
    "ddd, DD MMM YYYY HH:mm:ss ZZZ",
    "ddd, D MMM YYYY HH:mm:ss ZZZ",
    "YYYY/MM/DD ddd A hh:mm:ss ZZ",
    "ddd, DD MMM YYYY HH:mm:ss ZZ",
    "ddd, D MMM YYYY HH:mm:ss ZZ",
    "YYYY/MM/DD ddd A hh:mm:ss Z",
    "ddd, DD MMM YYYY HH:mm:ss Z",
    "ddd, D MMM YYYY HH:mm:ss Z",
    "DD MMM YYYY HH:mm:ss ZZZ",
    "D MMM YYYY HH:mm:ss ZZZ",
]

ONE_SEC = datetime.timedelta(seconds=1)

def parse_date(timestring):
    "A few tries to parse message dates"
    timestring = timestring.strip()
    if timestring.lower().startswith("date:"):
        # print(f"strip leading 'date:' from {timestring}")
        timestring = timestring.split(maxsplit=1)[1].strip()
    timestring = timestring.strip()
    # map obsolete names since arrow appears not to do that.
    timestring = timestring.strip()
    for obsolete, name in TZMAP.items():
        tzs = timestring.replace(obsolete, name)
        if tzs != timestring:
            #print(f"{timestring} -> {tzs}")
            timestring = tzs
            break
    if timestring.endswith(")"):
        timestring = re.sub(r"\s*\([^)]*\)$", "", timestring)
    try:
        timestamp = dateutil.parser.parse(timestring, tzinfos=TZINFOS)
    except dateutil.parser.ParserError:
        # try arrow with its format capability
        try:
            timestamp = arrow.get(timestring, ARROW_FORMATS).datetime
        except arrow.parser.ParserError as exc:
            raise dateutil.parser.ParserError(str(exc))
    return timestamp

def decompose_filename(filename):
    "Extract year, month and sequence number from filename."

    # Filename looks like this:
    #    CR/2004-01/eml-files/classicrendezvous.10401.0368.eml
    # Trust the year and month in the subdirectory, then take the last
    # number (0368, in this case) minus one as the sequence number.

    try:
        seq = int(os.path.split(filename)[1].split(".")[-2], 10)
    except (ValueError, IndexError):
        print(f"Error decomposing {filename}", file=sys.stderr)
        raise
    (year, month) = [int(x)
                     for x in
                     os.path.split(filename)[0].split("/")[1].split("-")]
    return (year, month, seq)

def insert_references(message, conn, filename, verbose):
    "extract reference bits from message and insert in db"
    nrecs = 0
    msgid = message["Message-ID"]
    datestr = message["Date"]
    sender = message["From"]
    subject = message["Subject"]
    if not msgid:
        return nrecs

    if verbose > 1:
        print("  >>", msgid)

    cur = conn.cursor()
    try:
        (year, month, seq) = decompose_filename(filename)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 0
    try:
        stamp = parse_date(datestr)
    except dateutil.parser.ParserError as exc:
        cur.execute("select max(timestamp) from messages"
                    "  where year <= ? and month <= ?",
                    (year, month))
        stamp = dateutil.parser.parse(cur.fetchone()[0]) + ONE_SEC
        print(f"date parsing error for {datestr} ({exc}) - fall back to {stamp}",
              file=sys.stderr)

    if stamp.tzinfo is None:
        # force UTC
        stamp = stamp.replace(tzinfo=dateutil.tz.UTC)

    cur.execute("delete from msgrefs"
                "  where messageid = ?",
                (msgid,))
    cur.execute("delete from msgreplies"
                "  where messageid = ?",
                (msgid,))
    cur.execute("delete from messages"
                "  where messageid = ?",
                (msgid,))
    cur.execute("insert into messages"
                "  values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (msgid, filename, sender, subject, year, month, seq,
                 0, stamp))
    nrecs += 1
    if verbose > 2:
        print("  >>", msgid)

    ref_list = []
    if message["References"] is not None:
        ref_list = [ref.strip() for ref in
                        re.findall(r"<[^\s>]+>", message["References"])]
    if message["In-Reply-To"] is not None:
        in_reply_to = message["In-Reply-To"].strip()
        if in_reply_to not in ref_list:
            ref_list.append(in_reply_to)

    for (parent, child) in zip(ref_list[:-1], ref_list[1:]):
        cur.execute("insert into msgreplies"
                    " values (?, ?)",
                    (child, parent))

    for reference in ref_list:
        cur.execute("insert into msgrefs"
                    "  values (?, ?)",
                    (msgid, reference))
        nrecs += 1
        if verbose > 3:
            print("    :", reference)

    cur.close()
    conn.commit()
    return nrecs

def process_one_file(filename, conn, verbose):
    "handle a single file"
    for encoding in ("utf-8", "latin-1"):
        with open(filename, encoding=encoding) as fobj:
            try:
                message = email.message_from_file(fobj)
            except (UnicodeDecodeError, email.errors.MessageError):
                continue
            else:
                break
    else:
        raise ValueError(f"failed to read message from {filename}")
    if message.defects:
        raise ValueError(f"message parse errors {message.defects} in {filename}")
    return insert_references(message, conn, filename, verbose)

def mark_thread_roots(conn):
    "identify those messages which start threads."
    cur = conn.cursor()

    # messages which are parents but don't have parents are roots
    cur.execute("update messages"
                "  set is_root = 1"
                "  where messageid in"
                "   (select r.parent"
                "      from msgreplies r"
                "      where r.parent not in"
                "        (select messageid from msgreplies))")
    conn.commit()
    return cur.execute("select count(*)"
                       "  from messages"
                       "  where is_root = 1").fetchone()[0]

def main():
    "see __doc__"
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--create", dest="createdb", action="store_true",
                        default=False)
    parser.add_argument("-v", "--verbose", dest="verbose", action="count",
                        default=0)
    parser.add_argument("-o", "--one", dest="one", help="Process a single email file",
                        default=None)
    parser.add_argument("-d", "--database", dest="sqldb",
                        help="SQLite3 database file", required=True)
    parser.add_argument("top", help="directory containing email files to process",
                        default=None, nargs="?")
    args = parser.parse_args()
    if args.one and args.top:
        print("Only one of top level directory and single filename may be given",
              file=sys.stderr)
        return 1

    if args.createdb and os.path.exists(args.sqldb):
        os.remove(args.sqldb)

    conn = ensure_db(args.sqldb)

    if args.one:
        try:
            nrecs = process_one_file(args.one, conn, args.verbose)
        except ValueError:
            print(f"failed to process message {args.one}", file=sys.stderr)
            return 1
        return 0

    records = nfiles = 0
    for (dirpath, _dirnames, filenames) in os.walk(args.top):
        for fname in filenames:
            if not fname.endswith(".eml"):
                continue
            path = os.path.join(dirpath, fname)
            try:
                nrecs = process_one_file(path, conn, args.verbose)
            except ValueError:
                print(f"failed to process file {path}", file=sys.stderr)
                continue
            nfiles += 1
            if args.verbose > 1:
                print("  >>", fname, nrecs)
            records += nrecs
        if args.verbose:
            print(">>", dirpath, records, nfiles)

    nroots = mark_thread_roots(conn)
    print(nroots, "thread roots identified")
    cur = conn.cursor()
    cur.execute("select count(*) from messages")
    print(f"{cur.fetchone()[0]} total message ids")
    cur.execute("select count(*) from msgrefs")
    print(f"{cur.fetchone()[0]} total references")
    return 0

if __name__ == "__main__":
    sys.exit(main())
