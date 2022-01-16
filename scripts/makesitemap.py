#!/usr/bin/env python

"""Create sitemap for archives."""

import contextlib
import os
import sys

import arrow

TEMPLATE = """
<url>
  <loc>http://www.smontanaro.net/{htmlfile}</loc>
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

def main(args):
    "see __doc__"

    with swallow((BrokenPipeError, KeyboardInterrupt)):
        print(HEADER)
        for line in sys.stdin:
            htmlfile = line.strip()
            lastmod = arrow.get(os.path.getmtime(htmlfile))
            lastmod = lastmod.replace(microsecond=0)
            priority = PRIORITIES.get(os.path.split(htmlfile)[-1], 0.5)
            print(TEMPLATE.format(**locals()))
        print(FOOTER)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
