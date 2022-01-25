#!/usr/bin/env python

"Return to Flask..."

from calendar import monthrange
import datetime
import html
import os
import re
import urllib.parse

from flask import redirect, url_for, render_template, abort, jsonify, request
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, RadioField
from wtforms.validators import DataRequired

from .db import ensure_db
from .strip import strip_footers
from .util import read_message, trim_subject_prefix
from .exc import NoResponse

SEARCH = {
    "DuckDuckGo": "https://search.duckduckgo.com/",
    "Bing": "https://bing.com/search",
    "Google": "https://google.com/search",
    "Brave": "https://search.brave.com/search",
}

ONE_DAY = datetime.timedelta(days=1)

# boundaries of the archive - should be discovered
OLDEST_MONTH = (2000, 3)
NEWEST_MONTH = (2011, 2)

LEFT_ARROW = "\N{LEFTWARDS ARROW}"
RIGHT_ARROW = "\N{RIGHTWARDS ARROW}"

def init_simple(app):
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
        return render_template("main.html", title="Home", nav="")

def init_cr(app, CR):
    @app.route("/CR")
    @app.route("/CR/")
    @app.route("/CR/index.html")
    @app.route("/CR/index")
    def cr_index():
        "templated index"

        with open(f"{CR}/generated/index.body", encoding="utf8") as fobj:
            return render_template("cr.html", body=fobj.read(), nav="",
                                   title="Old Classic Rendezvous Archive")

    @app.route("/CR/<year>/<month>")
    @app.route("/CR/<year>/<month>/dates")
    def dates(year, month):
        "new date index"

        year = int(year)
        month = int(month)
        date = datetime.date(year, month, 1)

        prev_url = month_url(year, month, -1, "dates")
        next_url = month_url(year, month, +1, "dates")

        title = date.strftime("%b %Y Date Index")
        thread_url = url_for("threads", year=year, month=f"{month:02d}")
        nav = (f''' <a href="{thread_url}">By Thread</a>''')

        with open(f'''{CR}/{date.strftime("%Y-%m")}/generated/dates.body''',
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

        prev_url = month_url(year, month, -1, "threads")
        next_url = month_url(year, month, +1, "threads")

        title = date.strftime("%b %Y Thread Index")
        date_url = url_for("dates", year=year, month=f"{month:02d}")
        nav = (f''' <a href="{date_url}">By Date</a>''')
        with open(f'''{CR}/{date.strftime("%Y-%m")}/generated/threads.body''',
                  encoding="utf-8") as fobj:
            body = fobj.read()
        return render_template("cr.html", title=title, body=body, nav=nav,
                               prev=prev_url, next=next_url)

    @app.route('/CR/<year>/<month>/<int:msg>')
    def cr_message(year, month, msg):
        "render email as html."
        return email_to_html(int(year), int(month), msg)

    def month_url(start_year, start_month, offset, what):
        "previous month - often month +/- 1, but not always (we have gaps)"

        day = 1 if offset == -1 else monthrange(start_year, start_month)[1]
        arrow = LEFT_ARROW if offset == -1 else RIGHT_ARROW
        dt = datetime.date(start_year, start_month, day) + ONE_DAY * offset

        while OLDEST_MONTH <= (dt.year, dt.month) <= NEWEST_MONTH:
            path = dt.strftime(f"{CR}/{dt.year}-{dt.month:02d}")
            if os.path.exists(path):
                prev_url = url_for(what, year=dt.year,
                                   month=f"{dt.month:02d}")
                return f'<a href="{prev_url}">{arrow}</a>&nbsp;'
            day = 1 if offset == -1 else monthrange(dt.year, dt.month)[1]
            dt = dt.replace(day=day) + ONE_DAY * offset
        return ""

    def generate_nav_block(year, month, msgid):
        "navigation header at top of email messages."

        mydir = os.path.join(CR, f"{year:04d}-{month:02d}", "eml-files")
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

        date_url = (url_for("dates", year=year, month=f"{month:02d}"))
        thread_url = (url_for("threads", year=year, month=f"{month:02d}"))

        return (f'<a href="{uplink}">Up</a>{nxt}{prv}'
                f'&nbsp;<a href="{date_url}#{msgid:05d}">Date Index</a>'
                f'&nbsp;<a href="{thread_url}#{msgid:05d}">Thread Index</a>')

    def email_to_html(year, month, msgid):
        "convert the email referenced by year, month and msgid to html."
        nav = generate_nav_block(year, month, msgid)
        msg = eml_file(year, month, msgid)
        mydir = os.path.join(CR, f"{year:04d}-{month:02d}", "eml-files")
        message = read_message(os.path.join(mydir, msg))

        filt = MessageFilter(message)
        filt.filter_message(message)
        filt.delete_empty_parts()

        title = html.escape(message["Subject"])
        clean = html.escape(trim_subject_prefix(message["Subject"]))

        return render_template("cr.html", title=title, page_title=clean,
                               nav=nav, body=message.as_html())

def init_redirect(app):
    @app.route('/<year>-<month>/html/<filename>')
    def old_cr(year, month, filename):
        "convert old archive url structure to new."

        # will arrive as a string, but we want an int to force formatting
        month = int(month, 10)

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

def init_extra(app):
    @app.route("/request/<header>")
    def req(header):
        if not header.startswith("HTTP_"):
            raise NoResponse
        return request.environ.get(header, "???")

    @app.context_processor
    def template_globals():
        "Today's date, etc"
        return {
            "today": datetime.date.today(),
            "form": SearchForm(),
        }

def init_debug(app):
    @app.route("/env")
    def printenv():
        return jsonify(dict(os.environ))

    @app.route('/api/help')
    def app_help():
        """Print available functions."""
        func_list = {}
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                func_list[rule.rule] = str(app.view_functions[rule.endpoint])
        return jsonify(func_list)

    @app.get('/shutdown')
    def shutdown():
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()
        return 'Server shutting down...\n'

def init_search(app):
    @app.route('/search', methods=['GET', 'POST'])
    def search():
        form = SearchForm()
        if form.validate_on_submit():
            query = urllib.parse.quote_plus(f"{form.query.data}")
            query += f"+site:{form.site.data}"
            engine = SEARCH.get(form.engine.data, SEARCH["Brave"])
            return redirect(f"{engine}?q={query}")
        return render_template('cr.html', form=form)

def init_topics(app):
    @app.route('/topics')
    @app.route('/topics/<topic>')
    def topics(topic=""):
        "list topics or display entries for a specific topic"
        conn = ensure_db(app.config["REFDB"])
        cur = conn.cursor()
        cur.execute("""
          select distinct topic from topics
          order by topic
        """)
        topics = [t[0] for t in cur.fetchall()]

        if not topic:
            msgrefs = []
        else:
            msgrefs=[(yr, mo, seq, trim_subject_prefix(subj))
                        for (yr, mo, seq, subj) in get_topic(topic, conn)]
        return render_template("topics.html", topics=topics, msgrefs=msgrefs,
                               topic=topic)

class SearchForm(FlaskForm):
    "simple form used to search Brave for archived list messages"
    query = StringField('Search:', validators=[DataRequired()])
    site = HiddenField('site', default='smontanaro.net')
    engine = RadioField('Engine:', choices=[
        ('Brave', 'Brave'),
        ('DuckDuckGo', 'DuckDuckGo'),
        ('Google', 'Google'),
    ], default='Brave')

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

class MessageFilter:
    "filter various uninteresting bits from messages"
    def __init__(self, message):
        self.message = message
        self.to_delete = []
        self.seen_parts = set()

    def filter_message(self, message):
        "filter headers and text body parts"
        for part in message.walk():
            if part in self.seen_parts:
                return
            self.seen_parts.add(part)
            part.filter_headers()
            if part.is_multipart():
                if part is not self.message:
                    self.filter_message(part)
                continue

            payload = message.get_payload(decode=True)
            if payload is None:
                # multipart/mixed, for example
                continue
            payload = message.decode(payload)
            payload = strip_footers(payload)
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

def get_topic(topic, conn):
    cur = conn.cursor()
    return cur.execute("""
      select m.year, m.month, m.seq, m.subject from
        topics t join messages m
          on t.messageid = m.messageid
        where t.topic = ?
        order by m.year, m.month, m.seq
    """, (topic,)).fetchall()

def init_app(app):
    CR = app.config["CR"]

    init_simple(app)
    init_cr(app, CR)
    init_redirect(app)
    init_extra(app)
    init_search(app)
    init_topics(app)

    if app.config["DEBUG"]:
        init_debug(app)
