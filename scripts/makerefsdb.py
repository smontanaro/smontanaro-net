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
                filename
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

def insert_references(message, conn, filename, verbose):
    nrecs = 0
    msgid = message["Message-ID"]
    if not msgid:
        return nrecs
    conn.execute("delete from msgrefs"
                 "  where messageid = ?",
                 (msgid,))
    conn.execute("delete from messageids"
                 "  where messageid = ?",
                 (msgid,))
    conn.commit()
    conn.execute("insert into messageids"
                 "  values (?, ?)",
                 (msgid, filename))
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
    print("Total records inserted:", records)

if __name__ == "__main__":
    sys.exit(main())
