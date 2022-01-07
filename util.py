#!/usr/bin/env python

"Some functions to share between parts of the app"

# Maybe need a Juno stripper:
#
# http://test.smontanaro.net:8080/CR/2008/11/941
# http://test.smontanaro.net:8080/CR/2008/11/944
#
# MSN too?
#
# http://test.smontanaro.net:8080/CR/2001/09/19
#
# And AOL?
#
# http://test.smontanaro.net:8080/CR/2008/06/12

import re

def strip_footers(payload):
    "strip non-content footers"
    while True:
        new_payload = payload
        for func in (strip_trailing_whitespace,
                     strip_mime,
                     strip_bikelist_footer,
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

def strip_between(payload, header, footer, tag):
    "strip all lines at the end of the strip between header and footer"
    lines = re.split(r"(\n+)", payload)
    state = "start"
    new_payload = []
    for line in lines:
        if state == "start":
            if re.match(f"(> )?{header}", line) is not None:
                state = "stripping"
                # print(">> elide", tag, state, repr(line))
                continue
            new_payload.append(line)
        else:  # state == "stripping"
            # print(">> elide", tag, state, repr(line))
            if re.match(f"(> )?{footer}", line) is not None:
                state = "start"
    new_payload = "".join(new_payload)
    # print(">> result:", tag, new_payload == payload)
    return new_payload

def strip_trailing_underscores(payload):
    "strip trailing underscores at the bottom of the message"
    # Looks like 47 underscores in the most common case.
    underscores = "_" * 47
    lines = re.split(r"(\n+)", payload.rstrip())
    if re.match(f"(> )?{underscores}", lines[-1]) is not None:
        lines = lines[:-1]
    lines = "".join(lines)
    # print(">> result:", "underscores", lines == payload)
    return lines

def strip_trailing_whitespace(payload):
    "strip trailing whitespace at the bottom of the message"
    underscores = "_" * 47
    lines = re.split(r"(\n+)", payload.rstrip())
    while re.match(r">?\s*$", lines[-1]) is not None:
        del lines[-1]
    lines = "".join(lines)
    # print(">> result:", "whitespace", lines == payload)
    return lines
