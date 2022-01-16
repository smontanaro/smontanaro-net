#!/usr/bin/env python

"""Create sitemap for archives."""

import contextlib
import os
import sys

import arrow

TEMPLATE = """
<url>
  <loc>http://www.smontanaro.net/{year}/{month}/{msg}</loc>
  <lastmod>{lastmod}</lastmod>
  <priority>{priority}</priority>
</url>
""".strip()

HEADER = """
<?xml version="1.0" encoding="UTF-8"?>
<urlset
      xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9
            http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">
<!-- based on output from Free Online Sitemap Generator www.xml-sitemaps.com -->
""".strip()

FOOTER = """
</urlset>
""".strip()

PRIORITIES = {
    "index.html": 1.0,
    "maillist.html": 0.8,
    "threads.html": 0.8,
}

@contextlib.contextmanager
def swallow(exceptions):
    "catch and swallow the named exceptions"
    try:
        yield None
    except exceptions:
        pass
    finally:
        pass

def main():
    "see __doc__"

    with swallow((BrokenPipeError, KeyboardInterrupt)):
        print(HEADER)
        for line in sys.stdin:
            emlfile = line.strip()
            dpath, fpath = os.path.split(emlfile)
            year, month = dpath.split("/")[1].split("-")
            msg = int(fpath.split(".")[2], 10)
            msg = f"{msg:04d}"
            lastmod = arrow.get(os.path.getmtime(emlfile))
            lastmod = lastmod.replace(microsecond=0)
            priority = 1.0
            print(f"""
<url>
  <loc>http://www.smontanaro.net/{year}/{month}/{msg}</loc>
  <lastmod>{lastmod}</lastmod>
  <priority>{priority}</priority>
</url>
""".strip())
        print(FOOTER)
    return 0

if __name__ == "__main__":
    sys.exit(main())
