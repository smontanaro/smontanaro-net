#!/usr/bin/env python

"Return to Flask..."

from calendar import monthrange
import datetime
import email
import html
import os
import re
import sqlite3
import textwrap
import urllib.parse

from flask import (Flask, redirect, url_for, render_template,
                   abort, jsonify)
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, RadioField
from wtforms.validators import DataRequired

from util import strip_footers

ONE_DAY = datetime.timedelta(days=1)

LEFT_ARROW = "\N{LEFTWARDS ARROW}"
RIGHT_ARROW = "\N{RIGHTWARDS ARROW}"

FLASK_DEBUG = os.environ.get("FLASK_ENV") == "development"

CRLF = "\r\n"
REFDB = os.path.join(os.path.dirname(__file__), "references.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = r"Aw6CNZn*GIEt8Aw6CNZn*GIEt8"

@app.route("/favicon.ico")
def favicon():
    "websites need these"
    return redirect(url_for("static", filename="images/favicon.ico"))

@app.route("/robots.txt")
def robots():
    "websites need these"
    return redirect(url_for("static", filename="txt/robots.txt"))

@app.route("/")
def index():
    "index"
    body = '''
<p>Nobody here but us chickens...
and the <a href="CR">old Classic Rendezvous Archives.</a>
</p>
'''
    return render_template("home.html", title="Hello", nav="", body=body)

def wrap(payload):
    "wrap paragraphs in the payload."
    pl_list = re.split("(\n+)", payload)
    for (i, chunk) in enumerate(pl_list):
        if chunk and (re.match(r"\s", chunk) is None):
            pl_list[i] = "\n".join(textwrap.wrap(chunk, width=74))
    return "".join(pl_list)

def make_urls_sensitive(text):
    "<a>-ify words which look like urls (just https?)."
    new_text = []
    for word in re.split(r"(\s+)", text):
        if re.match("https?://", word):
            new_text.append(f"""<a href="{word}">{word}</a>""")
        else:
            new_text.append(word)
    return "".join(new_text)

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

if not FLASK_DEBUG:
    ZAP_HEADERS.add("message-id")

def filter_headers(message):
    "generate message header block"
    conn = sqlite3.connect(REFDB)
    cur = conn.cursor()
    last_refs = set()
    for hdr in message.keys():
        # Skip various headers - maybe later insert as comments...
        val = message[hdr]
        hdr = hdr.lower()
        if (hdr in ZAP_HEADERS or
            hdr[:2] == "x-" or
            hdr[:5] == "list-"):
            del message[hdr]
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
                    # pylint: disable=no-member
                    app.logger.warning(f"failed to locate {tgt_msgid}.")
                    tag = html.escape(tgt_msgid)
                else:
                    url = url_for('cr_message', year=year,
                                  month=month, msg=seq)
                    tag = f"""<a href="{url}">{html.escape(tgt_msgid)}</a>"""
                tags.append(tag)
            if tags:
                message.replace_header(hdr, f"{' '.join(tags)}")
        else:
            message.replace_header(hdr, html.escape(val))

def eml_file(year, month, msgid):
    "compute email file from sequence number"
    # MHonARC was written in Perl, so of course Y2k
    perl_yr = year - 1900
    return f"classicrendezvous.{perl_yr:3d}{month:02d}.{(msgid):04d}.eml"

def msg_exists(mydir, year, month, msgid):
    "test to see if there is an email message to which we should href"
    name = eml_file(year, month, msgid)
    full_path = os.path.join(mydir, name)
    if os.path.exists(full_path):
        return full_path
    return ""

PFX_MATCHER = re.compile(r"\[classicrendezvous\]|\[cr\]|re:|\s+", flags=re.I)
def trim_subject_prefix(subject):
    "Trim prefix detritus like [CR], Re:, etc"
    words = PFX_MATCHER.split(subject)
    return " ".join([word for word in words if word])

def read_message(path):
    "read an email message from path, trying encodings"
    for encoding in ("utf-8", "latin-1"):
        with open(path, encoding=encoding) as fobj:
            try:
                message = email.message_from_file(fobj)
            except UnicodeDecodeError as exc:
                exc_msg = str(exc)
            else:
                break
    else:
        raise UnicodeDecodeError(exc_msg)
    return message

def generate_nav_block(year, month, msgid):
    "navigation header at top of email messages."
    mydir = os.path.join("CR", f"{year:04d}-{month:02d}", "eml-files")
    anchor = f"{msgid:05d}"
    nxt = prv = ""
    if msg_exists(mydir, year, month, msgid - 1):
        url = url_for("cr_message", year=year, month=f"{month:02d}",
                      msg=(msgid - 1))
        prv = f' <a href="{url}">Prev</a>'
    if msg_exists(mydir, year, month, msgid + 1):
        url = url_for("cr_message", year=year, month=f"{month:02d}",
                      msg=(msgid + 1))
        nxt = f' <a href="{url}">Next</a>'
    uplink = url_for("dates", year=year, month=f"{month:02d}")

    date_url = (url_for("dates", year=year, month=f"{month:02d}") +
                f"#{anchor}")
    thread_url = (url_for("threads", year=year, month=f"{month:02d}") +
                  f"#{anchor}")

    return (f'''<a href="{uplink}">Up</a>{nxt}{prv}'''
            f'''&nbsp;<a href="{date_url}">Date Index</a>'''
            f'''&nbsp;<a href="{thread_url}">Thread Index</a>''')

class MessageFilter:
    "filter various uninteresting bits from messages"
    def __init__(self, message):
        self.message = message
        self.to_delete = []

    def filter_message(self, message):
        "filter headers and text body parts"
        for part in message.walk():
            filter_headers(part)
            if part.is_multipart():
                if part is not self.message:
                    self.filter_message(part)
                continue

            for encoding in ("utf-8", "latin-1"):
                try:
                    payload = part.get_payload(decode=True)
                    payload = payload.decode(encoding=encoding)
                except UnicodeDecodeError:
                    continue
                break
            payload = strip_footers(payload)
            payload = wrap(payload)
            payload = html.escape(payload)
            payload = make_urls_sensitive(payload).strip()
            part.set_payload(payload)
            if not payload and part is not self.message:
                self.to_delete.append(part)

    def delete_empty_parts(self):
        "if we emptied out parts, remove them altogether"
        if not self.to_delete:
            return
        for part in self.message.walk():
            if part.is_multipart():
                payload = part.get_payload()
                for todel in self.to_delete:
                    if todel in payload:
                        payload.remove(todel)

def email_to_html(year, month, msgid):
    "convert the email referenced by year, month and msgid to html."
    nav = generate_nav_block(year, month, msgid)
    msg = eml_file(year, month, msgid)
    mydir = os.path.join("CR", f"{year:04d}-{month:02d}", "eml-files")
    message = read_message(os.path.join(mydir, msg))

    filt = MessageFilter(message)
    filt.filter_message(message)
    filt.delete_empty_parts()

    # content-type and content-transfer-encoding are necessary when
    # manipulating message elements, but we prefer not to display
    # them, so filter them out of the string representation.
    content_headers = ("content-type", "content-transfer-encoding")
    nl = '\n'
    lines = [line
               for line in re.split(nl, str(message))
                 if line.lower().split(":", 1)[0] not in content_headers]
    body = f"""<pre>{nl.join(lines)}</pre>"""
    return render_template("cr.html", title=message["Subject"],
                           nav=nav, body=body)

# boundaries of the archive - should be discovered
OLDEST_MONTH = (2000, 3)
NEWEST_MONTH = (2011, 2)

def _month_url(start_year, start_month, offset, what):
    "previous month - often month +/- 1, but not always (we have gaps)"

    day = 1 if offset == -1 else monthrange(start_year, start_month)[1]
    arrow = LEFT_ARROW if offset == -1 else RIGHT_ARROW
    dt = datetime.date(start_year, start_month, day)
    dt += ONE_DAY * offset

    while OLDEST_MONTH <= (dt.year, dt.month) <= NEWEST_MONTH:
        path = dt.strftime(f"CR/{dt.year}-{dt.month:02d}")
        if os.path.exists(path):
            prev_url = url_for(what, year=dt.year,
                               month=f"{dt.month:02d}")
            return f'<a href="{prev_url}">{arrow}</a>&nbsp;'
        day = 1 if offset == -1 else monthrange(dt.year, dt.month)[1]
        dt = dt.replace(day=day) + ONE_DAY * offset
    return ""

@app.route("/CR/<year>/<month>")
@app.route("/CR/<year>/<month>/dates")
def dates(year, month):
    "new date index"

    year = int(year)
    month = int(month)
    date = datetime.date(year, month, 1)

    prev_url = _month_url(year, month, -1, "dates")
    next_url = _month_url(year, month, +1, "dates")

    title = date.strftime("%b %Y Date Index")
    thread_url = url_for("threads", year=year, month=f"{month:02d}")
    nav = (f''' <a href="{thread_url}">By Thread</a>''')

    with open(f'''CR/{date.strftime("%Y-%m")}/generated/dates.body''',
              encoding="utf-8") as fobj:
        body = fobj.read()
    return render_template("cr.html", title=title, body=body, nav=nav,
                           prev=prev_url, next=next_url)

@app.route("/CR/<year>/<month>/threads")
def threads(year, month):
    "new thread index"

    year = int(year)
    month = int(month)
    date = datetime.date(year, month, 1)

    prev_url = _month_url(year, month, -1, "threads")
    next_url = _month_url(year, month, +1, "threads")

    title = date.strftime("%b %Y Thread Index")
    date_url = url_for("dates", year=year, month=f"{month:02d}")
    nav = (f''' <a href="{date_url}">By Date</a>''')
    with open(f'''CR/{date.strftime("%Y-%m")}/generated/threads.body''',
              encoding="utf-8") as fobj:
        body = fobj.read()
    return render_template("cr.html", title=title, body=body, nav=nav,
                           prev=prev_url, next=next_url)

@app.route('/CR/<year>/<month>/<int:msg>')
def cr_message(year, month, msg):
    "render email as html."
    return email_to_html(int(year), int(month), msg)

@app.route('/<year>-<month>/html/<filename>')
def old_cr(year, month, filename):
    "convert old archive url structure to new."

    if filename in ("index.html", "maillist.html"):
        return redirect(url_for("dates", year=year, month=month),
                        code=301)

    if filename == "threads.html":
        return redirect(url_for("threads", year=year, month=f"{month:02d}"),
                        code=301)

    mat = re.search("msg([0-9]+)[.]html", filename)
    if mat is None:
        abort(404)
        # dead code, but this should make pylint like us again...
        return redirect("cr_index")

    map_to = f"{(int(mat.groups()[0]) + 1):05d}"
    return redirect(url_for("cr_message", year=year, month=month,
                            msg=map_to),
                    code=301)

@app.route("/CR")
@app.route("/CR/")
@app.route("/CR/index.html")
@app.route("/CR/index")
def cr_index():
    "templated index"

    title = "Old Classic Rendezvous Archive"
    if os.path.exists("CR/generated/index.body"):
        with open("CR/generated/index.body", encoding="utf8") as fobj:
            body = fobj.read()
            return render_template("cr.html", title=title,
                                   body=body, nav="")
    else:
        with open("CR/index.html", encoding="utf-8") as fobj:
            return fobj.read()

@app.route('/api/help')
def app_help():
    """Print available functions."""
    func_list = {}
    for rule in app.url_map.iter_rules():
        if rule.endpoint != 'static':
            func_list[rule.rule] = str(app.view_functions[rule.endpoint])
    return jsonify(func_list)

class SearchForm(FlaskForm):
    "simple form used to search Brave for archived list messages"
    query = StringField('search:', validators=[DataRequired()])
    site = HiddenField('site', default='smontanaro.net')
    engine = RadioField('engine', choices=[
        ('Brave', 'Brave'),
        ('DuckDuckGo', 'DuckDuckGo'),
        ('Google', 'Google'),
    ], default='Brave')

SEARCH = {
    "DuckDuckGo": "https://search.duckduckgo.com/",
    "Bing": "https://bing.com/search",
    "Google": "https://google.com/search",
    "Brave": "https://search.brave.com/search",
}

@app.route('/search', methods=['GET', 'POST'])
def search():
    form = SearchForm()
    if form.validate_on_submit():
        query = urllib.parse.quote_plus(f"{form.query.data}")
        query += f"+site:{form.site.data}"
        engine = SEARCH.get(form.engine.data, SEARCH["Brave"])
        return redirect(f"{engine}?q={query}")
    return render_template('cr.html', form=form)

@app.context_processor
def template_globals():
    "Today's date, etc"
    return {
        "today": datetime.date.today(),
        "form": SearchForm(),
    }

if FLASK_DEBUG:
    @app.route("/env")
    def printenv():
        return jsonify(dict(os.environ))
