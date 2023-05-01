#!/usr/bin/env python3

"print <a href...> and <img src...> links."

import os
import sys

from smontanaro.util import MyHTMLParser

def main():
    for fname in sys.argv[1:]:
        parser = MyHTMLParser()
        with open(fname, encoding="latin1") as fobj:
            try:
                parser.feed(fobj.read())
            except KeyError:
                # This can happen with a bit of HTML is corrupted by email
                # quoting, e.g., from 2000/10/0675:
                # >  <A
                # >
                # HREF="http://www.cyclesdeoro.com/Classc_Home.htm">Classic
                # > Rendezvous
                # > Vintage bicycles</A>

                print(f"unable to parse {fname}", file=sys.stderr)

if __name__ == "__main__":
    sys.exit(main())
