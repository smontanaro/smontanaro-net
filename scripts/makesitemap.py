#!/usr/bin/env python

"""Create sitemap for archives."""

import contextlib
import glob
import os
import sys

import arrow

MONTH_INDEX = """
<sitemap>
  <loc>https://www.smontanaro.net/CR/{year}/{month}/sitemap.xml</loc>
</sitemap>
""".strip()

TEMPLATE = """
<url>
  <loc>https://www.smontanaro.net/CR/{year}/{month}/{seq}</loc>
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

INDEX_HEADER = """
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
""".strip()

INDEX_FOOTER = """
</sitemapindex>
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

    with open("CR/generated/sitemap.xml", "w", encoding="utf-8") as index:
        with swallow((BrokenPipeError, KeyboardInterrupt)):
            print(INDEX_HEADER, file=index)
            for year_month in glob.glob("CR/20??-??"):
                year, month = os.path.split(year_month)[1].split("-")
                print(MONTH_INDEX.format(year=year, month=month).strip(),
                      file=index)
                with open(os.path.join(year_month, "generated", "sitemap.xml"),
                          "w", encoding="utf-8") as sitemap:
                    print(HEADER, file=sitemap)
                    for emlfile in glob.glob(f"{year_month}/eml-files/*.eml"):
                        emlfile = emlfile.strip()
                        dpath, fpath = os.path.split(emlfile)
                        year, month = dpath.split("/")[1].split("-")
                        seq = int(fpath.split(".")[2], 10)
                        seq = f"{seq:04d}"
                        pckgz = os.path.splitext(emlfile)[0] + ".pck.gz"
                        stampfile = pckgz if os.path.exists(pckgz) else emlfile
                        lastmod = arrow.get(os.path.getmtime(stampfile))
                        lastmod = lastmod.replace(microsecond=0)
                        print(TEMPLATE.format(year=year, month=month, seq=seq,
                                              lastmod=lastmod, priority=1.0),
                                              file=sitemap)
                    print(FOOTER, file=sitemap)
            print(INDEX_FOOTER, file=index)
    return 0

if __name__ == "__main__":
    sys.exit(main())
