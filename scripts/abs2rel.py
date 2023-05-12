#!/usr/bin/env python3

"Convert embedded absolute href and src links to relative"

import argparse
import os
import sys

from bs4 import BeautifulSoup

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(dest="top", help="top-level directory to process")
    parser.add_argument("-n", "--dry-run", dest="dry_run", default=False,
                        action="store_true", help="Don't write any output")
    args = parser.parse_args()
    for (dirpath, _dirnames, fnames) in os.walk(args.top):
        dp_comps = dirpath.split("/")
        rel = "/".join([".."] * (len(dp_comps) - 1)) or "."
        process_dir(dirpath, fnames, rel, args.dry_run)

def process_dir(dirpath, fnames, rel, dry_run):
    print(dirpath, rel)
    for fname in fnames:
        if not fname.endswith("html"):
            continue
        infname = os.path.join(dirpath, fname)
        with open(infname) as inp:
            raw = inp.read()
        if not dry_run:
            os.rename(infname, os.path.join(dirpath, f"old-{fname}"))
        soup = BeautifulSoup(raw, features="lxml")
        for (tag, attr) in (("img", "src"),
                            ("a", "href"),
                            ("link", "href")):
            for elt in soup.find_all(tag):
                if elt[attr] and elt[attr][0] == "/":
                    newattr = rel + elt[attr]
                    if newattr.endswith("/"):
                        newattr += "index.html"
                    if elt[attr] != newattr:
                        print(attr, elt[attr], "->", newattr)
                        elt[attr] = newattr
        if not dry_run:
            with open(infname, "w") as out:
                out.write(str(soup))

if __name__ == "__main__":
    sys.exit(main())

# from BeautifulSoup import BeautifulSoup
# from os.path import basename, splitext
# soup = BeautifulSoup(my_html_string)
# for img in soup.findAll('img'):
#     img['src'] = 'cid:' + splitext(basename(img['src']))[0]
# my_html_string = str(soup)

# for d in $(for f in $(find . -name '*html' | xargs egrep -li '(href|src)="/') ; do
# echo $(dirname $f)
# done | sort -u) ; do
# up=$(echo $d | tr -dc / | sed -e 's:/:../:g')
# echo "***** $d $up"
# for html in $(find $d -name '*html' ! -name 'new*html') ; do
# echo $html ; sed -e 's:\(href\|src\)="/:\1="$up:' < $html > $(dirname $html)/new-$(basename $html)
# done
# done
