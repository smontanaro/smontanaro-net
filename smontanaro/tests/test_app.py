import csv
import os
import re
import shutil
import tempfile
import urllib.parse

import dateutil.parser
import pytest
from flask import session

from smontanaro import create_app
from smontanaro.refdb import ensure_db
from smontanaro.dates import parse_date
from smontanaro.util import (read_message, read_message_string,
                             trim_subject_prefix, eprint, open_)
from smontanaro.views import MessageFilter, eml_file
from smontanaro.strip import strip_footers, strip_leading_quotes
from smontanaro.srchdb import ensure_search_db, get_page_fragments

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

def test_toss_filter(client):
    "check that we eliminate stuff we don't want but keep stuff we do"
    rv = client.post("/CR/filter_date", data={
        "pattern": "ebay",
        "in_out": "toss",
        "year": "2005",
        "month": "09",
        })
    assert rv.status_code == 302
    session["pattern"] = "ebay"
    session["in_out"] = "toss"
    rv = client.get("/CR/2005/06/dates")
    assert rv.status_code == 200
    assert (re.search(b"<li>.*ebay", rv.data, re.I) is None and
            re.search(b"01 Jun 2005", rv.data) is not None)

def test_keep_filter(client):
    "check that we keep stuff we ask to keep"
    rv = client.post("/CR/filter_date", data={
        "pattern": "Campagnolo",
        "in_out": "keep",
        "year": "2005",
        "month": "09",
        })
    assert rv.status_code == 302
    session["pattern"] = "Campagnolo"
    session["in_out"] = "keep"
    rv = client.get("/CR/2005/09/dates")
    assert re.search(b"01 Sep 2005", rv.data) is not None
    for line in rv.data.split(b"\n"):
        if b'<li>' in line:
            assert re.search(b"<li>.*Campagnolo", line, re.I) is not None

def test_toss_everything(client):
    "check that we keep stuff we ask to keep"
    rv = client.post("/CR/filter_date", data={
        "pattern": "Colnago",
        "in_out": "keep",
        "year": "2001",
        "month": "10",
        })
    assert rv.status_code == 302
    session["pattern"] = "Colnago"
    session["in_out"] = "keep"
    rv = client.get("/CR/2001/10/dates")
    assert re.search(b"Oct 2001 Date Index", rv.data) is not None
    assert b"Pretty brutal filter, eh?" in rv.data

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

def test_filter_nodate(client):
    "check that we keep stuff we ask to keep"
    cache_dir = "CR/generated/cache"
    # First time, guarantee cache is missing
    shutil.rmtree(cache_dir, ignore_errors=True)
    rv = client.post("/CR/filter_date", data={
        "pattern": "Colnago",
        "in_out": "keep",
        })
    assert rv.status_code == 302
    session["pattern"] = "Colnago"
    session["in_out"] = "keep"
    # Second time, cache_dir should be there
    rv = client.post("/CR/filter_date", data={
        "pattern": "Colnago",
        "in_out": "keep",
        })
    assert rv.status_code == 302
    session["pattern"] = "Colnago"
    session["in_out"] = "keep"
    rv = client.get("/CR/2001/10/dates")
    assert re.search(b"Oct 2001 Date Index", rv.data) is not None
    assert b"Pretty brutal filter, eh?" in rv.data

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

def test_under_paren_urlmap(client):
    msg = read_message("CR/2005-01/eml-files/classicrendezvous.10501.1670.eml")
    url = "http://www.moots.com/messages/1040.shtml"
    with client.application.app_context():
        filt = MessageFilter(msg)
        filt.filter_message(msg)
        filt.delete_empty_parts()
        text = msg.as_html()
        # need to mimic the path splitting of long urls (see Message.map_url)
        split = (urllib.parse.urlsplit(url))
        br_url = split._replace(path=split.path.replace("/", "/<wbr>")).geturl()
        assert (br_url in text and
                f"_{url}_" not in text and
                f"({url})" not in text)

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

def test_fmt_sig1(client):
    with client.application.app_context():
        msg = read_message("CR/2010-07/eml-files/classicrendezvous.11007.0144.eml")
        html = msg.as_html()
        assert ("<br>Ted Ernst" in html and
                "<br>Palos Verdes Estates" in html and
                "<br>CA  USA" in html)

def test_fmt_sig2(client):
    with client.application.app_context():
        msg = read_message("CR/2009-03/eml-files/classicrendezvous.10903.0134.eml")
        html = msg.as_html()
        assert ("<br>Ted Ernst" in html and
                "<br>Palos Verdes Estates" in html and
                "<br>CA  USA" in html)

def test_para_split(client):
    with client.application.app_context():
        msg = read_message("CR/2009-03/eml-files/classicrendezvous.10903.0144.eml")
        payload = msg.get_payload(decode=True)
        payload = msg.decode(payload)
        payload = strip_leading_quotes(strip_footers(payload))
        msg.set_payload(payload)
        html = msg.as_html()
        assert html.count("<p>") == 10, html

EMPTY_MAIL = """\
x-sender: classicrendezvous-bounces@bikelist.org
x-receiver: classicrendezvous-index@archive.nt.phred.org
Received: from phred.org ([172.16.1.2]) by monkeyfood.nt.phred.org with Microsoft SMTPSVC(6.0.3790.3959);
	 Wed, 4 Mar 2009 16:11:55 -0800
Return-Path: <passionateyouththing@yahoo.com>
Delivered-To: classicrendezvous@bikelist.org
Received: from monkeyfood.nt.phred.org (unknown [172.16.1.15])
	by phred.org (Postfix) with ESMTP id 51A5A5E58
	for <classicrendezvous@bikelist.org>;
	Wed,  4 Mar 2009 16:12:02 -0800 (PST)
Received: from exchange12.nt.phred.org ([172.16.1.12]) by
	monkeyfood.nt.phred.org with Microsoft SMTPSVC(6.0.3790.3959);
	Wed, 4 Mar 2009 16:11:53 -0800
Received: from web53307.mail.re2.yahoo.com (206.190.49.97) by
	exchange12.nt.phred.org (172.16.1.12) with Microsoft SMTP Server id
	8.1.340.0; Wed, 4 Mar 2009 16:11:53 -0800
Received: (qmail 35315 invoked by uid 60001); 5 Mar 2009 00:12:01 -0000
DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed; d=yahoo.com; s=s1024;
	t=1236211921; bh=hP0oGBClEX04Rfe+6lljF+q4iyvtpU8SEWEnG7POrDg=;
	h=Message-ID:X-YMail-OSG:Received:X-Mailer:Date:From:Reply-To:Subject:To:MIME-Version:Content-Type;
	b=M21EUndi0GGrNM73SMGE7gD93ff9FbrK39uaCZizJHVS34w/QknNJUm0ai0jkLtroXrjXw3gfb7bkrNt72oyUTf1aN+k5wvBTCPFnzgZD9DquUuwyNG8sldC+JdB/ac7u8ehufTlkEYsvIDaDmP7uI2lM/Sve+ETBAwQHz+Oqz8=
DomainKey-Signature: a=rsa-sha1; q=dns; c=nofws; s=s1024; d=yahoo.com;
	h=Message-ID:X-YMail-OSG:Received:X-Mailer:Date:From:Reply-To:Subject:To:MIME-Version:Content-Type;
	b=Ws3x1HtnY4I1zWqDwCLah+2/ivDaaUJ5XFQVLVRHm07CiDWMebEcp4ozE/XnBgGzZs/mo+cU27yoKOV4yowzIp6OoY0YmgykrfCYBFFyrzBnfmzye/Eqe8JUxELsaLTwzpP14BHGbT54phyXWvp91HV+zhGl6y7DN6q1R2xwMrg=;
Message-ID: <488976.31337.qm@web53307.mail.re2.yahoo.com>
X-YMail-OSG: jA_slkMVM1nmPFTijVNzuU8v3H8ResFKerC2mlYmbP7Hnp68pG3nydRic6Xxb3KqELsnOfilNE469vpu76r7wweXHzXDlRzAObxVT1Lt.N7MhrqLF6bcKIOtDkylFVuKgBM2gPlLB4BiXon03kgAqXk6gw--
Received: from [129.7.156.181] by web53307.mail.re2.yahoo.com via HTTP; Wed,
	04 Mar 2009 16:12:01 PST
X-Mailer: YahooMailWebService/0.7.289.1
Date: Wed, 4 Mar 2009 16:12:01 -0800
From: Kirke Campbell <passionateyouththing@yahoo.com>
To: <classicrendezvous@bikelist.org>
MIME-Version: 1.0
Received-SPF: None (exchange12.nt.phred.org: passionateyouththing@yahoo.com
	does not designate permitted sender hosts)
X-OriginalArrivalTime: 05 Mar 2009 00:11:53.0906 (UTC)
	FILETIME=[FD32E920:01C99D26]
X-StripMime: Non-text section removed by stripmime
Subject: [CR] FS: 3TTT stems, Maillard hubs, BB's...
X-BeenThere: classicrendezvous@bikelist.org
X-Mailman-Version: 2.1.11
Precedence: list
Reply-To: passionateyouththing@yahoo.com
List-Id: A sharing of vintage lightweight bicycle information and lore
	<classicrendezvous.bikelist.org>
List-Unsubscribe: <http://www.bikelist.org/mailman/options/classicrendezvous>,
	<mailto:classicrendezvous-request@bikelist.org?subject=unsubscribe>
List-Archive: <http://www.bikelist.org/pipermail/classicrendezvous>
List-Post: <mailto:classicrendezvous@bikelist.org>
List-Help: <mailto:classicrendezvous-request@bikelist.org?subject=help>
List-Subscribe: <http://www.bikelist.org/mailman/listinfo/classicrendezvous>,
	<mailto:classicrendezvous-request@bikelist.org?subject=subscribe>
Content-Type: x-unknown/plain
Content-Transfer-Encoding: 7bit
Sender: classicrendezvous-bounces@bikelist.org
Errors-To: classicrendezvous-bounces@bikelist.org






--- StripMime Report -- processed MIME parts ---
multipart/alternative
  text/plain (text body -- kept)
  text/html
---
_______________________________________________
Classicrendezvous mailing list
Classicrendezvous@bikelist.org
http://www.bikelist.org/mailman/listinfo/classicrendezvous
"""


def test_empty_payload(client):
    with client.application.app_context():
        msg = read_message_string(EMPTY_MAIL)
        payload = msg.get_payload(decode=True)
        payload = msg.decode(payload)
        payload = strip_footers(payload)
        assert not payload, payload


def test_subject_fix(client):
    msg = read_message("CR/2000-11/eml-files/classicrendezvous.10011.1036.eml")
    assert msg["Subject"] == "[CR] Danger, items for sale"

def test_long_url_fix(client):
    with client.application.app_context():
        msg = read_message("CR/2010-05/eml-files/classicrendezvous.11005.1410.eml")
        payload = msg.get_payload(decode=True)
        payload = msg.decode(payload)
        payload = strip_footers(payload)
        msg.set_payload(payload)
        html = msg.as_html()
        assert "/<wbr>FoldingATubularTire" in html

def test_vintage_trek(client):
    with client.application.app_context():
        rv = client.get("/vintage-trek/Trekpromoa.htm")
        assert rv.status_code == 200


def test_query_get(client):
    with client.application.app_context():
        rv = client.get("/CR/query?page=3&query='faliero+masi'&size=20")
        assert rv.status_code == 200


def test_low_level_query(client):
    with client.application.app_context():
        conn = ensure_search_db(client.application.config["SRCHDB"])
        for (filename, fragment) in get_page_fragments(conn, "faliero masi"):
            assert filename
            assert fragment
            break
        else:
            raise ValueError("no search results")


def test_from_query(client):
    with client.application.app_context():
        conn = ensure_search_db(client.application.config["SRCHDB"])
        for (filename, fragment) in get_page_fragments(conn, "from:mark petry"):
            assert filename
            assert not fragment
            break
        else:
            raise ValueError("no search results")


def test_query_post_arg(client):
    with client.application.app_context():
        rv = client.post("/CR/query", data={
            "query": "colnago",
        })
        assert rv.status_code == 200

def test_query_post_empty(client):
    with client.application.app_context():
        rv = client.post("/CR/query", data={})
        assert rv.status_code == 200


def test_unknown_content_type(client):
    msg = read_message_string(EMPTY_MAIL)
    maintype = msg.get_content_maintype()
    assert maintype not in ("image", "text", "multipart"), msg.get_content_type()
    try:
        x = msg.as_html()
    except ValueError:
        pass


def test_eprint(client):
    eprint("Hello World!", file=open_(os.devnull, "w"))
