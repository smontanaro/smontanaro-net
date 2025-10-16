#!/usr/bin/env python3

"The really simple stuff, not really related to old CR archives."

import datetime
import os
import urllib.parse

from flask import redirect, url_for, render_template, request, send_from_directory, current_app
import requests

from .forms import PhotoForm
# from .log import eprint
from .util import GooglePhotoParser


def init_simple():
    app = current_app
    @app.route("/favicon.ico")
    def favicon():
        "websites need these"
        return redirect(url_for("static", filename="images/favicon.ico"))

    @app.route("/robots.txt")
    def robots():
        "websites need these"
        return redirect(url_for("static", filename="txt/robots.txt"))

    @app.route("/sitemap.xml")
    def sitemap():
        "websites need these"
        return redirect(url_for("static", filename="txt/sitemap.xml"))

    @app.route("/python/<filename>")
    def python_redir(filename):
        "adjust to structural change in website"
        return redirect(url_for("static", filename=f"python/{filename}"))

    @app.route("/sitemap_index.xml")
    def sitemap_index():
        "websites need these"
        return redirect(url_for("static", filename="txt/sitemap_index.xml"))

    @app.route("/")
    def index():
        "index"
        return render_template("main.jinja", title="Home")

    @app.route("/photolink/help")
    def photolink_help_():
        "websites need these"
        return render_template("help-photolink.jinja")

    @app.route("/calendar")
    def cal_reroute():
        return redirect(url_for("calendar"))

    @app.route("/calendar/today")
    def calendar_today():
        dt = datetime.date.today()
        return redirect(url_for("calendar", year=dt.year, month=dt.month, day=dt.day))

    @app.route("/calendar/")
    @app.route("/calendar/<int:year>")
    @app.route("/calendar/<int:year>/<int:month>/<int:day>")
    def calendar(year=10**22, month=0, day=0):
        "One-page calendar"
        error = ""

        if year != 10**22 and month > 0 and day > 0:
            try:
                date = datetime.date(year, month, day)
            except ValueError as exc:
                date = datetime.date.today()
                error = f"Invalid date: {year:4d}-{month:02d}-{day:02d} {exc}"
        else:
            date = datetime.date.today()

        if year == 10**22:
            year = date.year

        today = year == date.year

        months = get_month_table(year)
        classes = get_class_table(date, today, months)

        return render_template("calendar.jinja", year=year, months=months,
                               classes=classes, error=error)

    @app.post("/photolink")
    def photolink_POST():
        form = PhotoForm()
        if form.validate_on_submit():
            return _photolink_internal(url=form.url.data, width=form.width.data,
                                       fmt=form.fmt.data, form=form)
        # eprint(form.errors)
        return render_template('photo.jinja',
                               reference="", error="",
                               title="Google Photo Link Form",
                               form=form)

    @app.get("/photolink")
    def photolink_GET():
        form = PhotoForm()
        url = request.args.get("url")
        if url is None:
            return render_template('photo.jinja', form=form,
                                   error="", reference="")
        return _photolink_internal(url=urllib.parse.unquote_plus(url),
                                   width=request.args.get("width", default=""),
                                   fmt=request.args.get("fmt", default="bbcode"),
                                   form=form)

    def _photolink_internal(*, url, width, fmt, form):
        # eprint(f"+++ url: {url}")
        # eprint(f"+++ width: {width}")
        # eprint(f"+++ fmt: {fmt}")

        html = GooglePhotoParser()
        try:
            response = requests.get(url, timeout=10)
        except requests.exceptions.ConnectionError:
            return render_template('photo.jinja', form=form,
                                   error=f"Invalid URL: {url}",
                                   reference="",
                                   title="Google Photo Link Form")
        if response.status_code == 200:
            html.feed(response.text)
        if not html.ref:
            return render_template('photo.jinja', form=form,
                                   error="No image reference found",
                                   reference="",
                                   title="Google Photo Link Form")

        if width:
            html.ref += f"=w{width}"
        match fmt.lower():
            case "html":
                reference = (f'&lt;a href={url}&gt;&#8203;'
                             f'&lt;img src="{html.ref}" /&gt;&lt;/a&gt;')
            case "bbcode":
                reference = f"[url={url}][img]{html.ref}[/img][/url]"
            case "raw":
                reference = html.ref

        return render_template('photo.jinja', form=form,
                               reference=reference, error="",
                               title="Google Photo Link Form")

    @app.route("/43bikes")
    def bike_reroute():
        return redirect(url_for("bikes_43"))

    @app.route("/43bikes/")
    @app.route("/43bikes/<path:path>")
    def bikes_43(path="index.html"):
        "static replica sites"
        vtdir = f"{os.environ.get('CRDIR')}/smontanaro/smontanaro/static/bikes"
        return send_from_directory(vtdir, os.path.join("43bikes", path))

    @app.route("/vintage-trek")
    def trek_reroute():
        return redirect(url_for("vintage_trek"))

    @app.route("/vintage-trek/")
    @app.route("/vintage-trek/<path:path>")
    def vintage_trek(path="index.html"):
        "static replica sites"
        vtdir = f"{os.environ.get('CRDIR')}/smontanaro/smontanaro/static/bikes"
        return send_from_directory(vtdir, os.path.join("vintage-trek", path))

def get_month_table(year):
    "return months table for the given year"
    months = [
        [" ", " ", " ", " ", " ", " ", " ", ],
        [" ", " ", " ", " ", " ", " ", " ", ],
        [" ", " ", " ", " ", " ", " ", " ", ],
        [" ", " ", " ", " ", " ", " ", " ", ],
        ]

    for m in range(1, 13):
        dt = datetime.date(year, m, 1)
        # This computes row index into months[i]. Sunday == 6 is the zeroth
        # cell.
        weekday = (dt.weekday() + 1) % 7
        for i in range(4):
            if months[i][weekday] == " ":
                months[i][weekday] = dt.strftime("%b")
                break

    return months

def get_class_table(date, today, months):
    "populate css class table"
    classes = []
    for _row in range(12):
        classes.append([])
        for _col in range(13):
            classes[-1].append("calendar")

    if today:
        # adjust calendar class to display today's month and date in red.
        ## day
        row = (date.day - 1) % 7 + 4
        col = (date.day - 1) // 7
        classes[row][col] += " calendar_today"
        ## month
        col = ""
        for i in range(4):
            for j in range(7):
                if months[i][j] == date.strftime("%b"):
                    classes[i][j+5] += " calendar_today"
                    col = j + 5
                    break
            if col:
                break
        # day of the week
        classes[row][col] += " calendar_today"

    return classes

def init_app(app):
    with app.app_context():
        init_simple()
