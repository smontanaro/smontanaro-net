#!/usr/bin/env python

"Return to Flask..."

import datetime
import email
import html
import os
import re
import sqlite3
import textwrap

from flask import (Flask, redirect, url_for, render_template,
                   abort, jsonify)

from util import strip_mime

CRLF = "\r\n"
REFDB = os.path.join(os.path.dirname(__file__), "references.db")

app = Flask(__name__)

@app.route("/favicon.ico")
def favicon():
    "websites need these"
    return redirect(url_for("static", filename="images/favicon.ico"))

@app.route("/")
def index():
    "index"
    body = '''
<p>Nobody here but us chickens...
and the <a href="CR">old Classic Rendezvous Archives.</a>
</p>
'''
    return render_template("main.html", title="Hello", nav="",
                           clean_title="Hello", body=body)

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
    "content-transfer-encoding",
    "content-type",
    "delivered-to",
    "domainkey-signature",
    "errors-to",
    "importance",
    "message-id",
    "mime-version",
    "precedence",
    "received",
    "reply-to",
    "return-path",
    "sender",
    }

def format_headers(message):
    "generate message header block"
    headers = []
    conn = sqlite3.connect(REFDB)
    cur = conn.cursor()
    for item in message.items():
        # Skip various headers - maybe later insert as comments...
        key = item[0].lower()
        if (key in ZAP_HEADERS or
            key[:2] == "x-" or
            key[:5] == "list-"):
            continue
        if key in ("in-reply-to", "references"):
            tags = []
            for tgt_msgid in item[1].split():
                cur.execute("select year, month, seq from messageids"
                            "  where messageid = ?",
                            (tgt_msgid,))
                try:
                    (year, month, seq) = cur.fetchone()
                except (TypeError, IndexError):
                    # pylint: disable=no-member
                    app.logger.error(f"failed to locate {tgt_msgid}.")
                    tag = html.escape(tgt_msgid)
                else:
                    url = url_for('cr_message', year=year,
                                  month=month, msg=seq)
                    tag = f"""<a href="{url}">{html.escape(tgt_msgid)}</a>"""
                tags.append(tag)
            headers.append(f'''{item[0]}: {" ".join(tags)}''')
        # elif key == "message-id":
        #     headers.append(f"<!-- {html.escape(': '.join(item))} -->")
        else:
            headers.append(html.escape(": ".join(item)))
    return CRLF.join(headers)

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
                raw_payload = message.get_payload(decode=True).decode(encoding)
            except UnicodeDecodeError as exc:
                exc_msg = str(exc)
            else:
                break
    else:
        raise UnicodeDecodeError(exc_msg)
    return (message, raw_payload)

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

    return (f'''<a href="/">Home</a>'''
            f''' <a href="/CR">CR Archives</a>'''
            f''' <a href="{uplink}">Up</a>{nxt}{prv}'''
            f''' <a href="{date_url}">Date Index</a>'''
            f''' <a href="{thread_url}">Thread Index</a>''')

def email_to_html(year, month, msgid):
    "convert the email referenced by year, month and msgid to html."
    msg = eml_file(year, month, msgid)
    mydir = os.path.join("CR", f"{year:04d}-{month:02d}", "eml-files")
    (message, raw_payload) = read_message(os.path.join(mydir, msg))

    headers = format_headers(message)
    body = make_urls_sensitive(html.escape(wrap(strip_mime(raw_payload))))

    nav = generate_nav_block(year, month, msgid)
    body = f"""<pre>{headers}\n\n{body}</pre>"""
    clean_title = trim_subject_prefix(message["Subject"])

    return render_template("main.html", title=message["Subject"],
                           clean_title=clean_title, nav=nav, body=body)

@app.route("/CR/<int:year>/<int:month>")
@app.route("/CR/<int:year>/<int:month>/dates")
def dates(year, month):
    "new date index"

    date = datetime.date(year, month, 1)
    title = date.strftime("%b %Y Date Index")
    thread_url = url_for("threads", year=year, month=f"{month:02d}")
    nav = (f'''<a name="top"><a href="/">Home</a></a>'''
           f''' <a href="/CR">Up</a>'''
           f''' <a href="{thread_url}">By Thread</a>''')
    with open(f'''CR/{date.strftime("%Y-%m")}/generated/dates.body''',
              encoding="utf-8") as fobj:
        body = fobj.read()
    return render_template("main.html", title=title, clean_title=title,
                           body=body, nav=nav)

@app.route("/CR/<int:year>/<int:month>/threads")
def threads(year, month):
    "new thread index"

    date = datetime.date(year, month, 1)
    title = date.strftime("%b %Y Thread Index")
    date_url = url_for("dates", year=year, month=f"{month:02d}")
    nav = (f'''<a href="/">Home</a>'''
           f''' <a href="/CR">Up</a>'''
           f''' <a href="{date_url}">By Date</a>''')
    with open(f'''CR/{date.strftime("%Y-%m")}/generated/threads.body''',
              encoding="utf-8") as fobj:
        body = fobj.read()
    return render_template("main.html", title=title, clean_title=title,
                           body=body, nav=nav)

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
        return redirect(url_for("threads", year=year, month=month),
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
            return render_template("main.html", title=title, clean_title=title,
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

# # Tutorial Gunicorn wsgi_app
# def application(environ, start_response):
#     """Simplest possible application object"""
#     data = b'Hello, World!\n'
#     status = '200 OK'
#     response_headers = [
#         ('Content-type', 'text/plain'),
#         ('Content-Length', str(len(data)))
#     ]
#     start_response(status, response_headers)
#     return iter([data])
