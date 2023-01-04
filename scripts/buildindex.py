#!/usr/bin/env python3

"construct dumb index of the old CR archives"

import csv
import getopt
import html
import logging
import os
import re
import string
import sys

import html2text
import regex as re
from textblob import TextBlob

from smontanaro.util import (read_message, trim_subject_prefix,
                             eprint, parse_from)
from smontanaro.strip import strip_footers, strip_leading_quotes, CRLF

from smontanaro.srchdb import ensure_search_db, have_term, add_term


def main():
    opts, args = getopt.getopt(sys.argv[1:], "h")
    for opt, _arg in opts:
        if opt == "-h":
            eprint("sorry, no help yet")
            return 0

    conn = ensure_search_db(args[0])
    last = ""
    for f in sys.stdin:
        parts = f.split("/")
        if parts[1] != last:
            eprint(">>>", parts[1])
            last = parts[1]
        process_file(f.strip(), conn)

    postprocess_db(conn)

    total = ones = twos = 0
    cur = conn.cursor()
    for count in cur.execute("select count(fs.fragment)"
                             " from search_terms st, file_search fs"
                             "  where fs.reference = st.rowid"
                             "  group by fs.reference"
                             "  order by st.term"):
        total += 1
        if count == 1:
            ones += 1
        elif count == 2:
            twos += 1

    eprint(f"{ones} terms with just one ref.")
    eprint(f"{twos} terms with just two refs.")
    eprint(f"{total} total terms.")

    return 0


def extract_text(msg):
    "recursively extract text bits of message payload"
    body_parts = []
    content_type = msg.get_content_type()
    if content_type == "text/plain":
        body_parts.append(msg.decode(msg.get_payload(decode=True)))
    elif content_type == "text/html":
        # This will return Markdown, not quite what we want
        text_maker = html2text.HTML2Text()
        text_maker.ignore_links = True
        body_parts.append(text_maker.handle(msg.decode(msg.get_payload(decode=True))))
    elif msg.get_content_maintype() == "multipart":
        for part in msg.walk():
            if part == msg:
                continue
            body_parts.append(extract_text(part))
    elif msg.get_content_maintype() == "image":
        pass
    else:
        logging.warning("Unrecognized content type: %s", content_type)
    return "\n\n".join(body_parts)


QUOTED = re.compile(r'''\s*"(.*)"\s*$''')
def process_file(f, conn):
    "extract bits from one file"
    f = f.strip()
    msg = read_message(f)

    payload = extract_text(msg)

    if not payload:
        return

    subject = trim_subject_prefix(msg["subject"])
    mat = QUOTED.match(subject)
    if mat is not None:
        # eprint(f"  {subject} -> {mat.group(1)}")
        subject = mat.group(1)
    if subject:
        payload = f"{subject}{CRLF}{CRLF}{payload}"
    cur = conn.cursor()
    cur.execute("begin")
    for term in get_terms(strip_leading_quotes(strip_footers(payload))):
        rowid = add_term(term, cur)
        fragment = create_fragment(payload, term)
        if fragment:
            cur.execute("insert into file_search"
                        " (filename, fragment, reference) values (?, ?, ?)",
                        (f, fragment, rowid))
            if cur.lastrowid % 10000 == 0:
                eprint(cur.lastrowid)

    (sender, addr) = parse_from(msg["from"])

    # from:name & from:someone@somewhere
    for term in (f"from:{sender.strip().lower()}",
                 f"from:{addr.strip().lower()}"):
        if term == "from:":
            continue
        rowid = add_term(term, cur)
        cur.execute("insert into file_search"
                    " (filename, fragment, reference) values (?, ?, ?)",
                    (f, "", rowid))
        if cur.lastrowid % 10000 == 0:
            eprint(cur.lastrowid)
    cur.execute("commit")


def create_fragment(payload, term):
    "get a fragment of text from the message matching the term"
    pad = ".{2,25}"
    try:
        mat = re.search(fr"({pad})({re.escape(term).replace(' ', 's*')})({pad})", payload, re.I)
    except re.error:
        eprint(pad, term, type(payload))
        raise

    fragment = ""
    if mat is not None:
        pfx, fragment, sfx = [html.escape(s) for s in mat.groups()]
        fragment = f"{pfx}<b>{fragment}</b>{sfx}".strip()
    return re.sub(r"\s+", " ", fragment)


def read_words(word_file):
    words = set()
    with open(word_file, "r", encoding="utf-8") as wf:
        for word in wf:
            if (len(word) < 4 or
                word[0] in string.ascii_uppercase or
                set(word) & PUNCTSET):
                continue
            words.add(word.lower().strip())
    return words


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


def all_words():
    dictionaries = [
        "/usr/share/dict/american-english-large",
        "/usr/share/dict/american-english",
        "/usr/share/dict/words",
    ]
    for word_file in dictionaries:
        if os.path.exists(word_file):
            return read_words(word_file)

    raise ValueError("no dictionary found")


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


# pylint: disable=unused-argument
def merge_plurals(k, conn):
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


def merge_ing(k, conn):
    "map 'ing' endings to base word"
    last = k.split()[-1]

    old = new = k
    why = "unknown"
    if last[-3:] == "ing":
        # we would merge "bicycling" into "bicycle" in preference
        # to "bicycl"
        for suffix in ("e", ""):
            if (last[:-3].strip() + suffix in ALL_WORDS and
                have_term(old[:-3].strip() + suffix, conn)):
                new = old[:-3].strip() + suffix
                why = "-ing"
                break
    return (old, new, why)


def merge_wrong(k, conn):
    "merge simple truncations"
    last = k.split()[-1]

    old = new = k
    if last not in ALL_WORDS:
        for suffix in ("e", "es", "s"):
            if last + suffix in ALL_WORDS and have_term(k+suffix, conn):
                new = k + suffix
                break
    return old, new, "wrong"


# pylint: disable=unused-argument
def merge_exceptions(k, conn):
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


# pylint: disable=unused-argument
def merge_whitespace(k, conn):
    "strip trailing whitespace and merge if possible"
    old = new = k
    why = "noop"
    ks = old.strip()
    if old != ks:
        new = ks
        why = "white"
    return old, new, why


# pylint: disable=unused-argument
def strip_nonprint(k, conn):
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

# pylint: disable=unused-argument
def zap_punct(k, conn):
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


# pylint: disable=unused-argument
def zap_long_phrases(k, conn):
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


def postprocess_db(conn):
    "final messing around"
    to_delete = set()

    refs = []
    cur = conn.cursor()
    cur.execute("begin")
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
            old, new, why = merge(old, conn)
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
    cur.execute("commit")

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

    # belt and suspenders
    to_delete.add("")

    delete_exceptions(to_delete, conn)

    delete_unreferenced_terms(conn)


def delete_unreferenced_terms(conn):
    eprint("deleting unreferenced terms")
    cur = conn.cursor()
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
    chunksize = 10000
    while to_delete:
        cur.execute("begin")
        ids, to_delete = tuple(to_delete[:chunksize]), to_delete[chunksize:]
        n += chunksize
        qmarks = ", ".join(["?"] * len(ids))
        cur.execute(f"delete from search_terms where rowid in ({qmarks})", ids)
        eprint(n)
        cur.execute("commit")


def delete_exceptions(to_delete, conn):
    "delete terms we determined aren't worth it."
    eprint(f"deleting {len(to_delete)} sketchy terms")
    cur = conn.cursor()

    to_delete = list(to_delete)
    n = 0
    chunksize = 10000
    while to_delete:
        cur.execute("begin")
        terms, to_delete = tuple(to_delete[:chunksize]), to_delete[chunksize:]
        n += chunksize
        qmarks = ", ".join(["?"] * len(terms))
        cur.execute("select distinct rowid from search_terms"
                    f"  where term in ({qmarks})", terms)
        rowids = tuple(x[0] for x in cur.fetchall())
        if not rowids:
            continue
        qmarks = ", ".join(["?"] * len(rowids))
        cur.execute("delete from file_search"
                    f"  where reference in ({qmarks})", rowids)
        cur.execute("delete from search_terms"
                    f"  where rowid in ({qmarks})", rowids)
        eprint(n)
        cur.execute("commit")


COMMON_WORDS = common_words()
ALL_WORDS = all_words()
EXCEPTIONS = read_csv(os.path.join(os.path.dirname(__file__),
                                   "buildindex.exc"))


def get_terms(text):
    "yield a series of words matching desired pattern"
    pat = re.compile(r"[A-Za-z][-/a-z0-9]{2,}"
                     r"(?:\s+[A-Za-z][-'/a-z0-9]+)*")
    seen = set()
    for phrase in set(TextBlob(text).noun_phrases):
        lphrase = phrase.lower()
        # common bits embedded in cc'd and forwarded messages.
        if "bikelist" in lphrase or lphrase.startswith("subject"):
            continue
        # not sure where these come from, but there are plenty. delete for now.
        if lphrase[0:3] == "'s " or len(lphrase) == 1:
            continue
        if pat.match(phrase) is None:
            # print("   nm:", repr(phrase))
            continue

        phrase = preprocess(phrase.lower())
        if not phrase or phrase.count(" ") > 5:
            # extraordinarily long multi-word phrases
            continue

        if (" " not in phrase and (len(phrase) < 4 or len(phrase) > 20) or
            " " in phrase and len(phrase) < 7):
            # too short or long one-word phrases
            continue

        words = phrase.split()
        while words:
            subphrase = " ".join(words)
            if subphrase not in seen:
                seen.add(subphrase)
                yield subphrase
            del words[-1]


if __name__ == "__main__":
    sys.exit(main())
