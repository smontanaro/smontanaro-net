#!/usr/bin/env python

"""
Process References: headers in email files from emaildir, adding to sqldb
(which might first need to be created).
"""

import argparse
import email.errors
import os
import sqlite3
import sys

def ensure_db(sqldb):
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

    seq = int(os.path.split(filename)[1].split(".")[-2], 10) - 1
    (year, month) = [int(x)
                       for x in
                         os.path.split(filename)[0].split("/")[1].split("-")]
    return (year, month, seq)

def insert_references(message, conn, filename, verbose):
    nrecs = 0
    msgid = message["Message-ID"]
    if not msgid:
        return nrecs

    (year, month, seq) = decompose_filename(filename)
    conn.execute("delete from msgrefs"
                 "  where messageid = ?",
                 (msgid,))
    conn.execute("delete from messageids"
                 "  where messageid = ?",
                 (msgid,))
    conn.commit()
    (year, month, seq) = decompose_filename(filename)
    conn.execute("insert into messageids"
                 "  values (?, ?, ?, ?, ?)",
                 (msgid, filename, year, month, seq))
    nrecs += 1
    if verbose:
        print("  >>", msgid)

    if message["References"] is not None:
        for reference in message["References"].split():
            conn.execute("insert into msgrefs"
                         "  values (?, ?)",
                         (msgid, reference))
            nrecs += 1
            if verbose:
                print("    :", reference)
    if message["In-Reply-To"] is not None:
        for reference in message["In-Reply-To"].split():
            conn.execute("insert into msgrefs"
                         "  values (?, ?)",
                         (msgid, reference))
            nrecs += 1
            if verbose:
                print("    :", reference)
    conn.commit()
    return nrecs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--create", dest="createdb", action="store_true",
                        default=False)
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                        default=False)
    parser.add_argument("emaildir")
    parser.add_argument("sqldb")
    args = parser.parse_args()
    if args.createdb and os.path.exists(args.sqldb):
        os.remove(args.sqldb)

    conn = ensure_db(args.sqldb)

    records = 0
    for filename in os.listdir(args.emaildir):
        filename = os.path.join(args.emaildir, filename)
        with open(filename, encoding="utf-8") as fp:
            try:
                message = email.message_from_file(fp)
            except email.errors.MessageError:
                print(f"failed to read message from {filename}", file=sys.stderr)
                continue
            except UnicodeDecodeError:
                print(f"failed to process {filename} as UTF-8, trying Latin-1",
                      file=sys.stderr)
                # Fall back to latin-1
                fp = open(filename, encoding="latin-1")
                try:
                    message = email.message_from_file(fp)
                except email.errors.MessageError:
                    print(f"failed to read message from {filename}",
                          file=sys.stderr)
                    continue
                except UnicodeDecodeError:
                    print(f"Unicode error while reading {filename}",
                          file=sys.stderr)
                    continue
            if message.defects:
                print(f"message parse errors {message.defects} in {filename}",
                      file=sys.stderr)
                continue
            nrecs = insert_references(message, conn, filename, args.verbose)
            if args.verbose:
                print(">>", filename, nrecs)
            records += nrecs
    print("records inserted:", records)
    cur = conn.cursor()
    cur.execute("select count(*) from messageids")
    print(f"{cur.fetchone()[0]} total message ids")
    cur.execute("select count(*) from msgrefs")
    print(f"{cur.fetchone()[0]} total references")

if __name__ == "__main__":
    sys.exit(main())
