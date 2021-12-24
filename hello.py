import email
import html
import os
import re
import textwrap

from flask import Flask, redirect, url_for

app = Flask(__name__)

@app.route("/")
def index():
    return '''
<p>Nobody here but us chickens...
and the <a href="CR">old Classic Rendezvous Archives.</a>
</p>
'''

@app.route('/hello')
def hello():
    return 'Hello, World'
    return "Hello, World!"

CRLF = "\r\n"

def wrap(payload):
    pl_list = re.split("(\n+)", payload)
    for i in range(len(pl_list)):
        chunk = pl_list[i]
        if chunk and (re.match(r"\s", chunk) is None):
            pl_list[i] = "\n".join(textwrap.wrap(chunk, width=74))
    return "".join(pl_list)

def email_to_html(year, month, msg):
    # Perl?
    yr = year - 1900
    msg = f"classicrendezvous.{yr:3d}{month:02d}.{msg:04d}.eml"
    filename = os.path.join("CR", f"{year:04d}-{month:02d}", "eml-files", msg)
    message = email.message_from_file(open(filename))
    headers = html.escape(CRLF.join(": ".join(hdr) for hdr in message._headers
                                        if hdr[0] != "Received" and hdr[0][0:2] != "X-"))
    raw_payload = message.get_payload(decode=True).decode("utf-8")
    body = html.escape(wrap(raw_payload))
    as_string = f"""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
<a href="../..">Up</a>
<pre>
{headers}
</pre>
{CRLF}
{CRLF}
<pre>
{body}
</pre>
</body>
</html>
    """
    return as_string

def _render_file(filename):
    "Relying on MHonArc's presumed Latin-1 encoding for now."
    return open(filename, encoding="latin1").read()

@app.route('/CR/<int:year>/<int:month>/<int:msg>')
def cr_message(year, month, msg):
    return email_to_html(year, month, msg)

@app.route('/<int:year>-<int:month>')
@app.route('/CR/<int:year>-<int:month>/html/<filename>')
@app.route('/<int:year>-<int:month>/html/<filename>')
@app.route('/<int:year>-<int:month>/<filename>')
def old_cr_month(year, month, filename="index.html"):
    return redirect(url_for("cr", year=year, month=month,
                            filename=filename),
                    code=301)
    # return redirect(url_for("cr", year=str(year), month=str(month),
    #                         filename=filename),
    #                 code=301)

@app.route("/CR")
@app.route("/CR/")
@app.route('/CR/<int:year>/<int:month>')
@app.route('/CR/<int:year>/<int:month>/<filename>')
def cr(year=None, month=None, filename="index.html"):
    if year is None or month is None:
        endpoint = os.path.join("CR", filename)
    else:
        endpoint = os.path.join("CR", f"{year:04d}-{month:02d}", "html",
                                filename)
    return _render_file(endpoint)
