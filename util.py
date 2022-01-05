#!/usr/bin/env python

"Some functions to share between parts of the app"

import re
import sys

def eprint(*args, file=sys.stderr, **kwds):
    "shorthand"
    return print(*args, file=file, **kwds)

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

    lines = re.split(r"(\n+)", payload)
    state = "start"
    new_payload = []
    for line in lines:
        if state == "start":
            if line.startswith(header):
                state = "stripping"
                continue
            new_payload.append(line)
        else:  # state == "stripping"
            if line.startswith(footer):
                state = "start"
    return "".join(new_payload)
