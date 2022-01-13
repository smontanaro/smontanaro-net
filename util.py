#!/usr/bin/env python

"Some functions to share between parts of the app"

# Other possible candidates for footer strippers
#
# Yahoo! Mail
#
# http://test.smontanaro.net:8080/CR/2006/04/676
#
# MSN
#
# http://test.smontanaro.net:8080/CR/2001/09/19
#
# AOL
#
# http://test.smontanaro.net:8080/CR/2008/06/12
#
# mail2web
#
# http://test.smontanaro.net:8080/CR/2006/4/659
#
# Yahoo! Auctions
#
# http://test.smontanaro.net:8080/CR/2001/5/00019

import re

QUOTE_PAT = r'(?:>+\s?)?'

def strip_footers(payload):
    "strip non-content footers"
    while True:
        new_payload = payload
        for func in (strip_trailing_whitespace,
                     strip_cr_index_pwds,
                     strip_mime,
                     strip_bikelist_footer,
                     strip_juno,
                     strip_msn,
                     strip_trailing_underscores):
            new_payload = func(new_payload)
        if new_payload == payload:
            return payload
        payload = new_payload

def strip_mime(payload):
    "strip the StripMime Report block."
    # The StripMime block looks like this:
    #
    # --- StripMime Report -- processed MIME parts ---
    # multipart/alternative
    #   text/plain (text body -- kept)
    #   text/html
    # ---
    #

    # I am just stripping from the first line to the last and
    # sweeping away anything in the middle.

    header = "--- StripMime Report -- processed MIME parts ---"
    footer = "---"
    return strip_between(payload, header, footer, "mime")

def strip_bikelist_footer(payload):
    "strip the CR mailing list footer"
    # The footer looks like this:
    #
    # Classicrendezvous mailing list
    # Classicrendezvous@bikelist.org
    #  http://www.bikelist.org/mailman/listinfo/classicrendezvous

    header = "Classicrendezvous mailing list"
    footer = "http://www.bikelist.org/mailman/listinfo/classicrendezvous"
    return strip_between(payload, header, footer, "bikelist")

def strip_juno(payload):
    "strip Juno ads"
    header = "_" * 60
    footer = "https?://.*juno.com"
    return strip_between(payload, header, footer, "juno")

def strip_msn(payload):
    "a bit looser, hopefully doesn't zap actual content"
    header = ".* MSN"
    footer = ".*https?:.*msn.com"
    return strip_between(payload, header, footer, "msn")

def strip_cr_index_pwds(payload):
    "this occurs on occasion. Strip to remove passwords."
    header = "Passwords for classicrendezvous-index@catfood.phred.org"
    footer = ".*index%40catfood.phred.org"
    return strip_between(payload, header, footer, "passwords")

# pylint: disable=unused-argument
def strip_between(payload, header, footer, tag):
    "strip all lines at the end of the strip between header and footer"
    lines = re.split(r"(\n+)", payload)
    state = "start"
    new_payload = []
    for line in lines:
        if state == "start":
            if re.match(f"{QUOTE_PAT}{header}", line) is not None:
                state = "stripping"
                # print(">> elide", tag, state, repr(line))
                continue
            new_payload.append(line)
        else:  # state == "stripping"
            # print(">> elide", tag, state, repr(line))
            if re.match(f"{QUOTE_PAT}{footer}", line) is not None:
                state = "start"
    new_payload = "".join(new_payload)
    # print(">> result:", tag, new_payload == payload)
    return new_payload

def strip_trailing_underscores(payload):
    "strip trailing underscores at the bottom of the message"
    # Looks like 47 underscores in the most common case.
    underscores = "_{45,50}"
    hyphens = "-{40,45}"
    # Juno dumps some cruft at the end of its URL which seems to be
    # separated from the rest of the URL by a newline. I treat it like
    # a trailing dashed line.
    juno_dashes = "[0-9A-Za-z]+/$"
    dashed_line = f"(?:{hyphens}|{underscores}|{juno_dashes})"
    lines = re.split(r"(\n+)", payload.rstrip())
    if re.match(f"{QUOTE_PAT}{dashed_line}", lines[-1]) is not None:
        lines = lines[:-1]
    lines = "".join(lines)
    # print(">> result:", "underscores", lines == payload)
    return lines

def strip_trailing_whitespace(payload):
    "strip trailing whitespace at the bottom of the message"
    if not payload:
        return ""
    lines = re.split(r"(\n+)", payload)
    pat = f"{QUOTE_PAT}" + r"\s*$"
    # print(">> lines[-1]:", pat, repr(lines[-1]),
    #       re.match(pat, lines[-1]))
    while re.match(pat, lines[-1]) is not None:
        # print(">> del:", repr(lines[-1]))
        del lines[-1]
    lines = "".join(lines)
    # print(">> result:", "whitespace", lines == payload)
    return lines

def get_thread_root(msgid, cur):
    """return the root of the message tree in which msgid resides."""

    while True:
        cur.execute("select parent"
                    "  from msgreplies"
                    "  where messageid = ?",
                    (msgid,))
        result = cur.fetchone()
        if not result:
            return msgid
        msgid = result[0]

# def build_thread_tree(msgid, cur, associations=None, ids=None):
#     "return a structure containing the thread(s) involving msgid."
#     if associations is None:
#         associations = set()
#     if ids is None:
#         ids = set()
#     if msgid in ids:
#         return (associations, ids)
#     ids.add(msgid)
#     to_do = set()
#     # Find descendants
#     cur.execute("select messageid, reference"
#                 "  from msgrefs"
#                 "  where messageid = ?",
#                 (msgid,))
#     for pair in cur.fetchall():
#         associations.add(pair)
#         to_do.add(pair[1])
#     # ... and ancestors
#     cur.execute("select messageid, reference"
#                 "  from msgrefs"
#                 "  where reference = ?",
#                 (msgid,))
#     for pair in cur.fetchall():
#         associations.add(pair)
#         to_do.add(pair[0])

#     to_do -= ids
#     for ref in to_do:
#         build_thread_tree(ref, cur, associations, ids)
#     return (associations, ids)
