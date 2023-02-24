#!/usr/bin/env python3

"construct dumb index of the old CR archives"

import concurrent.futures
import csv
import datetime as dt
import getopt
import glob
import html
import os
import string
import sys
from threading import Lock

import regex as re
from textblob import TextBlob
from textblob.classifiers import NaiveBayesClassifier

from smontanaro.log import eprint
from smontanaro.srchdb import SearchDB, SRCHDB
from smontanaro.strip import strip_footers, strip_leading_quotes, CRLF

from smontanaro.util import (read_message, trim_subject_prefix,
                             parse_from, read_words, all_words)

# Something in textblob and/or nltk doesn't play nice with no-gil, so just
# serialize all blobby accesses.
BLOB_LOCK = Lock()

DB = None

def main():
    opts, args = getopt.getopt(sys.argv[1:], "ht:")
    classifier = None
    for opt, arg in opts:
        if opt == "t":
            with open(arg, "r", encoding="utf-8") as fp:
                classifier = NaiveBayesClassifier(fp, format="csv")
        if opt == "-h":
            eprint("sorry, no help yet")
            return 0

    SRCHDB.set_database(args[0])
    with concurrent.futures.ThreadPoolExecutor() as executor:
        months = {}
        for month in sys.stdin:
            month = month.strip()
            months[executor.submit(process_month, month, classifier)] = month
        for future in concurrent.futures.as_completed(months):
            merge_into_srchdb(future.result(), months[future])

    SRCHDB.cursor().execute("begin")
    postprocess_db()
    SRCHDB.commit()

    return 0


def merge_into_srchdb(db_data, month):
    "smash all the :memory: databases into the main db, one-by-one"

    # First, take the db data passed back from the thread and reinsert it into
    # a new in-memory database (sqlite3 doesn't support sharing connections
    # across threads).
    db = SearchDB()
    db.set_database(":memory:")
    db.deserialize(db_data)

    terms = db.execute("select count(term) from search_terms").fetchone()[0]
    refs = db.execute("select count(*) from file_search").fetchone()[0]
    eprint(f"merging {month} ({terms} terms, {refs} references) into main db")

    db.execute("begin")
    memcur = db.cursor()
    maincur = SRCHDB.cursor()

    missingterms = ({t[0] for t in memcur.execute("select distinct term from search_terms")}
        - {t[0] for t in maincur.execute("select distinct term from search_terms")})

    # If there are any new terms in the incoming db, insert them into the main db
    if missingterms:
        eprint(f"{len(missingterms)} in mem db not yet in main db")
        maincur.executemany("insert into search_terms (term) VALUES (?)",
                            list((t,) for t in missingterms))

    # Map the incoming rowids to rowids in the main db
    memterms = {}
    for (term, rowid) in memcur.execute("select distinct term, rowid from search_terms"):
        memterms[term] = rowid
    mainterms = {}
    for (term, rowid) in maincur.execute("select distinct term, rowid from search_terms"):
        mainterms[term] = rowid
    eprint(f"{len(memterms)} mem db terms, {len(mainterms)} main db terms")

    rowids = {}
    for t in set(memterms) & set(mainterms):
        memrowid = memterms[t] if t in memterms else 0
        mainrowid = mainterms[t] if t in mainterms else 0
        assert memrowid != 0 and mainrowid != 0
        rowids[memrowid] = mainrowid

    # Read the incoming file_search table and map references to the main db rowids
    references = []
    for filename, fragment, reference in memcur.execute("select filename, fragment, reference"
                                                        "  from file_search"):
        reference = int(reference)
        references.append((filename, fragment, rowids[reference]))
    maincur.executemany("insert into file_search"
                        "  (filename, fragment, reference)"
                        "  values"
                        "  (?, ?, ?)", references)

    SRCHDB.commit()
    eprint(f"{month} merged {len(memterms)} terms, {len(references)} references into main db")

def process_month(month, classifier):
    "Process one month's worth of email messages"
    start = dt.datetime.now()
    n = 0
    db = SearchDB()
    db.set_database(":memory:")
    cur = db.cursor()
    cur.execute("begin")
    emails = glob.glob(f"{month}/eml-files/*.eml")
    eprint(f"{month} processing {len(emails)} messages")
    for eml in emails:
        process_file(eml, cur, month, classifier)
        n += 1
        if n % 50 == 0:
            db.commit()
            cur.execute("begin")
    db.commit()
    result = db.serialize()
    db.close()
    eprint(f"{month} processed {n} emails in {(dt.datetime.now()-start).total_seconds()}s")
    return result

def filter_positive(cl, text):
    "Only use sentences which score positive with the NaiveBayesClassifier"
    positive = []
    blob = TextBlob(text)
    upper = 0.65
    for sent in blob.sentences:
        prob_dist = cl.prob_classify(sent)
        if prob_dist.prob("pos") >= upper:
            positive.append(sent)
    return f"{CRLF}{CRLF}".join(positive)


QUOTED = re.compile(r'''\s*"(.*)"\s*$''')
def process_file(f, cur, month, classifier):
    "extract bits from one file"
    f = f.strip()
    msg = read_message(f)

    payload = msg.extract_text()

    if not payload:
        return

    if classifier is not None:
        with BLOB_LOCK:
            payload = filter_positive(classifier, payload)

    subject = trim_subject_prefix(msg["subject"])
    mat = QUOTED.match(subject)
    if mat is not None:
        subject = mat.group(1)
    if subject:
        payload = f"{subject}{CRLF}{CRLF}{payload}"
    terms = sorted(set(get_terms(strip_leading_quotes(strip_footers(payload)))))
    for term in terms:
        rowid = add_term(term, cur)
        fragment = create_fragment(payload, term)
        lastrowid = add_fragment(fragment, f, rowid, cur)
        if lastrowid % 20000 == 0:
            eprint(month, lastrowid)

    (sender, addr) = parse_from(msg["from"])

    sub_frags = set([subject])

    # add from:name, from:someone@somewhere, subject:...
    for term in (f"from:{sender.strip().lower()}",
                 f"from:{addr.strip().lower()}",
                 f"subject:{subject.strip().lower()}",):
        if term in ("from:", "subject:"):
            continue
        rowid = add_term(term, cur)
        add_fragment("", f, rowid, cur)
    for phrase in get_terms(subject):
        if phrase in sub_frags:
            continue
        rowid = add_term(f"subject:{phrase}", cur)
        add_fragment("", f, rowid, cur)

def add_fragment(fragment, f, rowid, cur):
    cur.execute("insert into file_search"
                " (filename, fragment, reference) values (?, ?, ?)",
                (f, fragment, rowid))
    return cur.lastrowid

def have_term(term, cur):
    "return rowid if we already have term in the database, else zero"
    result = cur.execute("select rowid from search_terms"
        "  where term = ?", (term,)).fetchone()
    return result[0] if result else 0

def add_term(term, cur):
    rowid = have_term(term, cur)
    if not rowid:
        cur.execute("insert into search_terms values (?)", (term,))
        rowid = cur.lastrowid
    return rowid

def create_fragment(payload, term):
    "get a fragment of text from the message matching the term"
    pad = ".{2,25}"
    try:
        mat = re.search(fr"({pad})"
                        fr"({re.escape(term).replace(' ', 's*')})"
                        fr"({pad})",
                        payload, re.I)
    except re.error:
        eprint(pad, term, type(payload))
        raise

    if mat is not None:
        pfx, fragment, sfx = [html.escape(s) for s in mat.groups()]
        fragment = f"{pfx}<b>{fragment}</b>{sfx}".strip()
        return re.sub(r"\s+", " ", fragment)
    return ""


def read_csv(csv_file):
    "read a CSV file but return as single dict, not list of dicts"
    records = {}
    with open(csv_file, "r", encoding="utf-8") as wf:
        rdr = csv.DictReader(wf)
        for row in rdr:
            records[row["from"]] = row["to"]
    return records


def common_words():
    word_file = os.path.join(os.path.dirname(__file__), "common-words.txt")
    return read_words(word_file)


def preprocess(phrase):
    "sanitize interesting phrases"
    phrase = re.sub("-+$", "", phrase)
    phrase = phrase.replace("/", " ")
    if phrase in COMMON_WORDS:
        return ""
    words = phrase.split()
    while words and words[0] in COMMON_WORDS:
        del words[0]
    while words and words[-1] in COMMON_WORDS:
        del words[-1]
    # Don't care about eBay URLs at this late date.
    words = [word for word in words if re.search("http.*ebay", word) is None]
    # Or excessively long "words".
    words = [word for word in words if len(word) < 40]
    # Or "words" made up entirely of punctuation.
    words = [word for word in words if set(word) - PUNCTSET]
    # Or "words" that look like urls.
    words = [word for word in words if word.lower()[0:4] != "www."]
    # Somehow we get stuff like "mother 's" out of the noun phrases. Deal with
    # that... ¯\_(ツ)_/¯
    phrase = re.sub(" 's( |$)", r"'s\1", " ".join(words))
    # Finally, exceedingly long or short phrases are uninteresting.
    return "" if len(phrase) < 5 or len(phrase) > 30 else phrase


def merge_plurals(k, _srchdb):
    "map simple plurals to singular"
    # we only want to consider words/phrases if the last word is in the
    # large dictionary - for example, we shouldn't mess with
    # "harry hetchins" because "hetchin" isn't in the large dictionary.
    last = k.split()[-1]

    old = new = k
    for end in ("s", "es"):
        n = len(end)
        # require truncated last word to be in large dictionary and
        # last n characters of the last word to be the plural
        if (last[:-n] in ALL_WORDS and
            last[-n:] == end):
            new = k[:-n]
            break
    return (old, new, "plural")


def merge_ing(k, srchdb):
    "map 'ing' endings to base word"
    last = k.split()[-1]

    old = new = k
    why = "unknown"
    if last[-3:] == "ing":
        # we would merge "bicycling" into "bicycle" in preference
        # to "bicycl"
        for suffix in ("e", ""):
            if (last[:-3].strip() + suffix in ALL_WORDS and
                srchdb.have_term(old[:-3].strip() + suffix)):
                new = old[:-3].strip() + suffix
                why = "-ing"
                break
    return (old, new, why)


def merge_wrong(k, srchdb):
    "merge simple truncations"
    last = k.split()[-1]

    old = new = k
    if last not in ALL_WORDS:
        for suffix in ("e", "es", "s"):
            if last + suffix in ALL_WORDS and srchdb.have_term(k+suffix):
                new = k + suffix
                break
    return old, new, "wrong"


def merge_exceptions(k, _srchdb):
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


def merge_whitespace(k, _srchdb):
    "strip trailing whitespace and merge if possible"
    old = new = k
    why = "noop"
    ks = old.strip()
    if old != ks:
        new = ks
        why = "white"
    return old, new, why


# pylint: disable=unused-argument
def strip_nonprint(k, _srchdb):
    "strip non-printable characters"
    old = new = k
    why = "noop"
    ks = re.sub(r"[^ -~]+", "", old)
    if old != ks:
        new = ks
        why = "non-print"
    return old, new, why


PUNCT = string.punctuation.replace("-", "")
PUNCTSET = set(re.sub("[-_]", "", string.punctuation))

def zap_punct(k, _srchdb):
    "strip leading or trailing punctuation or whitespace and zap terms with punct & no ' '"
    old = new = k
    why = "noop"
    ks = re.sub(f"[ {PUNCT}-]+$", "", old)
    ks = re.sub(f"^[ {PUNCT}-]+", "", ks).strip()
    if ks and ks[0] == "'":
        ks = ""
    if old != ks:
        new = ks
        why = "punct"
    # If term is a single word and contains punctuation other than '-' or '_',
    # get rid of it.
    if set(new) & PUNCTSET and " " not in new:
        new = ""
    return old, new, why


def zap_long_phrases(k, _srchdb):
    "mark long phrases for deletion"
    old = k
    why = "noop"
    words = k.split()
    for (i, word) in reversed(list(enumerate(words))):
        ws = set(word)
        # delete words which are just punctuation
        if ws & PUNCTSET == ws:
            del words[i]
    return old, " ".join(words), why


def postprocess_db():
    "final messing around"
    to_delete = set()

    refs = []
    cur = SRCHDB.cursor()
    for (term, count) in cur.execute("select st.term, count(fs.fragment)"
                                     " from search_terms st, file_search fs"
                                     "  where fs.reference = st.rowid"
                                     "  group by fs.reference"
                                     "  order by st.term"):
        old = new = term
        why = "noop"
        for merge in (merge_exceptions, merge_plurals, merge_ing,
                      merge_wrong, strip_nonprint, zap_punct,
                      zap_long_phrases):
            # pylint: disable=unused-variable
            old, new, why = merge(old, SRCHDB)
            if not new:
                eprint("d:", old)
                to_delete.add(old)
                break
            if new != old:
                eprint(f"pp: {new} |= {old} ({why})")
                add_term(new, cur)
                refs.append((
                    cur.execute("select rowid from search_terms"
                                "  where term = ?", (new,)).fetchone()[0],
                    cur.execute("select rowid from search_terms"
                                "  where term = ?", (old,)).fetchone()[0]
                    ))
                to_delete.add(old)
                old = new

    for (newid, oldid) in refs:
        cur.execute("update file_search"
                    "  set reference = ?"
                    "  where reference = ?", (newid, oldid))

    for (term, count) in cur.execute("select st.term, count(fs.fragment)"
                                     " from search_terms st, file_search fs"
                                     "  where fs.reference = st.rowid"
                                     # always keep synthetic terms...
                                     '    and st.term not like "from:%"'
                                     "  group by fs.reference"
                                     "  order by st.term"):
        if (len(term) < 4 or
            count <= 1 or
            " " not in term and len(term) > 20):
            to_delete.add(term)

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

    for (term,) in cur.execute("select term from search_terms"
                            "  where term not like 'from:%'"):
        if (set(term) & nonprint or
            term[0] in punct or
            term[-1] in punct_nodot or
            phonepat.search(term) is not None):
            to_delete.add(term)
        elif term[-1] == ".":
            # trim trailing periods
            move_these.add((term, term[:-1]))
        elif (mat := wordspat.match(term)) is not None:
            # toss last "word" if it's a single character
            move_these.add((term, mat.group(1)))

    # belt and suspenders
    to_delete.add("")

    move_terms(move_these, SRCHDB)
    delete_exceptions(to_delete, SRCHDB)
    delete_unreferenced_terms(SRCHDB)

def move_terms(from_to, srchdb):
    "move terms from undesirable value to more desirable real estate."
    eprint("moving some terms")
    # We don't really move them, just change the
    # reference. delete_referenced_items will then take care of eliminating the
    # now orphaned terms.
    cur = srchdb.cursor()
    for (old, new) in from_to:
        try:
            (old_rowid,) = cur.execute("select rowid from search_terms"
                                       "  where term = ?", (old,)).fetchone()
        except TypeError:
            eprint("can't find term:", old)
            continue
        new_rowid = add_term(new, cur)
        if old.startswith("camp"):
            eprint(f"{old} ({old_rowid}) -> {new} ({new_rowid})")
        cur.execute("update file_search set reference = ?"
                    "  where reference = ?", (new_rowid, old_rowid))


def delete_unreferenced_terms(srchdb):
    eprint("deleting unreferenced terms")
    cur = srchdb.cursor()
    cur.execute("select rowid from file_search")
    rowids = [x for (x,) in cur.fetchall()]

    to_delete = set()
    for rowid in rowids:
        cur.execute("select count(*) from file_search where reference = ?",
                    (rowid,))
        if cur.fetchone()[0] == 0:
            to_delete.add(rowid)

    n = 0
    to_delete = list(to_delete)
    chunksize = 20000
    while to_delete:
        ids, to_delete = tuple(to_delete[:chunksize]), to_delete[chunksize:]
        n += chunksize
        qmarks = ", ".join(["?"] * len(ids))
        cur.execute(f"delete from search_terms where rowid in ({qmarks})", ids) # nosec
        eprint(n)


def delete_exceptions(to_delete, srchdb):
    "delete terms we determined aren't worth it."
    eprint(f"deleting {len(to_delete)} sketchy terms")
    cur = srchdb.cursor()

    to_delete = list(to_delete)
    n = 0
    chunksize = 20000
    while to_delete:
        terms, to_delete = tuple(to_delete[:chunksize]), to_delete[chunksize:]
        n += chunksize
        qmarks = ", ".join(["?"] * len(terms))
        cur.execute("select distinct rowid from search_terms"   # nosec
                    f"  where term in ({qmarks})", terms)
        rowids = tuple(x[0] for x in cur.fetchall())
        if not rowids:
            continue
        qmarks = ", ".join(["?"] * len(rowids))
        cur.execute("delete from file_search"   # nosec
                    f"  where reference in ({qmarks})", rowids)
        cur.execute("delete from search_terms"                    # nosec
                    f"  where rowid in ({qmarks})", rowids)
        eprint(n)


COMMON_WORDS = common_words()
ALL_WORDS = all_words()
EXCEPTIONS = read_csv(os.path.join(os.path.dirname(__file__),
                                   "buildindex.exc"))


TERM_PAT = re.compile(r"[A-Za-z][-/a-z0-9]{2,}"
                      r"(?:\s+[A-Za-z][-'/a-z0-9]+)*")
DIMENSION_PAT = re.compile(r"[0-9]+[a-z]+$")
def get_terms(text):
    "yield a series of words matching desired pattern"
    seen = set()
    tpat = TERM_PAT
    dpat = DIMENSION_PAT
    with BLOB_LOCK:
        phrases = sorted(set(TextBlob(text).noun_phrases))
    for phrase in phrases:
        lphrase = phrase.lower()
        # common bits embedded in cc'd and forwarded messages.
        if "bikelist" in lphrase or lphrase.startswith("subject"):
            continue
        # not sure where these come from, but there are plenty. delete for now.
        if lphrase[0:3] == "'s " or len(lphrase) == 1:
            continue
        if tpat.match(phrase) is None:
            # print("   nm:", repr(phrase))
            continue

        phrase = preprocess(phrase.lower())
        if not phrase or phrase.count(" ") > 5:
            # extraordinarily long multi-word phrases
            continue

        phrase_len = len(phrase)
        if (" " not in phrase and (phrase_len < 4 or phrase_len > 20) or
            " " in phrase and phrase_len < 7):
            # too short or long one-word phrases
            continue

        words = phrase.split()
        # Always keep the full phrase
        if phrase not in seen:
            seen.add(phrase)
            yield phrase

        # and the first word, if it matches DIMENSION_PAT (useful stuff like
        # 126mm, 130bcd, etc).
        if words[0] not in seen and dpat.match(words[0]) is not None:
            seen.add(words[0])
            yield words[0]

        # and any leading subphrases of at least two words.
        while len(words) > 2:
            del words[-1]
            subphrase = " ".join(words)
            if subphrase not in seen:
                seen.add(subphrase)
                yield subphrase


if __name__ == "__main__":
    sys.exit(main())
