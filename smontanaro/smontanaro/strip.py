#!/usr/bin/env python

"bunch of small functions to strip various cruft from end of emails."

import re

# from .util import eprint

QUOTE_PAT = r'(?:(?:>\s?)*)?'
CRLF = "\r\n"

def strip_footers(payload):
    "strip non-content footers"
    while True:
        new_payload = payload
        for func in (strip_trailing_whitespace,
                     strip_cr_index_pwds,
                     strip_mime,
                     strip_bikelist_footer,
                     strip_juno,
                     strip_virus,
                     strip_virgin,
                     strip_fastmail,
                     strip_yp,
                     strip_aol,
                     strip_yahoo,
                     strip_msn,
                     strip_trailing_underscores):
            # eprint(func.__name__)
            new_payload = func(new_payload)
        if new_payload == payload:
            return payload
        payload = new_payload


def strip_leading_quotes(payload):
    """strip any leading '>' characters"""
    lines = payload.split(CRLF)
    for (i, line) in enumerate(lines):
        lines[i] = re.sub("^(>\s*)*", "", line)
    return CRLF.join(lines)


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
    header = (".*(search for businesses|get a jump)", re.I)
    footer = (".*yellowpages.(lycos|aol).com", re.I)
    return strip_between(payload, header, footer, "yp")

def strip_aol(payload):
    "strip Yahoo! ads"
    header = ("_____", 0)
    footer = (".*yahoo.(ca|com)|yahoo! mail", re.I)
    return strip_between(payload, header, footer, "yahoo")

def strip_yahoo(payload):
    "strip Yahoo! ads"
    header = ("_____", 0)
    footer = (".*yahoo.(ca|com)|yahoo! mail", re.I)
    return strip_between(payload, header, footer, "yahoo")

def strip_juno(payload):
    "strip Juno ads"
    header = "_" * 60
    footer = "https?://.*juno.com"
    return strip_between(payload, header, footer, "juno")

def strip_fastmail(payload):
    "strip fastmail ads"
    header = footer = "http://www.fastmail.fm"
    return strip_between(payload, header, footer, "fastmail")

def strip_virgin(payload):
    "strip Virgin Media email bits"
    header = footer = ".*virginmedia.com"
    return strip_between(payload, header, footer, "virgin")

def strip_virus(payload):
    "strip 'virus checked' lines"
    header = "Virus-checked using McAfee|Outgoing mail is certified Virus Free"
    footer = ("Virus-checked using McAfee|"
              "Version: [0-9]+.[0-9]+.[0-9]+ / Virus Database: [0-9]+ - Release Date:")
    return strip_between(payload, header, footer, "virus")

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
def strip_between(payload, start, end, tag):
    "strip all lines at the end of the strip between start and end"
    s_flags = e_flags = 0
    if isinstance(start, tuple):
        start, s_flags = start
    if isinstance(end, tuple):
        end, e_flags = end
    lines = re.split(r"(\n+)", payload)
    state = "start"
    new_payload = []
    spat = f"{QUOTE_PAT}{start}"
    epat = f"{QUOTE_PAT}{end}"
    # eprint(tag, repr(spat), repr(epat))
    for line in lines:
        if state == "start":
            if re.match(spat, line, s_flags) is not None:
                state = "stripping"
                # eprint(">> elide", tag, state, repr(line))
                continue
            new_payload.append(line)
        else:  # state == "stripping"
            # eprint(">> elide", tag, state, repr(line))
            if re.match(epat, line, e_flags) is not None:
                state = "start"
    new_payload = "".join(new_payload)
    # eprint(">> result:", tag,
    #        "unchanged" if new_payload == payload else "stripped")
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
    # eprint(">> result:", "underscores", lines == payload)
    return lines

def strip_trailing_whitespace(payload):
    "strip trailing whitespace at the bottom of the message"
    if not payload:
        return ""
    lines = re.split(r"(\n+)", payload)
    pat = f"{QUOTE_PAT}" + r"\s*$"
    # eprint(">> lines[-1]:", pat, repr(lines[-1]),
    #       re.match(pat, lines[-1]))
    while lines and re.match(pat, lines[-1]) is not None:
        # eprint(">> del:", repr(lines[-1]))
        del lines[-1]
    lines = "".join(lines)
    # eprint(">> result:", "whitespace", lines == payload)
    return lines
