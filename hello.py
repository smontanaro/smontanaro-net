import email
import html
import os

from flask import Flask, redirect, url_for

app = Flask(__name__)

@app.route("/")
def index():
    return 'Index Page'

@app.route('/hello')
def hello():
    return 'Hello, World'
    return "Hello, World!"

CRLF = "\r\n"

def email_to_html(year, month, msg):
    # Perl?
    yr = year - 1900
    msg = f"classicrendezvous.{yr:3d}{month:02d}.{msg:04d}.eml"
    filename = os.path.join("CR", f"{year:04d}-{month:02d}", "eml-files", msg)
    message = email.message_from_file(open(filename))
    headers = html.escape(CRLF.join(": ".join(hdr) for hdr in message._headers
                                        if hdr[0] != "Received" and hdr[0][0:2] != "X-"))
    body = html.escape(message.get_payload())
    as_string = f"""
<html>
<head></head>
<body>
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
    # print(os.path.abspath(filename))
    return open(filename, encoding="latin1").read()

@app.route('/CR/<int:year>/<int:month>/<int:msg>')
def cr_message(year, month, msg):
    return email_to_html(year, month, msg)

@app.route("/CR")
@app.route('/CR/<year>/<month>')
@app.route('/CR/<year>/<month>/<filename>')
def cr(year=None, month=None, filename="index.html"):
    if year is None or month is None:
        endpoint = os.path.join("CR", filename)
    else:
        endpoint = os.path.join("CR", f"{year}-{month}", "html", filename)
    return _render_file(endpoint)

@app.route('/<year>-<month>')
@app.route('/<year>-<month>/html/<filename>')
@app.route('/<year>-<month>/<filename>')
def old_cr_month(year, month, filename="index.html"):
    return redirect(url_for("cr", year=year, month=month, filename=filename),
                    code=301)
