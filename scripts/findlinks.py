#!/usr/bin/env python3

from html.parser import HTMLParser
import os
import sys

class MyHTMLParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attr = "href"
        elif tag == "img":
            attr = "src"
        else:
            return
        ref = dict(attrs)[attr]
        if (ref and ref[0:6] not in ("http:/", "https:") and
            not os.path.exists(ref)):
            print(tag, attr, ref)

def main():
    for fname in sys.argv[1:]:
        print("***", fname, "***")
        parser = MyHTMLParser()
        with open(fname, encoding="latin1") as fobj:
            parser.feed(fobj.read())

if __name__ == "__main__":
    sys.exit(main())
