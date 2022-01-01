#!/usr/bin/env python

"""
Process References: headers in email files from emaildir, adding to sqldb
(which might first need to be created).
"""

import argparse
import email.errors
import glob
import os
import sqlite3
import sys

def ensure_db(sqldb):
    "make sure the database and its schema exist"
    create = not os.path.exists(sqldb)
    conn = sqlite3.connect(sqldb)
    if create:
        cur = conn.cursor()
        cur.execute('''
            create table messageids
              (
                messageid,
                filename,
                year,
                month,
                seq
              )
        ''')
        cur.execute('''
            create table msgrefs
              (
                messageid,
                reference
              )
        ''')
        conn.commit()
    return conn

def decompose_filename(filename):
    "Extract year, month and sequence number from filename."

    # Filename looks like this:
    #    CR/2004-01/eml-files/classicrendezvous.10401.0368.eml
    # Trust the year and month in the subdirectory, then take the last
    # number (0368, in this case) minus one as the sequence number.

    try:
        seq = int(os.path.split(filename)[1].split(".")[-2], 10) - 1
    except IndexError:
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
    if not msgid:
        return nrecs

    cur = conn.cursor()
    (year, month, seq) = decompose_filename(filename)
    cur.execute("delete from msgrefs"
                "  where messageid = ?",
                (msgid,))
    cur.execute("delete from messageids"
                "  where messageid = ?",
                (msgid,))
    cur.execute("insert into messageids"
                "  values (?, ?, ?, ?, ?)",
                (msgid, filename, year, month, seq))
    nrecs += 1
    if verbose > 2:
        print("  >>", msgid)

    if message["References"] is not None:
        for reference in message["References"].split():
            cur.execute("insert into msgrefs"
                        "  values (?, ?)",
                        (msgid, reference))
            nrecs += 1
            if verbose > 3:
                print("    :", reference)
    if message["In-Reply-To"] is not None:
        for reference in message["In-Reply-To"].split():
            cur.execute("insert into msgrefs"
                        "  values (?, ?)",
                        (msgid, reference))
            nrecs += 1
            if verbose > 3:
                print("    :", reference)
    cur.close()
    conn.commit()
    return nrecs

def main():
    "see __doc__"
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--create", dest="createdb", action="store_true",
                        default=False)
    parser.add_argument("-v", "--verbose", dest="verbose", action="count",
                        default=0)
    parser.add_argument("top", help="directory containing email files to process")
    parser.add_argument("sqldb")
    args = parser.parse_args()
    if args.createdb and os.path.exists(args.sqldb):
        os.remove(args.sqldb)

    conn = ensure_db(args.sqldb)

    last_dir = ""
    for email_dir in sorted(glob.glob(f"{args.top}/**/eml-files")):
        records = nfiles = 0
        dirpath = os.path.dirname(email_dir)
        if args.verbose and last_dir != dirpath:
            print(">>", dirpath)
            last_dir = dirpath
        for filename in sorted(glob.glob(f"{email_dir}/*.eml")):
            for encoding in ("utf-8", "latin-1"):
                with open(filename, encoding=encoding) as fobj:
                    try:
                        message = email.message_from_file(fobj)
                    except (UnicodeDecodeError, email.errors.MessageError):
                        continue
                    else:
                        break
            else:
                print(f"failed to read message from {filename}", file=sys.stderr)
                continue
            if message.defects:
                print(f"message parse errors {message.defects} in {filename}",
                      file=sys.stderr)
                continue
            nfiles += 1
            nrecs = insert_references(message, conn, filename, args.verbose)
            if args.verbose > 1:
                print("  >>", filename, nrecs)
            records += nrecs
        if args.verbose:
            print("<<", dirpath, records, nfiles)
    cur = conn.cursor()
    cur.execute("select count(*) from messageids")
    print(f"{cur.fetchone()[0]} total message ids")
    cur.execute("select count(*) from msgrefs")
    print(f"{cur.fetchone()[0]} total references")

if __name__ == "__main__":
    sys.exit(main())
