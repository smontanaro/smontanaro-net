#!/usr/bin/env python

"Return to Flask..."

import email
import html
import os
import re
import sqlite3
import sys
import textwrap

from flask import Flask, redirect, url_for, render_template

CRLF = "\r\n"
REFDB = os.path.join(os.path.dirname(__file__), "references.db")

app = Flask(__name__)

@app.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="images/favicon.ico"))

@app.route("/")
def index():
    "index"
    primary = '''
<p>Nobody here but us chickens...
and the <a href="CR">old Classic Rendezvous Archives.</a>
</p>
'''
    return render_template("main.html", title="Hello", nav="", primary=primary)

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
    "message-id",
    "mime-version",
    "precedence",
    "received",
    "return-path",
    "sender",
    }

def format_headers(message):
    headers = []
    conn = sqlite3.connect(REFDB)
    cur = conn.cursor()
    for item in message.items():
        # Skip various headers - maybe later insert as comments...
        if (item[0].lower() in ZAP_HEADERS or
            item[0][:2].lower() == "x-" or
            item[0][:5].lower() == "list-"):
            continue
        if item[0].lower() == "message-id":
            cur.execute("select reference from msgrefs"
                        "  where messageid = ?",
                        (item[1],))
            print("refs>>", item[1], "->", cur.fetchall())
            cur.execute("select year, month, seq from messageids"
                        "  where messageid = ?",
                        (item[1],))
            print("message>>", item[1], "->", cur.fetchall())
            headers.append(html.escape(": ".join(item)))
        elif item[0].lower() in ("in-reply-to", "references"):
            tags = []
            for tgt_msgid in item[1].split():
                cur.execute("select year, month, seq from messageids"
                            "  where messageid = ?",
                            (tgt_msgid,))
                try:
                    (year, month, seq) = cur.fetchone()
                except (TypeError, IndexError):
                    print(f"failed to locate {tgt_msgid}.",
                          file=sys.stderr)
                    tag = html.escape(tgt_msgid)
                else:
                    url = url_for('cr_message', year=year,
                                  month=month, msg=seq)
                    tag = f"""<a href="{url}">{html.escape(tgt_msgid)}</a>"""
                tags.append(tag)
            headers.append(f'''{item[0]}: {" ".join(tags)}''')
        else:
            headers.append(html.escape(": ".join(item)))
    return CRLF.join(headers)

def eml_file(year, month, msgid):
    # MHonARC was written in Perl, so of course Y2k
    perl_yr = year - 1900
    return f"classicrendezvous.{perl_yr:3d}{month:02d}.{(msgid+1):04d}.eml"

def msg_exists(mydir, year, month, msgid):
    name = eml_file(year, month, msgid)
    full_path = os.path.join(mydir, name)
    if os.path.exists(full_path):
        return full_path
    return ""

def trim_subject_prefix(subject):
    "Trim prefix detritus like [CR], Re:, etc"
    clean_subject = []
    words = subject.split()
    for word in words:
        if word.lower() in ("[classicrendezvous]", "[cr]", "re:"):
            continue
        clean_subject.append(word)
    return " ".join(clean_subject)

def email_to_html(year, month, msgid):
    "convert the email referenced by year, month and msgid to html."
    msg = eml_file(year, month, msgid)
    mydir = os.path.join("CR", f"{year:04d}-{month:02d}", "eml-files")
    for encoding in ("utf-8", "latin-1"):
        with open(os.path.join(mydir, msg), encoding=encoding) as fobj:
            try:
                message = email.message_from_file(fobj)
            except UnicodeDecodeError:
                pass
            else:
                raw_payload = message.get_payload(decode=True).decode(encoding)
                break

    headers = format_headers(message)
    body = make_urls_sensitive(html.escape(wrap(raw_payload)))

    anchor = f"{(msgid - 1):05d}"

    nxt = prv = ""
    if msg_exists(mydir, year, month, msgid - 1):
        url = url_for("cr_message", year=year, month=f"{month:02d}",
                      msg=(msgid - 1))
        prv = f' <a href="{url}">Prev</a>'
    if msg_exists(mydir, year, month, msgid + 1):
        url = url_for("cr_message", year=year, month=f"{month:02d}",
                      msg=(msgid + 1))
        nxt = f' <a href="{url}">Next</a>'
    up = url_for("new_cr", year=year, month=f"{month:02d}", filename="maillist.html")

    date_url = url_for("new_cr", year=year, month=f"{month:02d}",
                       filename="maillist.html") + f"#{anchor}"
    thread_url = url_for("new_cr", year=year, month=f"{month:02d}",
                           filename="threads.html") + f"#{anchor}"

    title = trim_subject_prefix(message["Subject"])
    nav = (f'''<a href="/">Home</a>'''
           f''' <a href="/CR">CR Archives</a>'''
           f''' <a href="{up}">Up</a>{nxt}{prv}'''
           f''' <a href="{date_url}">Date Index</a>'''
           f''' <a href="{thread_url}">Thread Index</a>''')
    primary = f"""<pre>{headers}\n\n{body}</pre>"""

    return render_template("main.html", title=title, nav=nav, primary=primary)

@app.route('/CR/<year>/<month>/<int:msg>')
def cr_message(year, month, msg):
    "render email as html."
    return email_to_html(int(year), int(month), msg)

@app.route('/<year>-<month>/html/<filename>')
@app.route('/CR/<year>-<month>/html/<filename>')
@app.route('/<year>-<month>')
@app.route('/<year>-<month>/<filename>')
def old_cr(year, month, filename="index.html"):
    "convert old archive url structure to new."
    print(">> old_cr:", (year, month, filename))
    return redirect(url_for("new_cr", year=year, month=month,
                            filename=filename),
                    code=301)
    # return redirect(url_for("new_cr", year=str(year), month=str(month),
    #                         filename=filename),
    #                 code=301)

@app.route("/CR")
@app.route("/CR/")
@app.route('/CR/<year>/<month>')
@app.route('/CR/<year>/<month>/<filename>')
def new_cr(year=None, month=None, filename="index.html"):
    "basic new archive url format display"
    print(">> cr:", (year, month, filename))
    if "#" in filename:
        (filename, anchor) = filename.split("#")
    else:
        anchor = ""
    if year is None or month is None:
        endpoint = os.path.join("CR", filename)
    else:
        endpoint = os.path.join("CR", f"{year}-{month}", "html",
                                filename)
    print(">> endpoint:", endpoint)
    # Rely on MHonArc's presumed Latin-1 encoding for now.
    with open(endpoint, encoding="latin1") as fobj:
        return fobj.read()

# Tutorial Gunicorn wsgi_app
def application(environ, start_response):
    """Simplest possible application object"""
    data = b'Hello, World!\n'
    status = '200 OK'
    response_headers = [
        ('Content-type', 'text/plain'),
        ('Content-Length', str(len(data)))
    ]
    start_response(status, response_headers)
    return iter([data])
