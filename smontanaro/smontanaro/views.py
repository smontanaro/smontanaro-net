#!/usr/bin/env python

"Return to Flask..."

from calendar import monthrange, month_name
import csv
import datetime
import glob
import logging
import os
# import signal
import sqlite3
import sys
import urllib.parse

# import mpl

# import arrow
from flask import (redirect, url_for, render_template, abort, jsonify, request,
                   current_app, send_from_directory)
from flask_wtf import FlaskForm
import regex as re
import requests
from wtforms import StringField, HiddenField, SelectField
from wtforms.validators import DataRequired

from .exc import NoResponse
from .log import eprint
from .refdb import ensure_db, get_topics_for, get_random_topic
from .srchdb import SRCHDB
from .query import execute_query
from .strip import strip_footers
from .util import (read_message, trim_subject_prefix, clean_msgid,
                   make_topic_hierarchy, get_topic, generate_link, open_,
                   GooglePhotoParser)

SEARCH = {
    "DuckDuckGo": "https://duckduckgo.com/",
    "Bing": "https://bing.com/search",
    "Google": "https://google.com/search",
    "Brave": "https://search.brave.com/search",
    "Neeva": "https://neeva.com/search",
}

ONE_DAY = datetime.timedelta(days=1)

# boundaries of the archive - should be discovered
OLDEST_MONTH = (2000, 3)
NEWEST_MONTH = (2011, 2)

LEFT_ARROW = "\N{LEFTWARDS ARROW}"
RIGHT_ARROW = "\N{RIGHTWARDS ARROW}"

def init_simple():
    app = current_app

    @app.route("/python")
    def python():
        "my old python stuff"
        return render_template("python.jinja")

    @app.route("/CR/about")
    def about():
        "websites need these"
        return render_template("about.jinja")

    @app.route("/sitemap.xml")
    def sitemap_index():
        "websites need these"
        CR = app.config["CR"]
        with open_(f'{CR}/generated/sitemap.xml', encoding="utf-8") as fobj:
            return fobj.read()

    @app.route("/CR/<year>/<month>/sitemap.xml")
    def sitemap_by_month(year, month):
        "websites need these"
        CR = app.config["CR"]
        with open_(f'{CR}/{year}-{month}/generated/sitemap.xml',
                   encoding="utf-8") as fobj:
            return fobj.read()

    @app.route('/CR/<year>/<month>/mybikes')
    @app.route('/<year>/<month>/mybikes')
    def mybikes(year, month):
        "currently broken link - redirect"
        return redirect(url_for("dates", year=year, month=month))

    @app.route('/CR/<year>/<month>/about')
    @app.route('/<year>/<month>/about')
    # pylint: disable=unused-argument
    def _about(year, month):
        "currently broken link - redirect"
        return redirect(url_for("about"))

    @app.route("/CR/help")
    def help_():
        "websites need these"
        return render_template("help.jinja")

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
        return render_template("main.jinja", title="Home")

    @app.route("/photolink/<fmt>/<width>/<path:path>")
    def photolink(fmt, width, path):
        html = GooglePhotoParser()
        response = requests.get(path, timeout=10)
        if response.status_code == 200:
            html.feed(response.text)
        if not html.ref:
            return "No image reference found"

        html.ref += f"=w{width}"
        match fmt.lower():
            case "html":
                return f"""<pre>&lt;a href={path}&gt;&lt;img src="{html.ref}" /&gt;&lt;/a&gt;</pre>"""
            case "forum":
                return f"<pre>[url={path}][img]{html.ref}[/img][/url]</pre>"
            case _:
                return f"Unrecognized format: {fmt}"


    @app.route("/43bikes")
    @app.route("/43bikes/")
    @app.route("/43bikes/<path:path>")
    def bikes_43(path="index.html"):
        "static replica sites"
        vtdir = f"{os.environ.get('CRDIR')}/smontanaro/smontanaro/static/bikes"
        return send_from_directory(vtdir, os.path.join("43bikes", path))

    @app.route("/vintage-trek")
    @app.route("/vintage-trek/")
    @app.route("/vintage-trek/<path:path>")
    def vintage_trek(path="index.html"):
        "static replica sites"
        vtdir = f"{os.environ.get('CRDIR')}/smontanaro/smontanaro/static/bikes"
        return send_from_directory(vtdir, os.path.join("vintage-trek", path))

    ## @app.route("/<staticbikes>")
    ## @app.route("/<staticbikes>/")
    ## @app.route("/<staticbikes>/<path:path>")
    ## def static_bikes(staticbikes, path="index.html"):
    ##     "static replica sites"
    ##     vtdir = f"{os.environ.get('CRDIR')}/smontanaro/smontanaro/static/bikes"
    ##     return send_from_directory(vtdir, os.path.join(staticbikes, path))

def init_indexes():
    app = current_app
    CR = app.config["CR"]

    @app.route("/CR/<year>/<month>")
    @app.route("/CR/<year>/<month>/dates")
    def dates(year, month):
        "new date index"

        year = int(year)
        month = int(month)
        date = datetime.date(year, month, 1)

        prev_url = month_url(year, month, -1, "dates")
        next_url = month_url(year, month, +1, "dates")

        title = f"{date.strftime('%b %Y Date Index')}"
        with open_(f'{CR}/{date.strftime("%Y-%m")}/generated/dates.body',
                   encoding="utf-8") as fobj:
            body = fobj.read()

        return render_template("dates.jinja", title=title, body=body,
                               prev=prev_url, next=next_url, year=year,
                               month=month)

    @app.route("/CR/<year>/<month>/threads")
    def threads(year, month):
        "new thread index"

        year = int(year)
        month = int(month)
        date = datetime.date(year, month, 1)

        prev_url = month_url(year, month, -1, "threads")
        next_url = month_url(year, month, +1, "threads")

        title = date.strftime("%b %Y Thread Index")
        with open_(f'{CR}/{date.strftime("%Y-%m")}/generated/threads.body',
                   encoding="utf-8") as fobj:
            body = fobj.read()

        return render_template("threads.jinja", title=title, body=body,
                               prev=prev_url, next=next_url, year=year,
                               month=month)

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

# LAST_BH_PING = arrow.get(0)
# def init_bh():
#     "Beach House..."
#     app = current_app
#     crdir = app.config["CRDIR"]
#     mapfile = os.path.join(crdir, "bhuptime.csv")

#     @app.route("/BH")
#     @app.route("/BH/")
#     @app.route("/BH/index.html")
#     @app.route("/BH/index")
#     def bh_index():
#         "templated index"
#         plotfile = os.path.join(crdir, "smontanaro", "smontanaro",
#                                 "static", "images", "bhuptime.png")
#         opts = mpl.Options()
#         opts.title = ""
#         opts.fields = [['timestamp', 'temperature', 'l', 'b', 'temp', '-', '']]
#         opts.plot_file = plotfile
#         opts.bg_spec = [["timestamp", "status", 1, "skyblue"],
#                         ["timestamp", "status", 0, "lightgreen"]]
#         with open_(mapfile, encoding="utf-8") as mapf:
#             mpl.plot(opts, csv.DictReader(mapf))
#         return render_template("bhindex.jinja",
#                                title="Beach House Power History")

#     @app.route("/BH/ping/<temp>")
#     def bh_ping(temp=0.0):
#         "Beach House ping endpoint."
#         # Every time this is called, it adds a line to bhuptime.csv
#         # and resets the last ping timer.
#         global LAST_BH_PING
#         now = LAST_BH_PING = arrow.get()
#         add_bh_record(now, 1, temp)
#         signal.alarm(300)
#         return "OK"

#     def add_bh_record(now, status, temp=None):
#         "Add a record to the Beach House CSV file."
#         mapfile = os.path.join(crdir, "bhuptime.csv")
#         with open_(mapfile, encoding="utf-8") as mapf:
#             fnames = csv.DictReader(mapf).fieldnames
#         with open_(mapfile, "a", encoding="utf-8") as mapf:
#             writer = csv.DictWriter(mapf, fieldnames=fnames)
#             writer.writerow({
#                 "timestamp": now,
#                 "status": status,
#                 "temperature": None if temp is None else temp,
#             })

#     def alarm_clock(_signum, _frame):
#         "Alarm went off. Record the problem and reset."
#         add_bh_record(arrow.get(), 0)
#         signal.alarm(300)

#     # Start things off...
#     signal.signal(signal.SIGALRM, alarm_clock)
#     signal.alarm(300)

def init_cr():
    app = current_app
    CR = app.config["CR"]

    @app.route("/CR")
    @app.route("/CR/<cache>")
    @app.route("/CR/")
    @app.route("/CR/index.html")
    @app.route("/CR/index")
    def cr_index(cache=None):
        "templated index"

        if cache is not None:
            # Already filtered...
            index = os.path.join(CR, "generated", "cache", cache)
        else:
            index = f"{CR}/generated/index.body"
        with open_(index, encoding="utf8") as fobj:
            return render_template("crtop.jinja", body=fobj.read(),
                                   title="Old Classic Rendezvous Archive")

    @app.route('/CR/<year>/<month>/<seq>')
    def cr_message(year, month, seq):
        "render email as html."
        return email_to_html(int(year), int(month), seq)


def email_to_html(year, month, seq, note=""):
    "convert the email referenced by year, month and seq to html."
    CR = current_app.config["CR"]

    if not isinstance(seq, int):
        seq = int(seq, 10)
    msg = eml_file(year, month, seq)
    mydir = os.path.join(CR, f"{year:04d}-{month:02d}", "eml-files")
    path = os.path.join(mydir, msg)
    try:
        message = read_message(path)
    except FileNotFoundError:
        logging.root.error("File not found: %s", path)
        abort(404)

    # Grab these before we sanitize any headers.
    msgid = message["Message-ID"]
    title = message["Subject"]
    clean = trim_subject_prefix(title)

    # Occurrences of Message-ID seem to sometimes contain whitespace, but
    # not always in the Message-ID header. See /CR/2006/10/0542
    # for an example
    msgid = clean_msgid(msgid)
    if msgid != message["Message-ID"]:
        logging.root.warning("Message-ID found to contain whitespace! %s", (year, month, seq))

    filt = MessageFilter(message)
    filt.filter_message(message)

    refdb = current_app.config["REFDB"]
    return render_template("cr.jinja", title=title, page_title=clean,
                           body=message.as_html(),
                           year=year, month=month, seq=seq,
                           topics=get_topics_for(msgid, refdb),
                           note=note,
                           nav=get_nav_items(year=year, month=month, seq=seq),
                           some_topic=get_random_topic(refdb))


def query_index(query):
    "use query string to search for matching pages"
    # TBD - a bit of AND and OR connectors
    # TBD - paginate results

    pages = []
    result = execute_query(query.strip())
    for page in sorted(result.pages()):
        fragment = result[page]
        match = re.match("CR/([0-9]+)-([0-9]+)/eml-files/"
                         "classicrendezvous.[0-9]+.([0-9]+).eml", page)
        if match is None:
            continue
        yr, mo, seq = [int(x) for x in match.groups()]
        msg = read_message(page)
        record = {
            "year": yr,
            "month": mo,
            "seq": seq,
            "Subject": trim_subject_prefix(msg["Subject"]),
            "sender": msg["from"],
        }
        link = generate_link(record)
        if fragment:
            link += f"<br>&nbsp;&nbsp;&nbsp;&nbsp;... {fragment} ..."
        pages.append((f"{month_name[mo]} {yr}", link))
    if not pages:
        logging.root.info("Empty search result: %r", query)
    return pages


def init_redirect():
    app = current_app

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

        seq = f"{(int(mat.groups()[0]) + 1):04d}"
        return redirect(url_for("cr_message", year=year, month=month,
                                seq=seq),
                        code=301)

    @app.route('/<year>/<month>/<int:seq>')
    def bad_cr(year, month, seq):
        return redirect(url_for("cr_message", year=year, month=month, seq=f"{seq:04d}"),
                        code=301)

def init_extra():
    app = current_app

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
            "search_form": SearchForm(),
            "topic_form": TopicForm(),
            "query_form": QueryForm(),
        }

def init_debug():
    app = current_app

    @app.route("/version")
    def print_version():
        return jsonify(sys.version)

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

def init_search():
    app = current_app

    SRCHDB.set_database(app.config["SRCHDB"])

    @app.route('/search', methods=['GET', 'POST'])
    def search():
        search_form = SearchForm()
        if search_form.validate_on_submit():
            query = urllib.parse.quote_plus(f"{search_form.query.data}")
            query += f"+site:{search_form.site.data}"
            engine = SEARCH.get(search_form.engine.data, SEARCH["Brave"])
            return redirect(f"{engine}?q={query}")
        return render_template('cr.jinja', search_form=search_form)

    @app.route('/CR/query', methods=['GET', 'POST'])
    def query():
        query_form = QueryForm()
        page = 1
        size = 100
        if request.method == "GET":
            query = request.args.get("query", default=None)
            if query is None:
                return render_template('cr.jinja', form=query_form)
            query = urllib.parse.unquote_plus(query)
            page = request.args.get("page", default=1, type=int)
            size = request.args.get("pagesize", default=100, type=int)
            matches = query_index(query)
            # eprint("+++", query, len(matches), "GET")
        elif request.method == "POST":
            if query_form.validate_on_submit():
                query = urllib.parse.unquote_plus(f"{query_form.query.data}")
                matches = query_index(query)
                eprint("+++", query, len(matches), "POST")
            else:
                # eprint("+++ empty form")
                return render_template('cr.jinja', form=query_form)
        else:
            raise ValueError(f"Unrecognized request method {request.method}")

        prev_next = build_prev_next(query, matches, page, size)

        return render_template('page.jinja', matches=matches,
                               query=query, page=page, size=size,
                               prev_next=prev_next)


def build_prev_next(query, matches, page, size):
    "construct html fragment - eventually do this in jinja"
    qurl = urllib.parse.quote_plus(query)
    nxt = prv = ""
    cr_query = f"/CR/query?query={qurl}"
    if matches[page*size:]:
        nxt = f'<a href="{cr_query}&page={page+1}&size={size}">Next</a>'
    if matches[:(page-1)*size]:
        prv = f'<a href="{cr_query}&page={page}&size={size}">Prev</a>'

    if nxt and prv:
        prev_next = f"{prv} | {nxt}"
    elif nxt:
        prev_next = f"{nxt}"
    elif prv:
        prev_next = f"{prv}"
    else:
        prev_next = ""

    return prev_next

def init_topics():
    app = current_app

    @app.route('/CR/topics')
    @app.route('/CR/topics/<topic>')
    def show_topics(topic=""):
        "list topics or display entries for a specific topic"
        conn = ensure_db(app.config["REFDB"])
        cur = conn.cursor()
        cur.execute("""
          select distinct topic from topics
          order by topic
        """)
        topics = [t[0].split(":") for t in cur.fetchall()]

        make_topic_hierarchy(topics, htopics:={}, "")

        if not topic:
            msgrefs = []
        else:
            msgrefs=[(yr, mo, seq, trim_subject_prefix(subj), sender)
                        for (yr, mo, seq, subj, sender) in
                           get_topic(f"{topic}%", conn)]
        return render_template("topics.jinja", topics=topics, msgrefs=msgrefs,
                               topic=topic, htopics=htopics)

    @app.route('/CR/addtopic', methods=['GET', 'POST'])
    def addtopic():
        "display/process form to associate topics with a message."
        topic_form = TopicForm()
        if topic_form.validate_on_submit():
            topic = urllib.parse.unquote_plus(f"{topic_form.topic.data}")
            year = topic_form.year.data
            month = topic_form.month.data
            seq = topic_form.seq.data

            conn = sqlite3.connect(app.config["REFDB"])
            cur = conn.cursor()
            cur.execute("""
            select messageid from messages
              where year = ?
                and month = ?
                and seq = ?
            """, (year, month, seq))
            msgid = cur.fetchone()[0]
            save_topic_record({
                "topic": topic,
                "year": year,
                "month": month,
                "seq": seq,
                "message-id": msgid,
            })
            # pylint: disable=undefined-variable
            return email_to_html(year=int(topic_form.year.data, 10),
                                 month=int(topic_form.month.data, 10),
                                 seq=topic_form.seq.data,
                                 note="Thanks for your submission.")
        return render_template('cr.jinja', topic_form=topic_form)


    def save_topic_record(record):
        "write submitted topic details to CSV file."
        fieldnames = ["topic", "message-id", "year", "month", "seq", "ip"]
        topicfile = app.config["TOPICFILE"]
        record["ip"] = (request.environ.get("HTTP_X_REAL_IP") or
                        request.environ.get("REMOTE_ADDR") or
                        "unknown")
        writeheader = (not os.path.exists(topicfile) or
                       os.path.getsize(topicfile) == 0)
        with open_(topicfile, "a", encoding="utf-8") as fobj:
            writer = csv.DictWriter(fobj, fieldnames)
            if writeheader:
                writer.writeheader()
            writer.writerow(record)

def next_msg(year, month, seq, incr):
    "provide next or prev message in sequence (according to incr)"
    CR = current_app.config["CR"]
    monthdir = os.path.join(CR, f"{year:04d}-{month:02d}", "eml-files")
    seq += incr
    files = sorted(glob.glob(os.path.join(monthdir, "*.eml")))
    # Fast path. This happens almost all the time.
    msg = os.path.join(monthdir, eml_file(year, month, seq))
    if msg in files:
        return {
            "year": year,
            "month": month,
            "seq": seq,
        }

    # Intermediate path - a gap in files, but the one we want is
    # in the list.
    if incr == -1:
        # We want the maximum file which is less than msg.
        lt_files = [f for f in files if f < msg]
        if lt_files:
            f = lt_files[-1]
            seq = int(f.split(".")[-2], 10)
            return {
                "year": year,
                "month": month,
                "seq": seq,
            }
    else:
        # We want the minimum file which is greater than msg.
        gt_files = [f for f in files if f > msg]
        if gt_files:
            f = gt_files[0]
            seq = int(f.split(".")[-2], 10)
            return {
                "year": year,
                "month": month,
                "seq": seq,
            }

    # Slow path
    # move forward or back one month
    dt = datetime.date(year, month, 15) + incr * 20 * ONE_DAY
    year = dt.year
    month = dt.month
    while OLDEST_MONTH <= (year, month) <= NEWEST_MONTH:
        monthdir = os.path.join(CR, f"{year:04d}-{month:02d}", "eml-files")
        files = sorted(glob.glob(os.path.join(monthdir, "*.eml")))
        if files:
            msg = files[-1] if incr == -1 else files[0]
            seq = int(msg.split(".")[-2], 10)
            return {
                "year": year,
                "month": month,
                "seq": seq,
            }
        dt = datetime.date(year, month, 15) + incr * 20 * ONE_DAY
        year = dt.year
        month = dt.month

    raise ValueError("No next/prev message found")

def get_nav_items(*, year, month, seq):
    "navigation items related to the argument message."
    items = []
    if not isinstance(seq, int):
        seq = int(seq, 10)
    items.append(("Date Index", url_for("dates",
                                        year=year,
                                        month=f"{month:02d}") + f"#{seq:04d}"))
    items.append(("Thread Index", url_for("threads",
                                          year=year,
                                          month=f"{month:02d}") + f"#{seq:04d}"))
    try:
        prev_seq = next_msg(year, month, seq, -1)
    except ValueError:
        pass
    else:
        items.append(("Prev", url_for("cr_message", **prev_seq)))
    try:
        next_seq = next_msg(year, month, seq, +1)
    except ValueError:
        pass
    else:
        items.append(("Next", url_for("cr_message", **next_seq)))

    return items

class TopicForm(FlaskForm):
    "simple form used to add topics to a message"
    topic = StringField('Add Topic(s):', validators=[DataRequired()])
    year = HiddenField('year')
    month = HiddenField('month')
    seq = HiddenField('seq')

class SearchForm(FlaskForm):
    "simple form used to search Brave for archived list messages"
    query = StringField('Search:', validators=[DataRequired()])
    site = HiddenField('site', default='smontanaro.net')
    engine = SelectField('Engine:', choices=[
        ('Brave', 'Brave'),
        ('DuckDuckGo', 'DuckDuckGo'),
        ('Bing', 'Bing'),
        ('Google', 'Google'),
        ('Neeva', 'Neeva'),
    ], default='Brave')

class QueryForm(FlaskForm):
    "simple query form used to search for indexed phrases"
    query = StringField('Search:', validators=[DataRequired()])

def eml_file(year, month, seq):
    "compute email file from sequence number"
    # MHonARC was written in Perl, so of course Y2k
    perl_yr = year - 1900
    return f"classicrendezvous.{perl_yr:3d}{month:02d}.{seq:04d}.eml"

# pylint: disable=too-few-public-methods
class MessageFilter:
    "filter various uninteresting bits from messages"
    def __init__(self, message):
        self.message = message
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


def init_app(app):
    with app.app_context():
        init_simple()
        init_indexes()
        init_cr()
        init_redirect()
        init_extra()
        init_search()
        init_topics()
        # init_bh()

        if app.config["DEBUG"]:
            print("Debug mode enabled.")
            init_debug()
