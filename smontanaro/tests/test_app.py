import csv
import os
import re
import tempfile

import dateutil.parser
import pytest

from smontanaro import create_app
from smontanaro.db import ensure_db
from smontanaro.dates import parse_date
from smontanaro.util import read_message, trim_subject_prefix
from smontanaro.views import MessageFilter, eml_file

@pytest.fixture
def client():
    topic_fd, topic_path = tempfile.mkstemp()
    app = create_app(
        {"TESTING": True,
         "REFDB": "references.db",
         "WTF_CSRF_ENABLED": False,
         "TOPICFILE": topic_path,
         "SERVER_NAME": "smontanaro.net",
         }
    )

    with app.test_client() as client:
        with app.app_context():
            ensure_db(app.config["REFDB"])
        yield client

    os.close(topic_fd)
    os.unlink(topic_path)

def test_parse_date(client):
    for (timestring, exp) in (
            ("Date: Mon, 26 Jan 2004 21:33:19 -0800 (PST)\n",
             dateutil.parser.parse("2004-01-26T21:33:19 -0800")),
            ("Date: 26 Jan 2004 21:33:19 America/Los_Angeles",
             dateutil.parser.parse("2004-01-26T21:33:19 -0800")),
            ):
        assert parse_date(timestring) == exp

def test_fresh_db(client):
    db_fd, db_path = tempfile.mkstemp()
    with client.application.app_context():
        ensure_db(db_path)
    os.close(db_fd)
    os.unlink(db_path)

def test_get_robots(client):
    rv = client.get("/robots.txt")
    assert rv.status_code == 302

def test_post_search(client):
    rv = client.post("/search", data={
        "query": "Faliero",
        "engine": "Brave",
        })
    assert rv.status_code == 302

@pytest.mark.skip(reason="flask test harness issues")
def test_toss_filter(client):
    "check that we eliminate stuff we don't want but keep stuff we do"
    with client.application.test_request_context("/CR/filter_date") as ctx:
        rv = client.post("/CR/filter_date", data={
            "pattern": "ebay",
            "in_out": "toss",
            "year": "2005",
            "month": "09",
            })
        assert rv.status_code == 302
        ctx.session["pattern"] = "ebay"
        ctx.session["in_out"] = "toss"
        rv = client.get("/CR/2005/06/dates")
        assert rv.status_code == 200
        assert (re.search(b"<li>.*ebay", rv.data, re.I) is None and
                re.search(b"01 Jun 2005", rv.data) is not None)

@pytest.mark.skip(reason="flask test harness issues")
def test_keep_filter(client):
    "check that we keep stuff we ask to keep"
    with client.application.test_request_context("/CR/filter_date") as ctx:
        rv = client.post("/CR/filter_date", data={
            "pattern": "Campagnolo",
            "in_out": "keep",
            "year": "2005",
            "month": "09",
            })
        assert rv.status_code == 302
        ctx.session["pattern"] = "Campagnolo"
        ctx.session["in_out"] = "keep"
        rv = client.get("/CR/2005/09/dates")
        assert re.search(b"01 Sep 2005", rv.data) is not None
        for line in rv.data.split("\n"):
            assert re.search(b"<h2|<ul|<li>.*Campagnolo", line) is not None

@pytest.mark.skip(reason="flask test harness issues")
def test_toss_everything(client):
    "check that we keep stuff we ask to keep"
    with client.application.test_request_context("/CR/filter_date") as ctx:
        rv = client.post("/CR/filter_date", data={
            "pattern": "Colnago",
            "in_out": "keep",
            "year": "2001",
            "month": "10",
            })
        assert rv.status_code == 302
        ctx.session["pattern"] = "Colnago"
        ctx.session["in_out"] = "keep"
        rv = client.get("/CR/2001/10/dates")
        assert re.search(b"Oct 2001 Date Index", rv.data) is not None
        for line in rv.data.split("\n"):
            assert re.search(b"Colnago", line) is None

def test_suggest_topic(client):
    "check that topics.csv is updated when a topic is suggested."
    rv = client.post("/CR/addtopic", data={
        "topic": "Sturmey-Archer",
        "year": "2005",
        "month": "09",
        "seq": "0001",
        })
    assert rv.status_code == 200
    # Add a second suggestion to test both branches of "if writeheader:"...
    rv = client.post("/CR/addtopic", data={
        "topic": "Sturmey-Archer",
        "year": "2005",
        "month": "09",
        "seq": "0001",
        })
    assert rv.status_code == 200
    rdr = csv.DictReader(open(client.application.config["TOPICFILE"]))
    row = next(rdr)
    assert (row["topic"] == "Sturmey-Archer" and
            row["message-id"] == "<7e.703e8851.30481dcb@aol.com>")

def test_read_message(client):
    "read a message, then a second time to get the pickled version"
    mfile = "CR/2008-12/eml-files/classicrendezvous.10812.0831.eml"
    pfile = os.path.splitext(mfile)[0] + ".pck.gz"
    try:
        os.unlink(pfile)
    except FileNotFoundError:
        pass
    msg1 = read_message(mfile)
    assert os.path.exists(pfile)
    msg2 = read_message(mfile)
    assert msg1.as_string() == msg2.as_string()

def test_message_strip(client):
    "verify the yellowpages footer disappears"
    msg = read_message("CR/2005-10/eml-files/classicrendezvous.10510.0508.eml")
    with client.application.app_context():
        filt = MessageFilter(msg)
        filt.filter_message(msg)
        filt.delete_empty_parts()
        assert "yellowpages.lycos.com" not in msg.as_string()

def test_message_strip_same_header_footer(client):
    "virginmedia stripper uses the same header and footer"
    msg = read_message("CR/2007-07/eml-files/classicrendezvous.10707.0004.eml")
    with client.application.app_context():
        filt = MessageFilter(msg)
        filt.filter_message(msg)
        filt.delete_empty_parts()
        assert "virginmedia.com" not in msg.as_string()

def test_next_msg(client):
    "make sure we can hop over gaps and between months"
    with client.application.app_context():
        from smontanaro.views import next_msg
        # intramonth gap at (2003, 8, 31)
        assert next_msg(2003, 8, 32, -1)["seq"] == 30
        # normal case
        assert next_msg(2003, 8, 382, -1)["seq"] == 381
        assert next_msg(2003, 8, 382, +1)["seq"] == 383
        # previous month
        result = next_msg(2003, 8, 1, -1)
        assert result["month"] == 7 and result["seq"] == 1216
        # next month
        result = next_msg(2003, 7, 1216, +1)
        assert result["month"] == 8 and result["seq"] == 1

def test_trim_subj():
    mfile = "CR/2001-01/eml-files/classicrendezvous.10101.0091.eml"
    msg = read_message(mfile)
    exp = "Cinelli Myths � aluminium bars, fastback seatstay design"
    assert trim_subject_prefix(msg["Subject"]) == exp

def test_eml_file():
    for exp, args in [
            ("classicrendezvous.10509.1592.eml", (2005, 9, 1592)),
            ("classicrendezvous.10509.0001.eml", (2005, 9, 1)),
            ("classicrendezvous.10509.0123.eml", (2005, 9, 123)),
    ]:
        assert exp == eml_file(*args)
