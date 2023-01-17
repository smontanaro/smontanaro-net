#!/usr/bin/env python3

"mostly to avoid circular dependency at the moment..."

import datetime
import sys


def eprint(*args, file=sys.stderr, dt="%T", **kwds):
    if dt:
        print(datetime.datetime.now().strftime(dt), end=" ", file=file)
    print(*args, file=file, **kwds)
