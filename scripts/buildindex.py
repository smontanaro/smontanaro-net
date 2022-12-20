#!/usr/bin/env python3

"construct dumb index of the old CR archives"

import csv
import getopt
import os
import pickle                             # nosec
import re
import string
import sys

from smontanaro.util import read_message, trim_subject_prefix


def main():
    opts, args = getopt.getopt(sys.argv[1:], "h")
    for opt, _arg in opts:
        if opt == "-h":
            print("sorry, no help yet", file=sys.stderr)
            return 0

    word_map = {}
    for f in sys.stdin:
        process_file(f.strip(), word_map)

    postprocess_map(word_map)

    print("found", len(word_map), "words and phrases")
    if args:
        outfile = args[0]
        print(f"save map to {outfile}")
        with open(outfile, "wb") as pobj:
            pickle.dump(word_map, pobj)

    return 0


def process_file(f, word_map):
    "extract bits from one file"
    f = f.strip()
    msg = read_message(f)
    payload = msg.get_payload(decode=True)
    if payload is None:
        return
    charset = msg.get_content_charset() or "utf-8"
    # heuristic: sort so we try latin-1 before utf-8
    for cs in sorted(set((charset, "utf-8", "latin-1"))):
        try:
            payload = payload.decode(cs)
        except (LookupError, UnicodeDecodeError) as exc:
            print(f, exc, file=sys.stderr)
            return
        else:
            break
    else:
        return
    for word in get_terms(payload):
        if word not in word_map:
            word_map[word] = set()
        word_map[word].add(f)
    subject = trim_subject_prefix(msg["subject"])
    if subject:
        if subject not in word_map:
            word_map[subject] = set()
        word_map[subject].add(f)


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
    phrase = " ".join(words)
    return phrase if len(phrase) >= 5 else ""


def merge_plurals(k, word_map):
    "map simple plurals to singular"
    # we only want to consider words/phrases if the last word is in the
    # large dictionary - for example, we shouldn't mess with
    # "harry hetchins" because "hetchin" isn't in the large dictionary.
    last = k.split()[-1]

    old = new = None
    for end in ("s", "es"):
        n = len(end)
        # require truncated last word to be in large dictionary and
        # last n characters of the last word to be the plural and
        # truncated word/phrase is also in the word map
        if (last[:-n] in ALL_WORDS and
            last[-n:] == end and
            k[:-n] in word_map):
            old = k
            new = k[:-n]
            break
    return (old, new, "plural")


def merge_ing(k, word_map):
    "map 'ing' endings to base word"
    last = k.split()[-1]

    old = new = None
    why = "unknown"
    for end in ("ing",):
        n = len(end)
        if last[-n:] == end:
            # we would merge "bicycling" into "bicycle" in preference
            # to "bicycl"
            for suffix in ("e", ""):
                if (last[:-n] + suffix in ALL_WORDS and
                    k[:-n] + suffix in word_map):
                    old = k
                    new = k[:-n] + suffix
                    why = f"-{end}"
                    break
    return (old, new, why)


def merge_wrong(k, word_map):
    "merge simple truncations"
    last = k.split()[-1]

    old = new = None
    if last not in ALL_WORDS:
        for suffix in ("e", "es", "s"):
            if last + suffix in ALL_WORDS and k + suffix in word_map:
                old = k
                new = k + suffix
                break
    return old, new, "wrong"


def merge_exceptions(k, word_map):
    "hand-crafted merge"
    # a CSV file contains 'from' and 'to' columns. The 'from' column can match
    # in two ways, either an exact match for `k` or as an exact match for the
    # last word in `k`.
    last = k.split()[-1]
    old = new = None
    why = "noop"
    if k in EXCEPTIONS:
        old = k
        new = EXCEPTIONS[k]
    elif last in EXCEPTIONS:
        old = k
        new = " ".join(k.split()[:-1] + [EXCEPTIONS[last]])
    if new is not None:
        if new not in word_map:
            word_map[new] = set()
        why = "exc"
    return old, new, why


def postprocess_map(word_map):
    "final messing around"
    to_delete = set()
    for k in sorted(word_map):
        if len(k) < 4:
            to_delete.add(k)
            continue

        old = new = None
        for merge in (merge_exceptions, merge_plurals, merge_ing,
                      merge_wrong):
            old, new, why = merge(k, word_map)
            if old is not None:
                break
        else:
            continue

        if new != old:
            print(f"pp: {new} |= {old} ({why})", file=sys.stderr)
            word_map[new] |= word_map[old]
            to_delete.add(old)

    for k in to_delete:
        del word_map[k]


COMMON_WORDS = common_words()
ALL_WORDS = all_words()
EXCEPTIONS = read_csv(os.path.join(os.path.dirname(__file__),
                                   "buildindex.exc"))


def get_terms(text):
    "yield a series of words matching desired pattern"
    pat = re.compile(r"([A-Z][-/a-z0-9]+(?: +[A-Z][-/a-z0-9]+)*)")
    seen = set()
    for phrase in pat.findall(text):
        phrase = preprocess(phrase.lower())
        if not phrase:
            continue
        if phrase in seen or len(phrase) < 5:
            continue
        words = phrase.split()
        while words:
            yield " ".join(words)
            del words[-1]


if __name__ == "__main__":
    sys.exit(main())
