#!/usr/bin/env python3

"construct dumb index of the old CR archives"

import concurrent.futures
import csv
import getopt
import glob
import html
import os
import queue
import sqlite3
import string
import sys
import threading
# import traceback

import regex as re
from textblob import TextBlob
from textblob.classifiers import NaiveBayesClassifier
from textblob.np_extractors import ConllExtractor

from smontanaro.log import eprint
from smontanaro.srchdb import SRCHDB
from smontanaro.strip import strip_leading_quotes, CRLF

from smontanaro.util import (read_message, trim_subject_prefix,
                             parse_from, all_words)

DB = None

EXTRACTOR = ConllExtractor()

def main():
    "process CR archive emails, generating index as SQLite database"
    opts, args = getopt.getopt(sys.argv[1:], "ht:w:")
    classifier = None
    workers = os.cpu_count() - 1
    for opt, arg in opts:
        if opt == "t":
            with open(arg, "r", encoding="utf-8") as fobj:
                classifier = NaiveBayesClassifier(fobj, format="csv")
        elif opt == "-w":
            workers = int(arg)
        elif opt == "-h":
            eprint("sorry, no help yet")
            return 0

    blq = QueuePair()
    blob_thread = threading.Thread(target=work_the_blob, args=(blq,))
    blob_thread.name = "TextBlob"
    blob_thread.daemon = True
    blob_thread.start()

    dbq = QueuePair()
    db_thread = ShareSQLDB(dbq)
    db_thread.name = "SQLDB"
    db_thread.daemon = True
    db_thread.start()

    dbq.put(("set_db", None, args))
    dbq.get_none()

    files = set()
    for month in sys.stdin:
        month = month.strip()
        files.update(set(glob.glob(f"{month}/eml-files/*.eml")))
    files = list(files)
    flen = len(files)

    xfiles = {}
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers,
                                               thread_name_prefix="pfile") as executor:
        while files:
            fnames, files = files[:10], files[10:]
            xfiles[executor.submit(process_several, fnames, classifier,
                                   blq, dbq)] = len(fnames)
        for future in concurrent.futures.as_completed(xfiles):
            completed += xfiles[future]
            if completed % 1000 == 0:
                eprint(f"{completed}/{flen}")
    eprint(f"{completed}/{flen}")

    dbq.put(("exit", None, ()))
    dbq.get_none()

    return 0

def process_several(fnames, classifier, blq, dbq):
    "group processing of several files together to minimize # txns"
    dbq.put(("begin", None, ()))
    dbq.get_none()
    for fname in fnames:
        process_file(fname, classifier, blq, dbq)
    dbq.put(("commit", None, ()))
    dbq.get_none()


QUOTED = re.compile(r'''\s*"(.*)"\s*$''')
def process_file(fname, classifier, blq, dbq):
    "extract bits from one file"
    fname = fname.strip()
    msg = read_message(fname)

    payload = msg.extract_text()

    if not payload:
        return

    if classifier is not None:
        blq.put("filter+", (classifier, payload))
        payload = blq.get()

    subject = trim_subject_prefix(msg["subject"])
    mat = QUOTED.match(subject)
    if mat is not None:
        subject = mat.group(1)
    if subject:
        payload = f"{subject}{CRLF}{CRLF}{payload}"
    terms = sorted(set(get_terms(strip_leading_quotes(payload), blq)))

    for term in terms:
        if term[0:4] == "http":
            continue
        rowid = add_term(term, dbq)
        fragment = create_fragment(payload, term)
        add_fragment(fragment, fname, rowid, dbq)
    (sender, addr) = parse_from(msg["from"])

    sub_frags = set([subject])

    # add from:name, from:someone@somewhere, subject:...
    for term in (f"from:{sender.strip().lower()}",
                 f"from:{addr.strip().lower()}",
                 f"subject:{subject.strip().lower()}",):
        if term in ("from:", "subject:"):
            continue
        rowid = add_term(term, dbq)
        add_fragment("", fname, rowid, dbq)
    for phrase in get_terms(subject, blq):
        if phrase in sub_frags:
            continue
        if phrase[0:4] == "http":
            continue
        rowid = add_term(f"subject:{phrase}", dbq)
        add_fragment("", fname, rowid, dbq)

def get_terms(text, blq):
    "yield a series of words matching desired pattern"
    blq.put(("phrase_gen", (text,)))
    for phrase in blq.get():
        yield phrase

def add_fragment(fragment, fname, rowid, dbq):
    "add fragment record to file_search table"
    dbq.put(("insert", ("insert into file_search"
                        " (filename, fragment, reference) values (?, ?, ?)"),
             (fname, fragment, rowid)))
    return dbq.get()

def have_term(term, dbq):
    "return rowid if we already have term in the database, else zero"
    dbq.put(("select_one",  ("select rowid from search_terms"
                             "  where term = ?"), (term,)))
    result = dbq.get()
    return result[0] if result else 0

def add_term(term, dbq):
    """add the given term to the database if it doesn't already exist.

    Return rowid for the term.
    """
    rowid = have_term(term, dbq)
    if not rowid:
        dbq.put(("insert", "insert into search_terms values (?)", (term,)))
        rowid = dbq.get()
    return rowid

def create_fragment(payload, term):
    "get a fragment of text from the message matching the term"
    try:
        index = payload.lower().index(term.lower())
    except ValueError:
        return ""

    pfx = html.escape(re.sub(r"\s+", " ",
        payload[index-25:index]))
    fragment = html.escape(re.sub(r"\s+", " ",
        payload[index:index+len(term)]))
    sfx = html.escape(re.sub(r"\s+", " ",
        payload[index+len(term):index+len(term)+25]))
    return f"{pfx}<b>{fragment}</b>{sfx}".strip()


def read_csv(csv_file):
    "read a CSV file but return as single dict, not list of dicts"
    records = {}
    with open(csv_file, "r", encoding="utf-8") as fobj:
        rdr = csv.DictReader(fobj)
        for row in rdr:
            records[row["from"]] = row["to"]
    return records


ALL_WORDS = all_words()
EXCEPTIONS = read_csv(os.path.join(os.path.dirname(__file__),
                                   "buildindex.exc"))

def merge_exceptions(k, _dbq):
    "hand-crafted merge"
    # a CSV file contains 'from' and 'to' columns. The 'from' column can match
    # in two ways, either an exact match for `k` or as an exact match for the
    # last word in `k`.
    last = k.split()[-1]
    old = new = k
    why = "noop"
    if k in EXCEPTIONS:
        new = EXCEPTIONS[k]
    elif last in EXCEPTIONS:
        new = (" ".join(k.split()[:-1] + [EXCEPTIONS[last]])).strip()
    if new != k:
        why = "exc"
    return old, new, why


PUNCT = string.punctuation.replace("-", "")
PUNCTSET = set(re.sub("[-_]", "", string.punctuation))
PUNCTPATNODOT = re.compile("[" +
                           re.escape(string.punctuation.replace(".", "")) +
                           "]+")
URLPAT = re.compile("https?://[^ ]+")

def zap_punct(k, _dbq):
    "strip leading or trailing punctuation or whitespace and zap terms with punct & no ' '"
    old = new = k
    why = "noop"
    kstrip = re.sub(f"[ {PUNCT}-]+$", "", old)
    kstrip = re.sub(f"^[ {PUNCT}-]+", "", kstrip).strip()
    if kstrip and kstrip[0] == "'":
        kstrip = ""
    if old != kstrip:
        new = kstrip
        why = "punct"
    # If term is a single word and contains punctuation other than '-' or '_',
    # get rid of it.
    if set(new) & PUNCTSET and " " not in new:
        new = ""
    return old, new, why


def work_the_blob(que):
    "chat with text blob worker"
    que.worker_id = threading.current_thread()
    def filter_positive(classifier, text):
        "Only use sentences which score positive with the NaiveBayesClassifier"
        positive = []
        blob = TextBlob(text, np_extractor=EXTRACTOR)
        upper = 0.65
        for sent in blob.sentences:
            prob_dist = classifier.prob_classify(sent)
            if prob_dist.prob("pos") >= upper:
                positive.append(sent)
        return f"{CRLF}{CRLF}".join(positive)

    while True:
        ((rcvq, _caller), (cmd, args)) = que.get()
        match cmd:
            case "filter+":
                (classifier, payload) = args
                rcvq.put(filter_positive(classifier, payload))
            case "phrase_gen":
                (text,) = args
                # no URLs
                text = URLPAT.sub(" ", text)
                # delete all punctuation other than periods
                text = PUNCTPATNODOT.sub(" ", text)
                rcvq.put(TextBlob(text, np_extractor=EXTRACTOR).noun_phrases)
            case _:
                raise ValueError(f"Unknown command: {cmd}")

class ShareSQLDB(threading.Thread):
    "communicate with SQLite db, properly interleaving transactions."
    # txn_caller is a key attribute. It can take on two values, None (no
    # transaction is active), or the name of a thread (the thread currently
    # executing an active transaction.
    def __init__(self, que):
        super().__init__()
        self.que = que
        self.lock = threading.RLock()
        self.txn_caller = None
        self.saved_requests = {}
        self.me = None
        self.cur = None

    def run(self):
        self.me = threading.current_thread()
        self.que.worker_id = self.me
        cmdq = self.que.send_queue
        while True:
            request = cmdq.get()
            (rcvq, caller), (cmd, stmt, args) = request
            with self.lock:
                if self.txn_caller is None:
                    if self.run_one((rcvq, caller), (cmd, stmt, args)):
                        return
                    continue
                if self.txn_caller != caller:
                    # Some other thread is in the midst of a transaction. We
                    # must wait.
                    self.saved_requests.setdefault(caller, []).append(request)
                    continue
                # self.txn_caller == caller, so caller is in the midst of a
                # transaction.  Execute immediately.
                try:
                    if self.run_one((rcvq, caller), (cmd, stmt, args)):
                        return
                except sqlite3.ProgrammingError as exc:
                    eprint(stmt, args, exc)

    def replay_saved(self):
        "replay one caller's saved requests"
        assert self.txn_caller is None
        caller = list(self.saved_requests).pop()
        requests = self.saved_requests.pop(caller)
        for ((rcvq, caller), (cmd, stmt, args)) in requests:
            self.run_one((rcvq, caller), (cmd, stmt, args))

    def run_one(self, receiver_info, cmd_info):
        "Run a single request."
        # Any pending requests are replayed after a commit or when the main
        # thread requests exit.
        (rcvq, caller) = receiver_info
        (cmd, stmt, args) = cmd_info
        # Worker never put()s to the QueuePair instance!
        match cmd:
            case "begin":
                assert self.txn_caller is None, (self.txn_caller, caller)
                self.txn_caller = caller
                self.cur.execute("begin")
                rcvq.put(None)
            case "commit":
                self.txn_caller = None
                SRCHDB.commit()
                rcvq.put(None)
                while self.saved_requests and self.txn_caller is None:
                    self.replay_saved()
            case "insert" | "update":
                self.cur.execute(stmt, args)
                rcvq.put(self.cur.lastrowid)
            case "select_all":
                rcvq.put(self.cur.execute(stmt, args).fetchall())
            case "select_one":
                rcvq.put(self.cur.execute(stmt, args).fetchone())
            case "insert_many" | "update_many":
                self.cur.executemany(stmt, args)
                rcvq.put(None)
            case "set_db":
                SRCHDB.set_database(args[0])
                self.cur = SRCHDB.cursor()
                rcvq.put(None)
            case "exit":
                # self.replay_saved()
                self.postprocess()
                rcvq.put(None)
                return True
        return False

    def have_term(self, term, cur):
        "return rowid if we already have term in the database, else zero"
        result = cur.execute("select rowid from search_terms"
                             "  where term = ?", (term,)).fetchone()
        return result[0] if result else 0

    def postprocess(self):
        "final messing around"

        to_delete = set()

        refs = []

        terms = self.cur.execute(
            "select st.term, count(fs.fragment)"
            "  from search_terms st, file_search fs"
            "  where fs.reference = st.rowid"
            "  group by fs.reference"
            "  order by st.term").fetchall()
        self.cur.execute("begin")
        for (term, count) in terms:
            term = term.strip()
            old = new = term
            for merge in (self.merge_plurals, self.merge_ing,
                          self.merge_wrong, self.strip_nonprint):
                if not old:
                    break
                old, new = merge(old)
                if not new:
                    to_delete.add(old)
                    break
                if new != old:
                    new_rowid = self.have_term(term, self.cur)
                    if not new_rowid:
                        self.cur.execute("insert into search_terms values (?)",
                                         (term,))
                        new_rowid = self.cur.lastrowid
                    old_rowid = self.have_term(old, self.cur)
                    refs.append((new_rowid, old_rowid))
                    to_delete.add(old)
                    old = new.strip()

        self.cur.executemany("update file_search"
                             "  set reference = ?"
                             "  where reference = ?", refs)
        for (term, count) in self.cur.execute(
            "select st.term, count(fs.fragment)"
            " from search_terms st, file_search fs"
            "  where fs.reference = st.rowid"
            # always keep synthetic terms...
            '    and st.term not like "from:%"'
            '    and st.term not like "subject:%"'
            "  group by fs.reference"
            "  order by st.term"):
            if (len(term) < 4 or
                count < 1 or
                " " not in term and len(term) > 20):
                to_delete.add(term)
        SRCHDB.commit()

        # zap terms...
        #   containing characters outside the printable ascii range
        nonprint = set(chr(i) for i in range(128, 256))
        nonprint |= set(chr(i) for i in range(0, ord(' ')))
        #   or anything beginning with punctuation
        punct = set(string.punctuation)
        #   or ending with punctuation other than periods
        punct_nodot = punct - set(".")
        #   or anything that looks like a (US) phone number
        phonepat = re.compile(r"[0-9]{3,3}[-.][0-9]{3,3}[-.][0-9]{4,4}")

        wordspat = re.compile(r"([a-z]+) .$")
        move_these = set()

        self.cur.execute("select term from search_terms"
                         "  where term not like 'from:%'"
                         "    and term not like 'subject:%'")
        for (term,) in self.cur:
            if (set(term) & nonprint or
                term[0] in punct or
                term[-1] in punct_nodot or
                phonepat.search(term) is not None or
                "message id" in term or
                re.search("message [0-9]", term) is not None or
                len(term) > 50 and term.count(" ") > 7 or
                len(term) > 70 or
                "classicrendezvous" in term or
                "bikelist.org" in term):
                to_delete.add(term)
            elif term.endswith("original message"):
                move_these.add((term, term.replace("original message", "").strip()))
            elif term[-1] == ".":
                # trim trailing periods
                move_these.add((term, term[:-1]))
            elif (mat := wordspat.match(term)) is not None:
                # toss last "word" if it's a single character
                move_these.add((term, mat.group(1)))

        # belt and suspenders
        to_delete.add("")

        self.cur.execute("begin")
        self.move_terms(move_these)
        self.delete_exceptions(to_delete)
        self.delete_unreferenced_terms()
        SRCHDB.commit()

    def move_terms(self, from_to):
        "move terms from undesirable value to more desirable real estate."
        eprint(f"moving {len(from_to)} terms")
        # We don't really move them, just change the
        # reference. delete_referenced_items will then take care of eliminating the
        # now orphaned terms.
        for (old, new) in from_to:
            self.cur.execute("select rowid from search_terms"
                             "  where term = ?", (old,))
            old_rowid = self.cur.fetchone()[0]
            new_rowid = self.have_term(new, self.cur)
            if not new_rowid:
                self.cur.execute("insert into search_terms values (?)",
                                 (new,))
                new_rowid = self.cur.lastrowid
            self.cur.execute("update file_search set reference = ?"
                             "  where reference = ?",
                             (new_rowid, old_rowid))

    def delete_unreferenced_terms(self):
        "delete terms which have no rowid refs in file_search table"
        to_delete = set()

        self.cur.execute("select distinct rowid from file_search")
        rowids = [x for (x,) in self.cur.fetchall()]

        # could do this with execute_many...
        for rowid in rowids:
            count = self.cur.execute("select count(*) from file_search"
                "  where reference = ?", (rowid,)).fetchone()[0]
            if count == 0:
                to_delete.add((rowid,))

        eprint(f"deleting {len(to_delete)} unreferenced terms")
        if to_delete:
            self.cur.executemany("delete from search_terms where rowid = ?",
                                 list(to_delete))

    def delete_exceptions(self, to_delete):
        "delete terms we determined aren't worth it."
        # TBD...
        eprint(f"deleting {len(to_delete)} sketchy terms")
        to_delete = list(to_delete)
        chunksize = 200
        while to_delete:
            terms = tuple(to_delete[:chunksize])
            to_delete = to_delete[chunksize:]
            qmarks = ", ".join(["?"] * len(terms))
            self.cur.execute("select distinct rowid from search_terms"   # nosec
                             f"  where term in ({qmarks})", terms)
            rowids = self.cur.fetchall()
            if not rowids:
                continue
            self.cur.executemany("delete from file_search"
                                 "  where reference = ?",
                                 rowids)
            self.cur.executemany("delete from search_terms"
                                 "  where rowid = ?",
                                 rowids)

    def merge_plurals(self, k):
        "map simple plurals to singular"
        # we only want to consider words/phrases if the last word is in the
        # large dictionary - for example, we shouldn't mess with
        # "harry hetchins" because "hetchin" isn't in the large dictionary.
        if not k.strip().split():
            return (k, k)

        last = k.split()[-1]

        old = new = k
        for end in ("s", "es"):
            sfx_len = len(end)
            # require truncated last word to be in large dictionary and
            # last sfx_len characters of the last word to be the plural
            if (last[:-sfx_len] in ALL_WORDS and
                last[-sfx_len:] == end):
                new = k[:-sfx_len]
                break
        return (old, new)


    def strip_nonprint(self, k):
        "strip non-printable characters"
        old = new = k
        new = re.sub(r"[^ -~]+", "", old)
        return old, new


    def merge_ing(self, k):
        "map 'ing' endings to base word"
        if not k.strip().split():
            return (k, k)

        last = k.split()[-1]

        old = new = k
        if last[-3:] == "ing":
            # we would merge "bicycling" into "bicycle" in preference
            # to "bicycl"
            for suffix in ("e", ""):
                if (last[:-3].strip() + suffix in ALL_WORDS and
                    self.have_term(old[:-3].strip() + suffix, self.cur)):
                    new = old[:-3].strip() + suffix
                    break
        return (old, new)


    def merge_wrong(self, k):
        "merge simple truncations"
        if not k.strip().split():
            return (k, k)

        last = k.split()[-1]

        old = new = k
        if last not in ALL_WORDS:
            for suffix in ("e", "es", "s"):
                if (last + suffix in ALL_WORDS and
                    self.have_term(k+suffix, self.cur)):
                    new = k + suffix
                    break
        return old, new



class QueuePair:
    """Bind a single send queue to per-thread receive queues

    clients put items on the send queue and retrieve from the per-client
    receive queue (created on the first call to put()).

    """

    def __init__(self):
        self.send_queue = queue.Queue()
        self.recv_queues = {}
        self.worker_id = None

    def put(self, item, block=True, timeout=None):
        "send item to worker"
        me = threading.current_thread()
        # traceback.print_stack()
        if me == self.worker_id:
            raise ValueError("Worker must not put to QueuePair.")
        if me not in self.recv_queues:
            self.recv_queues[me] = queue.Queue()
        rcvq = self.recv_queues[me]
        self.send_queue.put(((rcvq, me), item), block, timeout)

    def get(self, block=True, timeout=None):
        "retrieve item from worker"
        me = threading.current_thread()
        if me == self.worker_id:
            return self.send_queue.get(block, timeout)
        return self.recv_queues[me].get(block, timeout)

    def get_none(self, block=True, timeout=None):
        "obligatory retrieve when we don't want the result"
        _dummy = self.get(block, timeout)

if __name__ == "__main__":
    sys.exit(main())
