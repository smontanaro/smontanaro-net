#!/usr/bin/env python3

"Extract gunicorn traceback info from syslog"

import re
import sys

def main():
    tb_line = re.compile(r"gunicorn\[[0-9]+\]: Traceback")
    inside_line = re.compile(r"gunicorn\[[0-9]+\]:  +")

    state = "start"
    for line in sys.stdin:
        match state:
            case "start":
                if tb_line.search(line) is not None:
                    state = "inside"
                    print(line.rstrip())
            case "inside":
                if inside_line.search(line) is not None:
                    print(line.rstrip())
                else:
                    state = "counting"
                    n = 1
                    print(line.rstrip())
            case "counting":
                if tb_line.search(line) is not None:
                    # Bump into the next traceback
                    print(line.rstrip())
                    state = "inside"
                elif n >= 3:
                    print()
                    state = "start"
                else:
                    n += 1
                    print(line.strip())

if __name__ == "__main__":
    sys.exit(main())
