#!/usr/bin/env python3

"extract ip address and user-agent string from log file on stdin"

import re
import sys

def main():
    pat = re.compile(r'^([0-9]+(?:[.][0-9]+){3,3}) [^"]+"[^"]+" [0-9]+ [0-9]+ "-" "([^"]+)"$')
    for line in sys.stdin:
        mat = pat.match(line.strip())
        if mat is not None:
            groups = mat.groups()
            print(groups[0], groups[1])
    return 0

if __name__ == "__main__":
    sys.exit(main())
