#!/usr/bin/env python

"Some functions to share between parts of the app"

# Other possible candidates for footer strippers
#
# Yahoo!
#
# http://localhost:8080/CR/2006/04/676
# http://localhost:8080/CR/2006/02/143
# http://localhost:8080/CR/2006/02/144
# http://localhost:8080/CR/2006/02/153
# http://localhost:8080/CR/2006/02/154
# http://localhost:8080/CR/2001/5/00019
# http://localhost:8080/CR/2006/02/156
#
# MSN
#
# http://localhost:8080/CR/2001/09/19
#
# AOL
#
# http://localhost:8080/CR/2008/06/12
#
# mail2web
#
# http://localhost:8080/CR/2006/4/659
#
# Virgin Media???
#
# https://localhost:8080/CR/2007/07/00004

import datetime
import email.message
import html
import re
import sys

import arrow
import dateutil.parser
from flask import abort

from . import app, FLASK_DEBUG

QUOTE_PAT = r'(?:(?:>\s?)*)?'

def strip_footers(payload):
    "strip non-content footers"
    while True:
        new_payload = payload
        for func in (strip_trailing_whitespace,
                     strip_cr_index_pwds,
                     strip_mime,
                     strip_bikelist_footer,
                     strip_juno,
                     strip_yp,
                     strip_msn,
                     strip_trailing_underscores):
            new_payload = func(new_payload)
        if new_payload == payload:
            return payload
        payload = new_payload

def strip_mime(payload):
    "strip the StripMime Report block."
    # The StripMime block looks like this:
    #
    # --- StripMime Report --...
    # multipart/alternative
    #   text/plain (text body -- kept)
    #   text/html
    # ---
    #

    # I am just stripping from the first line to the last and
    # sweeping away anything in the middle.

    header = "--- StripMime Report --"
    footer = "---"
    return strip_between(payload, header, footer, "mime")

def strip_bikelist_footer(payload):
    "strip the CR mailing list footer"
    # The footer looks like this:
    #
    # Classicrendezvous mailing list
    # Classicrendezvous@bikelist.org
    #  http://www.bikelist.org/mailman/listinfo/classicrendezvous

    header = "Classicrendezvous mailing list"
    footer = "http://www.bikelist.org/mailman/listinfo/classicrendezvous"
    return strip_between(payload, header, footer, "bikelist")

def strip_yp(payload):
    "strip Yellow Pages ads"
    header = "(?i).*get a jump"
    footer = "(?i).*yellowpages.(lycos|aol).com"
    return strip_between(payload, header, footer, "yp")

def strip_juno(payload):
    "strip Juno ads"
    header = "_" * 60
    footer = "https?://.*juno.com"
    return strip_between(payload, header, footer, "juno")

def strip_msn(payload):
    "a bit looser, hopefully doesn't zap actual content"
    header = ".* MSN"
    footer = ".*https?:.*msn.com"
    return strip_between(payload, header, footer, "msn")

def strip_cr_index_pwds(payload):
    "this occurs on occasion. Strip to remove passwords."
    header = "Passwords for classicrendezvous-index@catfood.phred.org"
    footer = ".*index%40catfood.phred.org"
    return strip_between(payload, header, footer, "passwords")

# pylint: disable=unused-argument
def strip_between(payload, header, footer, tag):
    "strip all lines at the end of the strip between header and footer"
    lines = re.split(r"(\n+)", payload)
    state = "start"
    new_payload = []
    # print(tag, repr(header), repr(footer))
    for line in lines:
        if state == "start":
            if re.match(f"{QUOTE_PAT}{header}", line) is not None:
                state = "stripping"
                # print(">> elide", tag, state, repr(line))
                continue
            new_payload.append(line)
        else:  # state == "stripping"
            # print(">> elide", tag, state, repr(line))
            if re.match(f"{QUOTE_PAT}{footer}", line) is not None:
                state = "start"
    new_payload = "".join(new_payload)
    # print(">> result:", tag, "unchanged" if new_payload == payload else "stripped")
    return new_payload

def strip_trailing_underscores(payload):
    "strip trailing underscores at the bottom of the message"
    # Looks like 47 underscores in the most common case.
    underscores = "_{35,50}"
    hyphens = "-{35,45}"
    # Juno dumps some cruft at the end of its URL which seems to be
    # separated from the rest of the URL by a newline. I treat it like
    # a trailing dashed line.
    juno_dashes = "[0-9A-Za-z]+/$"
    dashed_line = f"(?:{hyphens}|{underscores}|{juno_dashes})"
    lines = re.split(r"(\n+)", payload.rstrip())
    if re.match(f"{QUOTE_PAT}{dashed_line}", lines[-1]) is not None:
        lines = lines[:-1]
    lines = "".join(lines)
    # print(">> result:", "underscores", lines == payload)
    return lines

def strip_trailing_whitespace(payload):
    "strip trailing whitespace at the bottom of the message"
    if not payload:
        return ""
    lines = re.split(r"(\n+)", payload)
    pat = f"{QUOTE_PAT}" + r"\s*$"
    # print(">> lines[-1]:", pat, repr(lines[-1]),
    #       re.match(pat, lines[-1]))
    while lines and re.match(pat, lines[-1]) is not None:
        # print(">> del:", repr(lines[-1]))
        del lines[-1]
    lines = "".join(lines)
    # print(">> result:", "whitespace", lines == payload)
    return lines

def convert_ts_bytes(stamp):
    "SQLite3 converter for tz-aware datetime objects"
    stamp = stamp.decode("utf-8")
    return datetime.datetime.fromisoformat(stamp)

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
        timestamp = dateutil.parser.parse(timestring, tzinfos=TZINFOS)
    except dateutil.parser.ParserError:
        # try arrow with its format capability
        try:
            timestamp = arrow.get(timestring, ARROW_FORMATS).datetime
        except arrow.parser.ParserError as exc:
            raise dateutil.parser.ParserError(str(exc))
    return timestamp

class Message(email.message.Message):
    "subclass to add as_html() method"
    content_headers = ("content-type", "content-transfer-encoding")
    def as_html(self):
        "return string in HTML form"

        if self.get_content_type() == "text/plain":
            headers = "<br>\n".join(f"{key}: {val}" for (key, val) in self.items())
            # zap "content-type and content-transfer-encoding" if we aren't debugging
            if not FLASK_DEBUG:
                headers = "\n".join([hdr for hdr in headers.split("\n")
                                           if hdr.split(":")[0].lower() not in self.content_headers])
            body = self.get_payload(decode=True).decode(self.get_content_charset())
            body = self.body_to_html(body)
            return f"{headers}<br>\n<br>\n{body}\n"

        if self.get_content_type() == "text/html":
            return self.as_string()

        if self.get_content_maintype() == "multipart":
            html = []
            for part in self.walk():
                html.append(part.as_html())
            return "".join(html)

        raise ValueError(f"Unrecognized content type: {self.get_content_type()}")

    def body_to_html(self, body):
        "the basics..."

        # Text message bodies consist of one or three parts:
        #
        # 1. author's message
        # 2. --- message separator ---
        # 3. message being replied to (which likely includes some
        #    headers).
        #
        # Parts 2 and 3 are optional, so the structure looks like:
        #
        # part 1 [ part 2 part 3 ]
        #
        # Accordingly, we try to split at the boundary,
        # and recurse if that succeeds.
        #
        # The author's message consists of the message proper,
        # possibly ending with a signature.  that signature can be
        # variable in structure.  BITD, sigs generally started with
        # "--" on a separate line.  That's not always true anymore,
        # however. We recognize two other styles of signatures:
        #
        # * a small number (2 to 4) of short lines (fewer than 50 chars)
        # * a small number of indented lines
        #
        # As should be obvious, these are overlapping heuristics.  I
        # imagine that as time goes on I will encounter other styles
        # which I will try to accommodate.

        # special case - appended original message
        appended = re.split("\n(--+ .* wrote:|--+ original message --+) *\n", body,
                            flags=re.I, maxsplit=1)
        main_msg = appended[0]
        main_msg = self.make_urls_sensitive(html.escape(main_msg))

        if len(appended) == 3:
            sep, ref = appended[1:]
            ref = read_message_string(ref)

            # the reference message might well be incomplete. if it
            # lacks a charset, override the various content-type
            # parameters (but not the content-type itself for now)
            # from the parent message.
            if ref.get_charset() is None:
                for key, val in self.get_params()[1:]:
                    ref.set_param(key, val)
            ref = f"<br>{sep}<br>{ref.as_html()}"
        else:
            ref = ""
            # force quoted text start a line
            main_msg = main_msg.replace("\n&gt;", "<br>\n&gt;")
            # what if the last paragraph is nothing but a quoted chunk?
            chunks = re.split("\n\s*\n+", main_msg)
            is_quote = True
            term = "\n"
            last_chunk = chunks[-1].split(term)
            for line in last_chunk:
                is_quote = is_quote and line[:4] == "&gt;"
                if not is_quote:
                    break
            if is_quote:
                term = "<br>\n"
            chunks[-1] = term.join(last_chunk)
            main_msg = "\n\n".join(chunks)
            main_msg = self.split_into_paras(self.handle_sig(main_msg))

        return f"{main_msg}{ref}"

    def split_into_paras(self, body):
        "use multiple blank lines to indicate paragraphs"
        paras = "</p>\n<p>".join(re.split("\n\s*\n+", body))
        return f"<p>\n{paras}\n</p>\n"

    def handle_sig(self, body):
        "preserve formatting (approximately) of any trailing e-sig."

        # last para might be a signature. Clues:
        #
        # * leading dashes
        # * 2-4 short lines (< 55 chars)

        # Here's a message with a sig I don't handle:
        #
        # http://localhost:8080/CR/2009/03/134
        #
        # It's only got a few short lines, but it's not separated from
        # the message body by white space or a dashed line.

        parts = re.split("(\n\s*\n+)", body.rstrip())
        sig = parts[-1].split("\n")
        if (sig and
            # starts with leadding dashes
            (sig[0].startswith("--") or
             # or only two to four short lines
             max(len(s) for s in sig) < 55 and
             2 <= len(sig) <= 4)):
            parts[-1] = "<br>".join(sig)
        else:
            # what about an indented style? last couple lines might look like:
            #
            # blah blah blah Masi blah blah blah.
            #     Homer Jones
            #     Timbuktu, Mali
            chunks = re.split(r"(\n\s+)", parts[-1])
            # convert whitespace to unbreakable spaces and force line break.
            for (i, chunk) in enumerate(chunks):
                if i % 2:
                    chunks[i] = "<br>\n" + "&nbsp;" * (len(chunk) - 1)
            parts[-1] = "\n".join(chunks)
        return "".join(parts)

    def make_urls_sensitive(self, text):
        "<a>-ify words which look like urls (just https? or leading www)."
        new_text = []
        for word in re.split(r"(\s+)", text):
            if re.match("https?://", word):
                new_text.append(f"""<a target="_blank" href="{word}">{word}</a>""")
            elif re.match("www[.]", word):
                # assume website, HTTPS Everywhere or similar will map to https
                new_text.append(f"""<a target="_blank" href="http://{word}">{word}</a>""")
            else:
                new_text.append(word)
        return "".join(new_text)


def read_message_string(raw):
    "construct Message from string."
    return email.message_from_string(raw, _class=Message)

def read_message(path):
    "read an email message from path, trying encodings"
    try:
        for encoding in ("utf-8", "latin-1"):
            with open(path, encoding=encoding) as fobj:
                try:
                    return read_message_string(fobj.read())
                except UnicodeDecodeError as exc:
                    exc_msg = str(exc)
                else:
                    break
        else:
            raise UnicodeDecodeError(exc_msg)
    except FileNotFoundError:
        app.logger.error("File not found: %s", path)
        abort(404)
        # keep pylint happy
        return path
