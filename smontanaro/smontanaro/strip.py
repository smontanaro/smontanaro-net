#!/usr/bin/env python

"bunch of small functions to strip various cruft from end of emails."

import regex as re

# from .log import eprint

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
                     strip_google_groups_footer,
                     strip_juno,
                     strip_virus,
                     strip_virgin,
                     strip_fastmail,
                     strip_yp,
                     strip_advcorps,
                     strip_yahoo,
                     strip_msn,
                     strip_trailing_underscores):
            # eprint(func.__name__)
            new_payload = func(new_payload)
        if new_payload == payload:
            return rewrite_ebay_urls(payload)
        payload = new_payload


EBAY_PAT = re.compile("(https?://.*ebay[.]com[^/]*"
                      "(?:/*[^?\r\n]*)?"                # path
                      "(?:[?][^&\r\n]*"                 # first param
                      "(?:&[^&\r\n]*)*)?"               # successive params
                      ")")
def rewrite_ebay_urls(payload):
    "all ebay urls will be defunct, so shorten the heck out of them."
    # example:
    #   http://cgi.ebay.com/1974-Masi...hash=item120316303908...
    # which we want to rewrite to:
    #   https://www.ebay.com/itm/120316303908

    # Unfortunately, there are plenty of variations, so I think I'll just
    # convert anything to "http://www.ebay.com/<blah>".
    return EBAY_PAT.sub("http://ebay.com/<blah>", payload)


def strip_leading_quotes(payload):
    """strip any leading '>' characters"""
    lines = payload.split(CRLF)
    for (i, line) in enumerate(lines):
        lines[i] = re.sub(r"^(>\s*)*", "", line)
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
    return _strip_helper(payload, header, footer)

def strip_google_groups_footer(payload):
    "strip the later CR mailing list footer"

    header = "You received this message because you are subscribed to the Google Groups"
    footer = "For more options, visit this group at http://groups.google.com/group"
    payload = _strip_helper(payload, header, footer, maxlines=4)
    if payload.endswith("\n--"):
        payload = payload[:-2].rstrip()
    return payload

def strip_bikelist_footer(payload):
    "strip the earlier CR mailing list footer"
    # The footer looks like this:
    #
    # Classicrendezvous mailing list
    # Classicrendezvous@bikelist.org
    #  http://www.bikelist.org/mailman/listinfo/classicrendezvous

    header = "Classicrendezvous mailing list"
    footer = "http://www.bikelist.org/mailman/listinfo/classicrendezvous"
    return _strip_helper(payload, header, footer, maxlines=5)

def strip_yp(payload):
    "strip Yellow Pages ads"
    header = (".*(search for businesses|get a jump)", re.I)
    footer = (".*SRC=lycos10|yellowpages.(lycos|aol).com", re.I)
    return _strip_helper(payload, header, footer, maxlines=10)

def strip_advcorps(payload):
    "strip AdventureCORPS ads"
    header = ("adventurecorps", re.I)
    footer = ("newsletter.*adventurecorps", re.I)
    return _strip_helper(payload, header, footer, maxlines=5)

def strip_yahoo(payload):
    "strip Yahoo! ads"
    header = "_____"
    footer = (".*yahoo.(ca|com)|yahoo! mail", re.I)
    return _strip_helper(payload, header, footer, maxlines=5)

def strip_juno(payload):
    "strip Juno ads"
    header = "_" * 60
    footer = "https?://.*juno.com"
    return _strip_helper(payload, header, footer, maxlines=5)

def strip_fastmail(payload):
    "strip fastmail ads"
    header = footer = "http://www.fastmail.fm"
    return _strip_helper(payload, header, footer, maxlines=3)

def strip_virgin(payload):
    "strip Virgin Media email bits"
    header = footer = ".*virginmedia.com"
    return _strip_helper(payload, header, footer, maxlines=3)

def strip_virus(payload):
    "strip 'virus checked' lines"
    header = "Virus-checked using McAfee|Outgoing mail is certified Virus Free"
    footer = ("Virus-checked using McAfee|"
              "Version: [0-9]+.[0-9]+.[0-9]+ / Virus Database: [0-9]+ - Release Date:")
    return _strip_helper(payload, header, footer, maxlines=5)

def strip_msn(payload):
    "a bit looser, hopefully doesn't zap actual content"
    header = ".* MSN"
    footer = ".*https?:.*msn.com"
    return _strip_helper(payload, header, footer, maxlines=5)

def strip_cr_index_pwds(payload):
    "this occurs on occasion. Strip to remove passwords."
    header = "Passwords for classicrendezvous-index@catfood.phred.org"
    footer = ".*index%40catfood.phred.org"
    return _strip_helper(payload, header, footer)

# pylint: disable=unused-argument
def _strip_helper(payload, start, end, maxlines=10**10):
    """Strip all lines at the end of the strip between start and end patterns.

    After the start pattern is matched, the end pattern must be found
    before maxlines more lines have been read.
    """

    s_flags = e_flags = 0
    if isinstance(start, tuple):
        start, s_flags = start
    if isinstance(end, tuple):
        end, e_flags = end

    lines = re.split(r"(\r?\n+)", payload)
    state = "start"
    new_payload = []
    pappend = new_payload.append
    smatch = re.compile(f"{QUOTE_PAT}{start}", flags=s_flags).match
    ematch = re.compile(f"{QUOTE_PAT}{end}", flags=e_flags).match
    stripped = []
    for line in lines:
        # eprint(state, line.rstrip())
        if state == "terminated":
            pappend(line)
        elif state == "start":
            if smatch(line) is None:
                pappend(line)
                continue
            i = 0
            state = "stripping"
            stripped.append(line)
        else:  # state == "stripping"
            stripped.append(line)
            if ematch(line) is not None:
                state = "start"
                stripped = []
                continue
            i += 1
            if i >= maxlines:
                # eprint("terminated without seeing the footer!")
                state = "terminated"
                new_payload.extend(stripped)
    return "".join(new_payload)

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
