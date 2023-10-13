#!/usr/bin/env python

"date handling bits"

import datetime
import sqlite3

import arrow
import dateutil.parser
import dateutil.tz
import regex as re


TZMAP = {
    # dumb heuristics - keep these first
    "+0000 GMT": "UTC",
    " 0 (GMT)": " UTC",
    " -800": " -0800",
    # more typical mappings (leading space to avoid stuff like "(EST)")
    " EST": " America/New_York",
    " EDT": " America/New_York",
    " CST": " America/Chicago",
    " CDT": " America/Chicago",
    " MST": " America/Denver",
    " MDT": " America/Denver",
    " PST": " America/Los_Angeles",
    " PDT": " America/Los_Angeles",
    " Pacific Daylight Time": " America/Los_Angeles",
}

ARROW_FORMATS = [
    "YYYY/MM/DD ddd A hh:mm:ss ZZZ",
    "ddd, DD MMM YYYY HH:mm:ss ZZZ",
    "ddd, D MMM YYYY HH:mm:ss ZZZ",
    "YYYY/MM/DD ddd A hh:mm:ss ZZ",
    "ddd, DD MMM YYYY HH:mm:ss ZZ",
    "ddd, D MMM YYYY HH:mm:ss ZZ",
    "YYYY/MM/DD ddd A hh:mm:ss Z",
    "ddd, DD MMM YYYY HH:mm:ss Z",
    "ddd, D MMM YYYY HH:mm:ss Z",
    "DD MMM YYYY HH:mm:ss ZZZ",
    "D MMM YYYY HH:mm:ss ZZZ",
    "YYYY-MM-DD, H:mmA ZZZ",
]

TZINFOS = {
    "EST": dateutil.tz.gettz("America/New_York"),
    "EDT": dateutil.tz.gettz("America/New_York"),
    "CST": dateutil.tz.gettz("America/Chicago"),
    "CDT": dateutil.tz.gettz("America/Chicago"),
    "MST": dateutil.tz.gettz("America/Denver"),
    "MDT": dateutil.tz.gettz("America/Denver"),
    "PST": dateutil.tz.gettz("America/Los_Angeles"),
    "PDT": dateutil.tz.gettz("America/Los_Angeles"),
    "SGT": dateutil.tz.gettz("Asia/Singapore"),
    "UT": dateutil.tz.UTC,
}

def parse_date(timestring):
    "A few tries to parse message dates"
    # Plenty of syntax variability in Date: headers. This code and the
    # ARROW_FORMATS list above take care of what I found.
    timestring = timestring.strip()
    if timestring.lower().startswith("date:"):
        # print(f"strip leading 'date:' from {timestring}")
        timestring = timestring.split(maxsplit=1)[1].strip()
    timestring = timestring.strip()
    # map obsolete names since arrow appears not to do that.
    timestring = timestring.strip()
    for obsolete, name in TZMAP.items():
        tzs = timestring.replace(obsolete, name)
        if tzs != timestring:
            #print(f"{timestring} -> {tzs}")
            timestring = tzs
            break
    if timestring.endswith(")"):
        timestring = re.sub(r"\s*\([^)]*\)$", "", timestring)
    try:
        # Always create Arrow, so we always have a non-None tzinfo
        timestamp = arrow.get(dateutil.parser.parse(timestring,
            tzinfos=TZINFOS))
    except dateutil.parser.ParserError:
        # try arrow with its format capability - fine to let it raise
        # an exception.
        timestamp = arrow.get(timestring, ARROW_FORMATS)
    return timestamp.datetime

# Beginning in Python 3.12, default datetime adapters for sqlite3 are
# deprecated. This code is a slight modification of the example adapter code
# given in the sqlite3 documentation.

def adapt_date_iso(val):
    """Adapt datetime.date to ISO 8601 date."""
    return val.isoformat()

def adapt_datetime_iso(val):
    """Adapt datetime.datetime to timezone-naive ISO 8601 date."""
    return val.isoformat()

def adapt_datetime_epoch(val):
    """Adapt datetime.datetime to Unix timestamp."""
    return int(val.timestamp())

def convert_date(val):
    """Convert ISO 8601 date to datetime.date object."""
    return datetime.date.fromisoformat(val.decode("utf-8"))

def convert_datetime(val):
    """Convert ISO 8601 datetime to datetime.datetime object."""
    return datetime.datetime.fromisoformat(val.decode("utf-8"))

def convert_timestamp(val):
    """Convert Unix epoch timestamp to datetime.datetime object."""
    return datetime.datetime.fromtimestamp(int(val))

def register_sqlite3_adapters():
    sqlite3.register_adapter(datetime.date, adapt_date_iso)
    sqlite3.register_adapter(datetime.datetime, adapt_datetime_iso)
    sqlite3.register_adapter(datetime.datetime, adapt_datetime_epoch)

    sqlite3.register_converter("date", convert_date)
    sqlite3.register_converter("datetime", convert_datetime)
    sqlite3.register_converter("timestamp", convert_datetime)
