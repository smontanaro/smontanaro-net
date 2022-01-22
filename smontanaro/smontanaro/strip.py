#!/usr/bin/env python

"bunch of small functions to strip various cruft from end of emails."

import re

QUOTE_PAT = r'(?:(?:>\s?)*)?'

def strip_footers(payload):
    "strip non-content footers"
    while True:
        new_payload = payload
        for func in (strip_trailing_whitespace,
                     strip_cr_index_pwds,
                     strip_mime,
                     strip_bikelist_footer,
                     strip_juno,
                     strip_yp,
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
    # --- StripMime Report --...
    # multipart/alternative
    #   text/plain (text body -- kept)
    #   text/html
    # ---
    #

    # I am just stripping from the first line to the last and
    # sweeping away anything in the middle.

    header = "--- StripMime Report --"
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

def strip_yp(payload):
    "strip Yellow Pages ads"
    header = "(?i).*get a jump"
    footer = "(?i).*yellowpages.(lycos|aol).com"
    return strip_between(payload, header, footer, "yp")

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
    # print(tag, repr(header), repr(footer))
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
    # print(">> result:", tag, "unchanged" if new_payload == payload else "stripped")
    return new_payload

def strip_trailing_underscores(payload):
    "strip trailing underscores at the bottom of the message"
    # Looks like 47 underscores in the most common case.
    underscores = "_{35,50}"
    hyphens = "-{35,45}"
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
    while lines and re.match(pat, lines[-1]) is not None:
        # print(">> del:", repr(lines[-1]))
        del lines[-1]
    lines = "".join(lines)
    # print(">> result:", "whitespace", lines == payload)
    return lines
