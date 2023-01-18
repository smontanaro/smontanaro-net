#!/usr/bin/env python

"Some functions to share between parts of the app"

import csv
from dataclasses import dataclass, field as dataclass_field
import datetime
import email.message
import email.policy
import gzip
import html
import logging
import os
import pickle                   # nosec
import statistics
import string
import typing
import urllib.parse

from flask import url_for, current_app
import html2text
import regex as re

# from .log import eprint
from .refdb import ensure_db
from .srchdb import ensure_search_db, have_term
from .strip import strip_footers

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

# Match sender of an email (crude)
ADDR_PAT = re.compile(r'''(?:\s*<?([^ >]+@[^ >]*)>?)''')          # email only
NAME_PAT = re.compile(r'''([^@]+)$''')                            # name only
NAME_ANGLED_PAT = re.compile(r'''"?([^"@<[]*)"?'''                # name <email>
                             r'''(?:\s*[[<]?(?:mailto:)?([^] >]+@[^] >]*)[]>]?)''')
EMAIL_PAREN_PAT = re.compile(r'''(?:\s*<?([^ >]+@[^ >]*)>?)'''    # email (name)
                             r'''\s*\(([^"@<)]*)\)''')
WHITESPACE_PAT = re.compile(r'\s')

CRLF = "\r\n"


# words which appear in one or more dictionaries which really aren't words.
EXCEPTIONS = {
    "throu",
    "iwa",
    "iwaiwa",
}
# /usr/share/dict/words (at least) has all single letters as "words". While
# this might be useful in some contexts, it's clearly not helpful when trying
# to smash separated words back together.  Toss all of them except "a" and "i".
_one_letter = set(string.ascii_uppercase) | set(string.ascii_lowercase)
for _ai in "aAiI":
    _one_letter.discard(_ai)
EXCEPTIONS |= _one_letter

def all_words(keep_odd=False):
    dictionaries = [
        "/usr/share/dict/american-english-large",
        "/usr/share/dict/american-english",
        "/usr/share/dict/words",
    ]
    for word_file in dictionaries:
        if os.path.exists(word_file):
            words = read_words(word_file, keep_odd)
            words -= EXCEPTIONS
            return words

    raise ValueError("no dictionary found")


def read_words(word_file, keep_odd=False):
    punctset = set(re.sub("[-_]", "", string.punctuation))
    words = set()
    with open(word_file, "r", encoding="utf-8") as wf:
        for word in wf:
            if not keep_odd and (len(word) < 4 or
                                 word[0] in string.ascii_uppercase or
                                 set(word) & punctset):
                continue
            words.add(word.lower().strip())
    return words


def parse_from(from_):
    "Parse content of the from_ header into name and email"
    if (mat := EMAIL_PAREN_PAT.match(from_)) is not None:
        name = mat.group(2).strip()
        addr = mat.group(1).strip()
    elif (WHITESPACE_PAT.match(from_) is None and
          (mat := ADDR_PAT.match(from_)) is not None):
        name = ""
        addr = mat.group(1).strip()
    elif mat := NAME_PAT.match(from_):
        name = mat.group(1).strip()
        addr = ""
    else:
        mat = NAME_ANGLED_PAT.match(from_)
        if mat is None:
            name = addr = ""
        else:
            name = mat.group(1).strip()
            addr = mat.group(2).strip()
    return (name, addr)


class Message(email.message.EmailMessage):
    "subclass to add as_html() method"
    content_headers = ("content-type", "content-transfer-encoding")
    app = None
    urlmap: typing.Dict[str, str] = {}
    urlmaptime = datetime.datetime.fromtimestamp(0)

    def as_html(self):
        "return string in HTML form"

        if self.get_content_type() == "text/plain":
            headers = []
            for (key, val) in self.items():
                if key[0:2].lower() == "x-":
                    continue
                if self[f"x-html-{key}"] is not None:
                    newval = self[f"x-html-{key}"]
                    headers.append(f"{key}: {newval}")
                else:
                    headers.append(f"{key}: {val}")
            headers = "<br>\n".join(headers)
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

        # Some other problematic display/formatting:
        #
        # inconsistent indentation of quoted block
        #   http://localhost:8080/CR/2008/09/0798
        #
        # unhandled main/quoted message separator
        #   http://localhost:8080/CR/2006/06/1085
        #
        # signature block not at end of message
        #   http://localhost:8080/CR/2004/01/0415
        #
        # larger-than-expected signature block
        #   http://localhost:8080/CR/2008/10/1121
        #
        # --- Original Message --- is indented
        #   http://localhost:8080/CR/2008/03/0505
        #
        # signature block not at end of message
        #   http://localhost:8080/CR/2008/03/0238
        #
        # atypical message quoting
        #   http://localhost:8080/CR/2002/09/0610
        #
        # unseparated quote after body
        #   http://localhost:8080/CR/2000/11/1034

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
        # * a few short lines (< 45 chars, unless it looks like an
        #   HTMLified web page reference)

        parts = re.split(PARA_SEP, body.rstrip())
        sig = re.split(EOL_SEP, parts[-1])
        if (sig and
            # starts with leading dashes
            (sig[0].startswith("--") or
             # or only a few short lines (other than URL links)
             2 <= len(sig) <= 10 and
             max([0] + [len(s) for s in sig if "<a target=" not in s]) < 45)):
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

    def extract_text(self):
        "recursively extract text bits of message payload"
        body_parts = []
        hier = self.get_hierarchy()
        content_type = hier.content_type
        if content_type == "text/plain":
            payload = self.decode(self.get_payload(decode=True))
            payload = strip_footers(payload)
            body_parts.append(patch_word_breaks(payload))
        elif content_type in ("multipart/mixed", "multipart/related"):
            for kid_hier in hier.children:
                body_parts.append(kid_hier.me.extract_text())
        elif content_type == "multipart/alternative":
            types = hier.child_types()
            if "text/plain" in types:
                desired = "text/plain"
            elif "text/html" in types:
                desired = "text/html"
            else:
                desired = None
            for kid_hier in hier.children:
                if kid_hier.content_type == desired:
                    body_parts.append(kid_hier.me.extract_text())
                    break
        elif content_type == "text/html":
            # This will return Markdown, not quite what we want
            text_maker = html2text.HTML2Text()
            text_maker.ignore_links = True
            payload = self.decode(self.get_payload(decode=True))
            payload = text_maker.handle(payload)
            payload = strip_footers(payload)
            body_parts.append(payload)
        elif self.get_content_maintype() == "image":
            pass
        else:
            logging.warning("Unrecognized content type: %s", content_type)
        return "\n\n".join(body_parts)


    @classmethod
    def initialize_urlmap(cls):
        "make sure urlmap is populated"
        mapfile = os.path.join(cls.app.config["CRDIR"], "urlmap.csv")
        stamp = os.path.getmtime(mapfile)
        urlmap = cls.urlmap
        if urlmap and stamp < cls.urlmaptime:
            return
        cls.urlmaptime = stamp
        with open(mapfile, encoding="utf-8") as fobj:
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
            # provide hints for optional breaking of long URLs.
            split = (urllib.parse.urlsplit(word))
            split = split._replace(path=split.path.replace("/", "/<wbr>"))
            word = f"""<a target="_blank" href="{target}">{split.geturl()}</a>{mapped}"""
        return word

    def make_urls_sensitive(self, text):
        r"""
        Make a few URL-related transformations:

        * map r"_URL_\s+(URL)" pattern to just "URL".
        * <a>-ify words which look like urls (just https? or leading www).
        * map defunct URLs to current ones where known.
        """

        new_text = []
        self.initialize_urlmap()
        text = re.sub(r'_(https?:.*)_\s+[(]\1[)]', r'\1', text)
        for word in re.split(r"(\s+)", text):
            new_text.append(self.map_url(word))
        return "".join(new_text)

    def get_hierarchy(self, indent=0, seen=None):
        "return nested hierarchy of (self, content-type, children) pairs."
        # children is a (possibly empty) list.
        if seen is None:
            seen = set()
        seen.add(self)

        content_type = f"{self.get_content_maintype()}/{self.get_content_subtype()}"
        me = MessageHierarchy(self, content_type)
        # eprint("  "*indent, hex(id(self)), me.content_type)
        if self.get_content_maintype() == "multipart":
            for part in self.walk():
                if part not in seen:
                    me.children.append(part.get_hierarchy(indent+1,
                                                          seen))
        # kid_types = me.child_types()
        # if kid_types:
        #     eprint("  "*indent, hex(id(self)), kid_types)
        return me

    def decode(self, payload):
        "decode payload, trying a couple different fallback encodings..."
        for charset in (self.get_content_charset("ascii"),  "latin-1", "utf-8"):
            try:
                return payload.decode(charset)
            except (LookupError, UnicodeDecodeError) as exc:
                last_exc = exc
        raise last_exc

    def filter_headers(self):
        "generate self header block"
        conn = ensure_db(self.app.config["REFDB"])
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
            elif hdr == "from":
                # Create a link for searching other posts by the same user.
                (sender, addr) = parse_from(val)
                self["x-html-from"] = generate_from_html(sender, addr)
            else:
                self.replace_header(hdr, html.escape(str(val)))


@dataclass
class MessageHierarchy:
    "represent a message and its children"
    me: Message
    content_type: str
    children: list = dataclass_field(default_factory=list)

    def child_types(self):
        return [kid.content_type for kid in self.children]

DICT_WORDS = all_words(keep_odd=True)
def patch_word_breaks(text):
    "reconstruct words which cross CRLF boundaries"
    # see CR/2005-07/eml-files/classicrendezvous.10507.0921.eml, where we
    # find this:
    #   ...snapped throuCRLFgh the middle...

    # The symptom is that we have a non-word (or uncommon word, more blow),
    # CRLF, then possibly another non-word. If we smush them together then wind
    # up with an actual word, perhaps we should delete the CRLF.

    # I'm not entirely sure why this happened, but it's in the raw email
    # messages.  In the above example, it's in poorly formatted quoted
    # material.

    # Despite my best intentions, /usr/share/dict/words on my Mac thinks
    # "throu" is a word. I can't find an online definition for it, however, and
    # on my web server, /usr/share/dict/american-english-large doesn't have it.
    # Maybe it's an archaic British spelling of "through." So, perhaps that
    # isn't the best test case. :-/

    punctset = set(re.sub("[-_]", "", string.punctuation))
    # We are willing to skip over multiple spaces, but it seems the CRLF breaks
    # between words are only single line breaks.
    splits = re.split(f"( +|{CRLF})", text)
    indexes = list(range(len(splits)))
    del_crlf = []
    for (off1, off2, off3) in zip(indexes[0:], indexes[1:], indexes[2:]):
        frag1 = splits[off1]
        frag2 = splits[off2]
        frag3 = splits[off3]
        if not frag3 or frag2 != CRLF:
            continue
        if frag3[-1] in punctset:
            # period or comma most likely
            frag3 = frag3[:-1]
        if not frag1 or not frag3:
            continue
        if frag1.lower() in DICT_WORDS:
            continue
        word = (frag1+frag3).lower()
        if word in DICT_WORDS or word[-1] == "s" and word[:-1] in DICT_WORDS:
            # eprint((off1, frag1, frag2, frag3, frag1+frag3))
            del_crlf.append(off2)
    for offset in reversed(del_crlf):
        del splits[offset]
    return "".join(splits)


def generate_from_html(sender, addr):
    "Create links for sender name and email address"
    conn = ensure_search_db(current_app.config["SRCHDB"])
    cur = conn.cursor()
    have_sender = have_term(f"from:{sender.lower()}", cur)
    have_addr = have_term(f"from:{addr.lower()}", cur)
    if have_sender:
        name = urllib.parse.quote_plus(sender)
        sender = html.escape(sender)
        sender = f'"<a href="/CR/query?query=from:{name}">{sender}</a>"'
    else:
        sender = html.escape(sender)
    if have_addr:
        mail = urllib.parse.quote_plus(addr)
        addr = html.escape(addr)
        addr = f'&lt;<a href="/CR/query?query=from:{mail}">{addr}</a>&gt;'
    else:
        addr = html.escape(addr)
    return f"{sender} {addr}"

def read_message_string(raw):
    "construct Message from string."
    return email.message_from_string(raw, _class=Message,
                                     policy=email.policy.default)

def read_message_bytes(raw):
    "construct Message from byte string."
    msg = email.message_from_bytes(raw, _class=Message,
                                   policy=email.policy.default)
    payload = msg.get_payload(decode=True)
    if (isinstance(payload, bytes) and
        b"=0A" in payload and
        "Content-Transfer-Encoding" not in msg):
        msg["Content-Transfer-Encoding"] = "quoted-printable"
        assert b"=0A" not in msg.get_payload(decode=True) # nosec
    return msg

def read_message(path):
    "read an email message from path, trying encodings"
    pckgz = os.path.splitext(path)[0] + ".pck.gz"
    msg = None
    if (os.path.exists(pckgz) and
        os.path.getmtime(pckgz) > os.path.getmtime(path)):
        with gzip.open(pckgz, "rb") as pobj:
            try:
                msg = pickle.load(pobj) # nosec
            except (EOFError, pickle.UnpicklingError):
                # corrupt pickle file I guess
                pass

    if msg is None:
        with open(path, "rb") as fobj:
            msg = read_message_bytes(fobj.read())
            # Cache message for future use - way faster than
            # parsing the message from the .eml file.
            with gzip.open(pckgz, "wb") as pobj:
                pickle.dump(msg, pobj, protocol=pickle.HIGHEST_PROTOCOL)

    # This looks so horrid, I will actually fix it here:
    #
    #   Subject: {ClassicRend]Danger, items for sale
    title = re.sub(r"{ClassicRend]\s*", "[CR] ", str(msg["Subject"]))
    msg.replace_header("Subject", title)

    return msg

PFX_MATCHER = re.compile(r"\[classicrendezvous\]"
                         r"|\[cr\]"
                         r"|cr:"
                         r"|re\[[0-9]\]:"
                         r"|re[-:]"
                         r"|fs:"
                         r"|aw:"
                         r"|\s+", flags=re.I)
def trim_subject_prefix(subject):
    "Trim prefix detritus like [CR], Re:, FS:, etc"
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

def get_message_bits(messageid, conn):
    return conn.execute("""
      select distinct year, month, seq
        from messages
        where messageid = ?
        order by year, month, seq
    """, (messageid,)).fetchall()

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


def generate_link(r):
    "HTML for a single message"
    root = "" # "(T)&nbsp;" if r['is_root'] else ""
    sub = re.sub(r"\s+", " ", r["Subject"])
    sender = generate_from_html(*parse_from(r["sender"]))

    return (f'''<a name="{r['seq']:04d}">'''
            f'''{root}'''
            f'''<a href="/CR/{r['year']}/{r['month']:02d}/{r['seq']:04d}">'''
            f'''{html.escape(sub)}</a></a>'''
            f''' {sender}''')


def open_(f, mode="r", encoding="utf-8"):
    "use ext to decide if we should compress"
    # TODO: Catch use of binary mode with non-empty encoding.
    if f.endswith(".gz"):
        return gzip.open(f, mode)
    return open(f, mode, encoding=None if "b" in mode else encoding)


def init_app(app):
    if not app.config["DEBUG"]:
        ZAP_HEADERS.add("message-id")
    else:
        logging.root.setLevel("DEBUG")
    Message.app = app
