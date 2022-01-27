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

import email.message
import gzip
import html
import logging
import os
import pickle
import re
import sqlite3

from flask import abort, url_for

CRLF = "\r\n"

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

class Message(email.message.Message):
    "subclass to add as_html() method"
    content_headers = ("content-type", "content-transfer-encoding")
    app = None
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
                params = self.get_params()
                if params is not None:
                    for key, val in params[1:]:
                        ref.set_param(key, val)
            ref = f"<br>{sep}<br>{ref.as_html()}"
        else:
            ref = ""
            # force quoted text start a line
            main_msg = main_msg.replace("\n&gt;", "<br>\n&gt;")
            # what if the last paragraph is nothing but a quoted chunk?
            chunks = re.split(r"\n\s*\n+", main_msg)
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

    #pylint: disable=no-self-use
    def split_into_paras(self, body):
        "use multiple blank lines to indicate paragraphs"
        paras = "</p>\n<p>".join(re.split(r"\n\s*\n+", body))
        return f"<p>\n{paras}\n</p>\n"

    #pylint: disable=no-self-use
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

        parts = re.split(r"(\n\s*\n+)", body.rstrip())
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

    #pylint: disable=no-self-use
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
                for tgt_msgid in re.findall(r"<[^\s>]+>", val):
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
                self.replace_header(hdr, html.escape(val))


def read_message_string(raw):
    "construct Message from string."
    return email.message_from_string(raw, _class=Message)

def read_message(path):
    "read an email message from path, trying encodings"
    pckgz = os.path.splitext(path)[0] + ".pck.gz"
    if os.path.exists(pckgz):
        with gzip.open(pckgz, "rb") as pobj:
            return pickle.load(pobj)

    try:
        for encoding in ("utf-8", "latin-1"):
            with open(path, encoding=encoding) as fobj:
                try:
                    msg = read_message_string(fobj.read())
                except UnicodeDecodeError as exc:
                    exc_msg = str(exc)
                else:
                    # Cache message for future use - way faster than
                    # parsing the message from the .eml file.
                    with gzip.open(pckgz, "wb") as pobj:
                        pickle.dump(msg, pobj)
                    return msg
        raise UnicodeDecodeError(exc_msg)
    except FileNotFoundError:
        # pylint: disable=no-member
        logging.root.error("File not found: %s", path)
        abort(404)
        # keep pylint happy
        return path


PFX_MATCHER = re.compile(r"\[classicrendezvous\]|\[cr\]|re:|\s+", flags=re.I)
def trim_subject_prefix(subject):
    "Trim prefix detritus like [CR], Re:, etc"
    words = PFX_MATCHER.split(subject)
    return " ".join([word for word in words if word])

def init_app(app):
    if not app.config["DEBUG"]:
        ZAP_HEADERS.add("message-id")
    else:
        logging.root.setLevel("DEBUG")
    Message.app = app
