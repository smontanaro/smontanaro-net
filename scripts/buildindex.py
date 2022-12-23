#!/usr/bin/env python3

"construct dumb index of the old CR archives"

import csv
import getopt
import os
import pickle                             # nosec
import string
import sys

import regex as re
from textblob import TextBlob

from smontanaro.util import (read_message, trim_subject_prefix, open_,
                             eprint)
from smontanaro.strip import strip_footers, strip_leading_quotes, CRLF


def main():
    opts, args = getopt.getopt(sys.argv[1:], "h")
    for opt, _arg in opts:
        if opt == "-h":
            eprint("sorry, no help yet")
            return 0

    word_map = {}
    last = ""
    for f in sys.stdin:
        parts = f.split("/")
        if parts[1] != last:
            eprint(">>>", parts[1])
            last = parts[1]
        process_file(f.strip(), word_map)

    postprocess_map(word_map)

    if args:
        outfile = args[0]
        print(f"save {len(word_map)} phrases to {outfile}")
        with open_(outfile, "wb") as pobj:
            pickle.dump(word_map, pobj, protocol=5)

    return 0


def process_file(f, word_map):
    "extract bits from one file"
    f = f.strip()
    msg = read_message(f)
    # Takes care of the content-transfer-encoding but returns bytes
    payload = msg.get_payload(decode=True)
    if payload is None:
        return
    try:
        payload = msg.decode(payload)
    except(LookupError, UnicodeDecodeError) as exc:
        eprint(f, exc)
        return

    quoted = re.compile(r'''\s*"(.*)"\s*$''')
    subject = trim_subject_prefix(msg["subject"])
    mat = quoted.match(subject)
    if mat is not None:
        # print(f"  {subject} -> {mat.group(1)}")
        subject = mat.group(1)
    if subject:
        payload = f"{subject}{CRLF}{CRLF}{payload}"
    for word in get_terms(strip_leading_quotes(strip_footers(payload))):
        if word not in word_map:
            word_map[word] = set()
            if len(word_map) % 1000 == 0:
                print("...", len(word_map))
        word_map[word].add(f)


def read_words(word_file):
    words = set()
    punct = set(string.punctuation)
    with open(word_file, "r", encoding="utf-8") as wf:
        for word in wf:
            if (len(word) < 4 or
                word[0] in string.ascii_uppercase or
                set(word) & punct):
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
    # Somehow we get stuff like "mother 's" out of the noun phrases. Deal with
    # that... ¯\_(ツ)_/¯
    phrase = re.sub(" 's( |$)", r"'s\1", " ".join(words))
    return phrase if len(phrase) >= 5 else ""


# pylint: disable=unused-argument
def merge_plurals(k, word_map):
    "map simple plurals to singular"
    # we only want to consider words/phrases if the last word is in the
    # large dictionary - for example, we shouldn't mess with
    # "harry hetchins" because "hetchin" isn't in the large dictionary.
    last = k.split()[-1]

    old = new = k
    for end in ("s", "es"):
        n = len(end)
        # eprint(k, end, last,
        #        last[:-n] in ALL_WORDS, last[-n:] == end,
        #        k[:-n] in word_map)
        # require truncated last word to be in large dictionary and
        # last n characters of the last word to be the plural
        if (last[:-n] in ALL_WORDS and
            last[-n:] == end):
            new = k[:-n]
            break
    return (old, new, "plural")


def merge_ing(k, word_map):
    "map 'ing' endings to base word"
    last = k.split()[-1]

    old = new = k
    why = "unknown"
    if last[-3:] == "ing":
        # we would merge "bicycling" into "bicycle" in preference
        # to "bicycl"
        for suffix in ("e", ""):
            if (last[:-3].strip() + suffix in ALL_WORDS and
                old[:-3].strip() + suffix in word_map):
                new = old[:-3].strip() + suffix
                why = "-ing"
                break
    return (old, new, why)


def merge_wrong(k, word_map):
    "merge simple truncations"
    last = k.split()[-1]

    old = new = k
    if last not in ALL_WORDS:
        for suffix in ("e", "es", "s"):
            if last + suffix in ALL_WORDS and k + suffix in word_map:
                new = k + suffix
                break
    return old, new, "wrong"


# pylint: disable=unused-argument
def merge_exceptions(k, word_map):
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
def merge_whitespace(k, word_map):
    "strip trailing whitespace and merge if possible"
    old = new = k
    why = "noop"
    ks = old.strip()
    if old != ks:
        new = ks
        why = "white"
    return old, new, why


# pylint: disable=unused-argument
def strip_nonprint(k, word_map):
    "strip non-printable characters"
    old = new = k
    why = "noop"
    ks = re.sub(r"[^ -~]+", "", old)
    if old != ks:
        new = ks
        why = "non-print"
    return old, new, why


PUNCT = string.punctuation.replace("-", "")

# pylint: disable=unused-argument
def strip_punct(k, word_map):
    "strip leading or trailing punctuation or whitespace"
    old = new = k
    why = "noop"
    ks = re.sub(f"[ {PUNCT}-]+$", "", old)
    ks = re.sub(f"^[ {PUNCT}-]+", "", ks).strip()
    if ks and ks[0] == "'":
        ks = ""
    if old != ks:
        new = ks
        why = "punct"
    return old, new, why


def postprocess_map(word_map):
    "final messing around"
    to_delete = set()

    for k in sorted(word_map):
        if len(k) < 4 or len(k) > 32 or len(word_map[k]) <= 1:
            to_delete.add(k)
            continue

        old = new = k
        why = "noop"
        for merge in (merge_exceptions, merge_plurals, merge_ing,
                      merge_wrong, strip_nonprint, strip_punct):
            # pylint: disable=unused-variable
            old, new, why = merge(old, word_map)
            if not new:
                to_delete.add(old)
                break
            if new != old:
                eprint(f"pp: {new} |= {old} ({why})")
                if new not in word_map:
                    word_map[new] = set()
                word_map[new] |= word_map[old]
                to_delete.add(old)
                old = new

    if "" in word_map:
        to_delete.add("")

    for k in word_map:
        if "bikelist.org" in k:
            to_delete.add(k)

    for k in to_delete:
        del word_map[k]


COMMON_WORDS = common_words()
ALL_WORDS = all_words()
EXCEPTIONS = read_csv(os.path.join(os.path.dirname(__file__),
                                   "buildindex.exc"))


def get_terms(text):
    "yield a series of words matching desired pattern"
    pat = re.compile(r"[A-Za-z][-/a-z0-9]{2,}"
                     r"(?:\s+[A-Za-z][-'/a-z0-9]+)*")
    blob = TextBlob(text)
    for phrase in sorted(set(blob.noun_phrases)):
        if pat.match(phrase) is None:
            # print("   nm:", repr(phrase))
            continue
        phrase = preprocess(phrase.lower())
        if (not phrase or
            " " not in phrase and len(phrase) < 4 or
            len(phrase) < 7):
            continue
        words = phrase.split()
        while words:
            yield " ".join(words)
            del words[-1]


if __name__ == "__main__":
    sys.exit(main())
