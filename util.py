#!/usr/bin/env python

"Some functions to share between parts of the app"

import sys

def eprint(*args, file=sys.stderr, **kwds):
    "shorthand"
    return print(*args, file=file, **kwds)
