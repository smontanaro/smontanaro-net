#!/usr/bin/env python3

"Extract gunicorn traceback info from syslog"

import re
import sys

def main():
    tb_line = re.compile(r"gunicorn\[[0-9]+\]: Traceback")
    inside_line = re.compile(r"gunicorn\[[0-9]+\]:  +")

    state = "start"
    nprints = 0
    for line in sys.stdin:
        match state:
            case "start":
                if tb_line.search(line) is not None:
                    state = "inside"
                    print(line.rstrip())
                    nprints += 1
            case "inside":
                if inside_line.search(line) is not None:
                    print(line.rstrip())
                    nprints += 1
                else:
                    state = "counting"
                    n = 1
                    print(line.rstrip())
                    nprints += 1
            case "counting":
                if tb_line.search(line) is not None:
                    # Bump into the next traceback
                    print(line.rstrip())
                    nprints += 1
                    state = "inside"
                elif n >= 3:
                    print()
                    nprints += 1
                    state = "start"
                else:
                    n += 1
                    print(line.strip())
                    nprints += 1

    if nprints == 0:
        print("No recent tracebacks to study")


if __name__ == "__main__":
    sys.exit(main())
