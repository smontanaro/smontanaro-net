#!/usr/bin/env python

"Some functions to share between parts of the app"

import csv
import datetime
import email.message
import gzip
import html
import logging
import os
import pickle
import re
import sqlite3
import statistics
import sys
import urllib.parse

from flask import url_for

ZAP_HEADERS = {
    "content-disposition",
    "content-language",
    "delivered-to",
    "dkim-signature",
    "domainkey-signature",
    "errors-to",
    "importance",
    "mime-version",
    "precedence",
    "priority",
    "received",
    "received-spf",
    "reply-to",
    "return-path",
    "sender",
    "user-agent",
    }

EOL_SEP = r"\r?\n"
PARA_SEP = fr"{EOL_SEP}\s*(?:{EOL_SEP})+"
INDENTED_SEP = fr"({EOL_SEP}\s+)"

class Message(email.message.Message):
    "subclass to add as_html() method"
    content_headers = ("content-type", "content-transfer-encoding")
    app = None
    urlmap = {}
    urlmaptime = datetime.datetime.fromtimestamp(0)

    def as_html(self):
        "return string in HTML form"

        if self.get_content_type() == "text/plain":
            headers = "<br>\n".join(f"{key}: {val}"
                                      for (key, val) in self.items())
            # zap "content-type and content-transfer-encoding" if we
            # aren't debugging
            if not self.app.config["DEBUG"]:
                headers = "\n".join([hdr for hdr in headers.split("\n")
                                           if hdr.split(":")[0].lower()
                                              not in self.content_headers])
            body = self.decode(self.get_payload(decode=True))
            body = self.body_to_html(body)
            return f"{headers}<br>\n<br>\n{body}\n"

        if self.get_content_type() == "text/html":
            return self.as_string()

        if self.get_content_maintype() == "multipart":
            rendered_html = []
            for part in self.walk():
                if part == self:
                    continue
                rendered_html.append(part.as_html())
            return "".join(rendered_html)

        if self.get_content_maintype() == "image":
            # pylint: disable=no-member
            logging.warning("Can't render images")
            return ('''<br><br><div style="font-size: 16pt ; font-weight: bold">'''
                    '''Image elided - can't yet render images</div>''')

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
        # * a small number of short lines at the end of the last paragraph
        #
        # As should be obvious, these are overlapping heuristics.  I
        # imagine that as time goes on I will encounter other styles
        # which I will try to accommodate.

        # special case - appended original message
        appended = re.split(f"{EOL_SEP}(--+ .* wrote:|--+ original message --+) *{EOL_SEP}",
                            body, flags=re.I, maxsplit=1)
        if len(appended) == 1:
            ref = ""
        else:
            sep, ref = appended[1:]
            ref = read_message_string(ref)

            # the reference message might well be incomplete. if it
            # lacks a charset, override the various content-type
            # parameters (but not the content-type itself for now)
            # from the parent message.
            if ref.get_charset() is None:
                params = self.get_params()
                if params is not None:
                    for key, val in params[1:]:
                        ref.set_param(key, val)
            ref = f"<br>\n{sep}<br>\n{ref.as_html()}"

        main_msg = self.make_urls_sensitive(html.escape(appended[0]))
        # force quoted text to start a line
        main_msg = re.sub(fr"({EOL_SEP})&gt;", r"<br>\1&gt;", main_msg)
        # what if the last paragraph is nothing but a quoted chunk?
        chunks = re.split(PARA_SEP, main_msg)
        is_quote = True
        last_chunk = re.split(EOL_SEP, chunks[-1])
        for line in last_chunk:
            is_quote = is_quote and line[:4] == "&gt;"
            if not is_quote:
                break
        if is_quote:
            chunks[-1] = fr"<br>{EOL_SEP}".join(last_chunk)

        main_msg = self.handle_sig("\n\n".join(chunks))
        main_msg = "<p>\n" + "</p>\n<p>".join(re.split(PARA_SEP, main_msg)) + "\n</p>\n"

        return f"{main_msg}{ref}"

    def handle_sig(self, body):
        "preserve formatting (approximately) of any trailing e-sig."

        # last para might be a signature. Clues:
        #
        # * leading dashes
        # * 2-4 short lines (< 55 chars)

        # Here are a couple messages with a sig I don't handle:
        #
        # One:
        #
        # http://localhost:8080/CR/2009/03/0134
        #
        # It's only got a few short lines, but it's not separated from
        # the message body by white space or a dashed line.
        #
        # Another:
        #
        # http://localhost:8080/CR/2010/07/0144
        #
        # It has a longer paragraph than the first and is likely
        # easier to discriminate between the paragraph proper and the
        # signature.

        parts = re.split(PARA_SEP, body.rstrip())
        sig = re.split(EOL_SEP, parts[-1])
        if (sig and
            # starts with leading dashes
            (sig[0].startswith("--") or
             # or only two to four short lines
             max(len(s) for s in sig) < 40 and
             2 <= len(sig) <= 4)):
            # eprint("entire paragraph is sig")
            parts[-1] = "<br>".join(sig)
        else:
            # what about an indented style? last couple lines might look like:
            #
            # blah blah blah Masi blah blah blah.
            #     Homer Jones
            #     Timbuktu, Mali
            chunks = re.split(INDENTED_SEP, parts[-1])
            if len(chunks) > 1:
                # eprint(chunks)
                # convert whitespace to unbreakable spaces and force line break.
                for (i, chunk) in enumerate(chunks):
                    if i % 2:
                        chunks[i] = "<br>\n" + "&nbsp;" * (len(chunk) - 1)
                parts[-1] = "\n".join(chunks)
                # eprint("last lines of paragraph are indented sig")
            else:
                # what about a non-indented style?
                # eprint("last lines of paragraph are non-indented sig")
                parts[-1] = self.maybe_format_sig(parts[-1])
        return "\n\n".join(parts)

    #pylint: disable=no-self-use
    def maybe_format_sig(self, para):
        "try and format signature smashed into the end of the paragraph"
        lines = re.split(EOL_SEP, para)
        lengths = [len(line) for line in lines]
        # eprint(tuple(zip(lengths, lines)))
        for i in range(min(5, len(lines) - 1), 1, -1):
            # sigs tend to be two to four short lines. once the mean
            # of the last few lines drops below 10 while the mean of
            # the remaining lines remains above 40, treat those last
            # few lines as the sig.

            # eprint(i, statistics.mean(lengths[-i:]), statistics.mean(lengths[:-i]))
            if (statistics.mean(lengths[-i:]) < 15 and
                statistics.mean(lengths[:-i]) > 40):
                # eprint("found our sig!")
                # eprint(lines[-i:])
                break
        else:
            # nothing to see here folks...
            return para

        lines[-i:] = ["<br>" + line for line in lines[-i:]]
        return "\n".join(lines)

    @classmethod
    def initialize_urlmap(cls):
        "make sure urlmap is populated"
        mapfile = os.path.join(cls.app.config["CRDIR"], "urlmap.csv")
        stamp = os.path.getmtime(mapfile)
        urlmap = cls.urlmap
        if urlmap and stamp < cls.urlmaptime:
            return
        cls.urlmaptime = stamp
        with open(mapfile) as fobj:
            rdr = csv.DictReader(fobj)
            for row in rdr:
                # eprint("urlmap:", row["old"], "->", row["new"])
                urlmap[row["old"]] = row["new"]

    def map_url_prefix(self, url):
        "try ever-shrinking prefixes of url in the map"
        # this is called after html escape.  restore url in case it
        # has special characters
        url = html.unescape(url)
        parts = urllib.parse.urlparse(url)
        # we don't want fragment or params.
        parts = parts._replace(fragment="", params="")
        # if the URL lacks a path, make it "/" so we traverse the
        # while loop once.
        if not parts.path:
            parts = parts._replace(path="/")
        while parts.path >= "/" or parts.query != "":
            prefix = urllib.parse.urlunparse(parts)
            # eprint("try:", prefix)
            if (target := self.urlmap.get(prefix)) is not None:
                # eprint(">>", url, "->", target)
                # now we have to re-escape...
                return html.escape(target)

            # zero out query before shortening path
            if parts.query:
                parts = parts._replace(query="")
            else:
                path = "/".join(parts.path.split("/")[:-1])
                parts = parts._replace(path=path)
        # no mapping for this bad boy...
        # eprint(">> no mapping found for", url)
        return html.escape(url)

    def map_url(self, word):
        "map a single word, possibly returning an <a...> construct"
        if re.search("https?://|www[.]", word) is None:
            return word

        if word[0:4] == "&lt;" and word[-4:] == "&gt;":
            # discard surrounding <...>. i think that notion came from
            # the olden days. not sure why it was needed though.
            word = word[4:-4]

        if re.match("www[.]", word):
            word = f"http://{word}"

        # wool jersey used ".../gallery/v/..." and ".../gallery/..." - remove the "v"
        word = word.replace("/gallery/v/", "/gallery/")

        target = self.map_url_prefix(word)
        mapped = "&nbsp;(mapped)" if target != word else ""
        if re.match("https?://", word):
            word = f"""<a target="_blank" href="{target}">{word}</a>{mapped}"""
        return word

    def make_urls_sensitive(self, text):
        """
        <a>-ify words which look like urls (just https? or leading www).
        Also map defunct URLs to current ones where known.
        """

        new_text = []
        self.initialize_urlmap()
        for word in re.split(r"(\s+)", text):
            new_text.append(self.map_url(word))
        return "".join(new_text)

    def decode(self, payload):
        "decode payload, trying a couple different fallback encodings..."
        for charset in (self.get_content_charset("us-ascii"), "utf-8", "latin-1"):
            try:
                return payload.decode(charset)
            except (LookupError, UnicodeDecodeError) as exc:
                last_exc = exc
        raise last_exc

    def filter_headers(self):
        "generate self header block"
        conn = sqlite3.connect(self.app.config["REFDB"])
        cur = conn.cursor()
        last_refs = set()
        for (hdr, val) in self.items():
            # Skip various headers - maybe later insert as comments...
            hdr = hdr.lower()
            if (hdr in ZAP_HEADERS or
                hdr[:2] == "x-" or
                hdr[:5] == "list-"):
                del self[hdr]
                continue
            if hdr in ("in-reply-to", "references"):
                tags = []
                for tgt_msgid in re.findall(r"<[^>]+>", val):
                    x = clean_msgid(tgt_msgid)
                    if x != tgt_msgid:
                        logging.root.warning("Message-ID found to contain whitespace! %s",
                                             tgt_msgid)
                        tgt_msgid = x

                    if tgt_msgid in last_refs:
                        continue
                    last_refs |= set([tgt_msgid])
                    cur.execute("select year, month, seq from messages"
                                "  where messageid = ?",
                                (tgt_msgid,))
                    try:
                        (year, month, seq) = cur.fetchone()
                    except (TypeError, IndexError):
                        # the occasional message-id isn't in the archive. That's ok.
                        # pylint: disable=no-member
                        tag = html.escape(tgt_msgid)
                    else:
                        url = url_for('cr_message', year=year,
                                      month=month, seq=seq)
                        tag = f"""<a href="{url}">{html.escape(tgt_msgid)}</a>"""
                    tags.append(tag)
                if tags:
                    self.replace_header(hdr, f"{' '.join(tags)}")
            elif hdr == "content-type":
                pass                # preserve as-is for later calcuations
            else:
                self.replace_header(hdr, html.escape(str(val)))


def read_message_string(raw):
    "construct Message from string."
    return email.message_from_string(raw, _class=Message)

def read_message_bytes(raw):
    "construct Message from byte string."
    msg = email.message_from_bytes(raw, _class=Message)
    payload = msg.get_payload(decode=True)
    if (isinstance(payload, bytes) and
        b"=0A" in payload and
        "Content-Transfer-Encoding" not in msg):
        msg["Content-Transfer-Encoding"] = "quoted-printable"
        assert b"=0A" not in msg.get_payload(decode=True)
    return msg

def read_message(path):
    "read an email message from path, trying encodings"
    pckgz = os.path.splitext(path)[0] + ".pck.gz"
    if (os.path.exists(pckgz) and
        os.path.getmtime(pckgz) > os.path.getmtime(path)):
        with gzip.open(pckgz, "rb") as pobj:
            return pickle.load(pobj)

    with open(path, "rb") as fobj:
        msg = read_message_bytes(fobj.read())
        # Cache message for future use - way faster than
        # parsing the message from the .eml file.
        with gzip.open(pckgz, "wb") as pobj:
            pickle.dump(msg, pobj)
        return msg

def eprint(*args, file=sys.stderr, **kwds):
    print(*args, file=file, **kwds)

PFX_MATCHER = re.compile(r"\[classicrendezvous\]"
                         r"|\[cr\]"
                         r"|re\[[0-9]\]:"
                         r"|re[-:]"
                         r"|\s+", flags=re.I)
def trim_subject_prefix(subject):
    "Trim prefix detritus like [CR], Re:, etc"
    words = PFX_MATCHER.split(str(subject))
    return " ".join([word for word in words if word])

def clean_msgid(msgid):
    "Sometimes message ids contain whitespace"
    return re.sub(r"\s+", "", msgid)

def get_topic(topic, conn):
    return conn.execute("""
      select m.year, m.month, m.seq, m.subject, m.sender from
        topics t join messages m
          on t.messageid = m.messageid
        where t.topic like ?
        order by m.year, m.month, m.seq
    """, (topic,)).fetchall()

def make_topic_hierarchy(topics, htopics, prefix):
    """construct hierarchical topic structure from list of colon-delimited topics.

       for example:

       ["Production Builders:LeJeune", "Production Builders:Peugeot:PX-10LE"]

       would produce this category structure:

           Production Builders
               LeJeune
               Peugeot
                   PX-10LE

       at each level, individual messages could be referenced.
    """

    for tlist in topics:
        if not tlist:
            return
        topic, rest = tlist[0], tlist[1:]
        topic_pfx = ":".join([prefix, topic]).lstrip(":")
        key = topic
        if key not in htopics:
            htopics[key] = [topic_pfx, {}]
        make_topic_hierarchy([rest], htopics[key][1], topic_pfx)

def init_app(app):
    if not app.config["DEBUG"]:
        ZAP_HEADERS.add("message-id")
    else:
        logging.root.setLevel("DEBUG")
    Message.app = app
