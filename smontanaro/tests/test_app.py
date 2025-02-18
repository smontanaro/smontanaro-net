"unit tests"

import csv
import os
import shutil
import tempfile
import time
import urllib.parse

import dateutil.parser
from flask import current_app, url_for
import regex as re
import pytest
from pytest import mark as _mark
pyt_parameterize = _mark.parametrize

from smontanaro.dates import parse_date
from smontanaro.log import eprint
from smontanaro.refdb import ensure_db
from smontanaro.srchdb import SRCHDB
from smontanaro.strip import (strip_footers, strip_leading_quotes,
                              rewrite_ebay_urls)
from smontanaro.util import (read_message, read_message_string, parse_from,
                             trim_subject_prefix, open_, all_words,
                             EXCEPTIONS)
from smontanaro.views import (MessageFilter, eml_file, query_index, next_msg,
                              get_nav_items)

from _test_helper import client

# pytest's use (and apparent requirement) of client as both an outer name and
#   argument necessitates this

# pylint: disable=redefined-outer-name

def test_parse_date():
    for (timestring, exp) in (
            ("Date: Mon, 26 Jan 2004 21:33:19 -0800 (PST)\n",
             dateutil.parser.parse("2004-01-26T21:33:19 -0800")),
            ("Date: 26 Jan 2004 21:33:19 America/Los_Angeles",
             dateutil.parser.parse("2004-01-26T21:33:19 -0800")),
            ("Date: 2010-06-27, 6:06PM CDT",
             dateutil.parser.parse("2010-06-27T18:06:00 -0500")),
            ):
        assert parse_date(timestring) == exp

def test_fresh_db(client):
    db_fd, db_path = tempfile.mkstemp()
    with client.application.app_context():
        ensure_db(db_path)
    os.close(db_fd)
    os.unlink(db_path)

@pyt_parameterize("yr, mo, prv, nxt",
                  [
                   # beginning
                   (2000, 3, "", "/CR/2000/6/dates"),
                   # middle with a gap
                   (2000, 6, "/CR/2000/3/dates", "/CR/2000/8/dates"),
                   # end
                   (2011, 2, "/CR/2011/1/dates", ""),
                   # middle without a gap, but non-integer month
                   (2003, "6", "/CR/2003/5/dates", "/CR/2003/7/dates"),
                   ])
def test_get_nav_items(client, yr, mo, prv, nxt):
    with client.application.app_context():
        rv = client.get(f"/CR/{yr}/{mo}/dates")
        assert rv.status_code == 200
        page = rv.text
        if prv and nxt:
            assert len(re.findall("/CR/[0-9]+/[0-9]+/dates", page)) == 2
        else:
            assert len(re.findall("/CR/[0-9]+/[0-9]+/dates", page)) == 1
        if prv:
            assert prv in page
        if nxt:
            assert nxt in page

@pyt_parameterize("yr, mo, seq",
                  [
                   (2001, 3, "1",),
                   (2001, 3, 12,),
                   (2011, 2, 1643,),
                   ])
def test_get_nav_items2(client, yr, mo, seq):
    exp_keys = {"Date Index", "Thread Index", "Prev", "Next"}
    with client.application.app_context():
        items = dict(get_nav_items(year=yr, month=mo, seq=seq))
        assert "Date Index" in items and "Thread Index" in items
        if "Prev" in items:
            assert items["Prev"] == url_for("cr_message",
                                            **next_msg(yr, mo, int(seq), -1))
        if "Next" in items:
            assert items["Next"] == url_for("cr_message",
                                            **next_msg(yr, mo, int(seq), +1))

def test_get_version(client):
    rv = client.get("/version")
    assert rv.status_code == 200

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
    with open(client.application.config["TOPICFILE"], encoding="utf-8") as fobj:
        rdr = csv.DictReader(fobj)
        row = next(rdr)
        assert (row["topic"] == "Sturmey-Archer" and
                row["message-id"] == "<7e.703e8851.30481dcb@aol.com>")

def test_read_message(client):
    "read a message, then a second time to get the pickled version"
    with client.application.app_context():
        mfile = eml_file(2002, 10, 759)
        pfile = os.path.splitext(mfile)[0] + ".pck.gz"
        if os.path.exists(pfile):
            os.unlink(pfile)
        msg1 = read_message(mfile)
        assert os.path.exists(pfile)
        msg2 = read_message(mfile)
        assert msg1.as_string() == msg2.as_string()

def _test_read_busted_helper(tmpdir):
    emlfile = os.path.join(tmpdir, "msg.eml")
    pckgzfile = os.path.join(tmpdir, "msg.pck.gz")
    with open_(emlfile, "w", encoding="utf-8") as fobj:
        fobj.write(EMPTY_MAIL)
    msg1 = read_message(emlfile)
    assert os.path.exists(pckgzfile)

    # read and write most of the bytes in the pckgz file
    with open_(pckgzfile, "rb") as fobj:
        bits = fobj.read()[:-100]
    with open_(pckgzfile, "wb") as fobj:
        fobj.write(bits)

    pcktime1 = os.path.getmtime(pckgzfile)
    time.sleep(1.1)

    # re-read, pckgz file should get EOFError, then get rewritten after the eml
    # file is read.
    msg2 = read_message(emlfile)
    assert os.path.exists(pckgzfile)
    pcktime2 = os.path.getmtime(pckgzfile)

    assert pcktime2 > pcktime1
    assert msg1.as_string() == msg2.as_string()

def test_read_busted_pickle():
    "save a message, read it, then corrupt the pckgz file and read again"
    tmpdir = tempfile.mkdtemp()
    try:
        _test_read_busted_helper(tmpdir)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_under_paren_urlmap(client):
    save_debug = client.application.config["DEBUG"]
    try:
        for debug in (True, False):
            client.application.config["DEBUG"] = debug
            url = "http://www.moots.com/messages/1040.shtml"
            with client.application.app_context():
                msg = read_message(eml_file(2005, 1, 1670))
                filt = MessageFilter(msg)
                filt.filter_message(msg)
                text = msg.as_html()
                # need to mimic the path splitting of long urls (see Message.map_url)
                split = (urllib.parse.urlsplit(url))
                br_url = split._replace(path=split.path.replace("/", "/<wbr>")).geturl()
                assert (br_url in text and
                        f"_{url}_" not in text and
                        f"({url})" not in text)
    finally:
        client.application.config["DEBUG"] = save_debug

def test_map_url(client):
    with client.application.app_context():
        # any old message will do (I think)
        msg = read_message(eml_file(2005, 1, 1670))
        domain = "www.wooljersey.com"
        word = f"&lt;{domain}&gt;"
        assert f'"http://{domain}"' in msg.map_url(word)

@pyt_parameterize("yr, mo, seq, incr, nmo, nseq",
                         [
                         # intramonth gap at (2003, 8, 31)
                          (2003, 8, 32, -1, 8, 30,),
                          (2003, 8, 30, +1, 8, 32,),
                          # normal case
                          (2003, 8, 382, -1, 8, 381,),
                          (2003, 8, 382, +1, 8, 383,),
                          # previous month
                          (2003, 8, 1, -1, 7, 1216,),
                          # next month
                          (2003, 7, 1216, +1, 8, 1,),
                          (2000, 6, 3, +1, 8, 1,),
                          ])
def test_next_msg(client, yr, mo, seq ,incr, nmo, nseq):
    "make sure we can hop over gaps and between months"
    with client.application.app_context():
        assert next_msg(yr, mo, seq, incr)["month"] == nmo
        assert next_msg(yr, mo, seq, incr)["seq"] == nseq

@pyt_parameterize("yr, mo, seq, incr",
                         [
                         # end of the line
                          (2011, 2, 1643, +1,),
                          (2000, 3, 1, -1,),
                          ])
def test_next_msg_fail(client, yr, mo, seq ,incr):
    "make sure we can hop over gaps and between months"
    with client.application.app_context():
        with pytest.raises(ValueError):
            nxt = next_msg(yr, mo, seq, incr)

def test_encoded_from(client):
    "check decode of quopri-encoding From:"
    with client.application.app_context():
        msg = read_message(eml_file(2002, 12, 1259))
        msg.filter_headers()
        assert msg["x-html-from"] is not None
        assert msg["from"] == 'Michael Butler <pariscycles@yahoo.co.uk>'
        header = str(msg["x-html-from"])
        assert header.count("<a href=") == 2

def test_trim_subj(client):
    with client.application.app_context():
        msg = read_message(eml_file(2001, 1, 91))
        exp = "Cinelli Myths � aluminium bars, fastback seatstay design"
        assert trim_subject_prefix(msg["Subject"]) == exp

def test_sender_pat():
    for (from_, sender, addr) in (
        # bare email address
        ("Bikerdaver@aol.com",
         "", "Bikerdaver@aol.com"),
        # quoted name, bracketed email address
        ('"Mark Poore" <rauler47@hotmail.com>',
         "Mark Poore", "rauler47@hotmail.com"),
        # name only, no email address
        ("Mark Bulgier",
         "Mark Bulgier", ""),
        # bare name, bracketed email address
        ("Chuck Schmidt <chuckschmidt@earthlink.net>",
         "Chuck Schmidt", "chuckschmidt@earthlink.net"),
        # quoted, complex name, bracketed email address
        ('"Beyer Jr., Chris (C.C.)" <cbeyer2@volvocars.com>',
         "Beyer Jr., Chris (C.C.)", "cbeyer2@volvocars.com"),
        # bare email address, parenthesized name
        ('kurtsperry@netscape.net (Kurt Sperry)',
         'Kurt Sperry', 'kurtsperry@netscape.net'),
        # bare name, square bracket enclosing mailto:
        ("Chuck Schmidt [mailto:chuckschmidt@earthlink.net]",
         "Chuck Schmidt", "chuckschmidt@earthlink.net"),
        ('Michael Butler <pariscycles@yahoo.co.uk>',
         'Michael Butler', 'pariscycles@yahoo.co.uk'),
    ):
        (name, email) = parse_from(from_)
        assert name == sender and email == addr

@pyt_parameterize("exp, yr, mo, seq",
                  [
                   ("2005-09/eml-files/classicrendezvous.10509.1592.eml",
                    2005, 9, 1592),
                   ("2005-09/eml-files/classicrendezvous.10509.0001.eml",
                    2005, 9, 1),
                   ("2005-09/eml-files/classicrendezvous.10509.0123.eml",
                    2005, 9, 123),
                   ])
def test_eml_file(client, exp, yr, mo, seq):
    with client.application.app_context():
        CR = current_app.config["CR"]
        assert os.path.join(CR, exp) == eml_file(yr, mo, seq)

def test_fmt_sig1(client):
    with client.application.app_context():
        msg = read_message(eml_file(2010, 7, 144))
        html = msg.as_html()
        assert ("<br>Ted Ernst" in html and
                "<br>Palos Verdes Estates" in html and
                "<br>CA  USA" in html)

def test_fmt_sig2(client):
    with client.application.app_context():
        msg = read_message(eml_file(2009, 3, 134))
        html = msg.as_html()
        assert ("<br>Ted Ernst" in html and
                "<br>Palos Verdes Estates" in html and
                "<br>CA  USA" in html)

def test_para_split(client):
    with client.application.app_context():
        msg = read_message(eml_file(2009, 3, 144))
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


MULTIPART_NO_TEXT_EMAIL = """\
x-sender: classic-rendezvous-lightweight-vintage-bicycles+bncCLO0uJroCxDt2YrrBBoEnaFj1w@googlegroups.com
x-receiver: classicrendezvous-index@archive.nt.phred.org
Received: from phred.org ([172.16.1.2]) by monkeyfood.nt.phred.org with Microsoft SMTPSVC(6.0.3790.4675);
	 Mon, 21 Feb 2011 15:01:52 -0800
Received: from mail-qw0-f62.google.com (mail-qw0-f62.google.com [209.85.216.62])
	by phred.org (Postfix) with ESMTP id 78C475E3F
	for <classicrendezvous-index@catfood.phred.org>; Mon, 21 Feb 2011 15:02:03 -0800 (PST)
Received: by qwe4 with SMTP id 4sf3919202qwe.7
        for <classicrendezvous-index@catfood.phred.org>; Mon, 21 Feb 2011 15:02:05 -0800 (PST)
DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed;
        d=googlegroups.com; s=beta;
        h=domainkey-signature:x-beenthere:received-spf:to:subject:date
         :x-mb-message-source:x-aol-ip:x-mb-message-type:mime-version:from
         :x-mailer:message-id:x-spam-flag:x-aol-sender:x-original-sender
         :x-original-authentication-results:reply-to:precedence:mailing-list
         :list-id:list-post:list-help:list-archive:sender:list-unsubscribe
         :content-type;
        bh=NaraORkC96232Zj0p8dbn57aHFVYPhOZjyaMawAt/vk=;
        b=xbSgR0Y5PcEwAVJa/yrXosZi4XX/gbT/S+oAz7ANw/6aneiUUec0gez50LMWkYAgvb
         GkBt9J8yQM+dBc5Z5cTPY5QQ5XilI4NnzoyRFA0BZ3ql4pyyYaFnIP5fJmvFf9oBmOPx
         p+ff5gXK1blHEyJvWo0uNACeATiwZ+u8QLuOE=
DomainKey-Signature: a=rsa-sha1; c=nofws;
        d=googlegroups.com; s=beta;
        h=x-beenthere:received-spf:to:subject:date:x-mb-message-source
         :x-aol-ip:x-mb-message-type:mime-version:from:x-mailer:message-id
         :x-spam-flag:x-aol-sender:x-original-sender
         :x-original-authentication-results:reply-to:precedence:mailing-list
         :list-id:list-post:list-help:list-archive:sender:list-unsubscribe
         :content-type;
        b=55E8UBZhFEitk66NLdpRkXnSwDfoiuxHIYZLvWpWDk7DdtpD8Rh/5UCaHMeI5dSPFx
         O0BdJJdB3MPomSLegaicu6am+0HYmQsu02bf8zdeeeX6MDpxRZes1sm5kv+96TDy5k7X
         0J9V7N78TPXiI9/DVqk4zyvimqLxmGFOxTtLw=
Received: by 10.229.67.133 with SMTP id r5mr189362qci.34.1298312429370;
        Mon, 21 Feb 2011 10:20:29 -0800 (PST)
X-BeenThere: classic-rendezvous-lightweight-vintage-bicycles@googlegroups.com
Received: by 10.224.3.230 with SMTP id 38ls661292qao.0.p; Mon, 21 Feb 2011
 10:20:29 -0800 (PST)
Received: by 10.224.89.14 with SMTP id c14mr154995qam.8.1298312429166;
        Mon, 21 Feb 2011 10:20:29 -0800 (PST)
Received: by 10.229.185.135 with SMTP id co7mr150289qcb.14.1298312377419;
        Mon, 21 Feb 2011 10:19:37 -0800 (PST)
Received: by 10.229.185.135 with SMTP id co7mr150288qcb.14.1298312377302;
        Mon, 21 Feb 2011 10:19:37 -0800 (PST)
Received: from imr-ma03.mx.aol.com (imr-ma03.mx.aol.com [64.12.206.41])
        by gmr-mx.google.com with ESMTP id k7si1167466qcu.6.2011.02.21.10.19.37;
        Mon, 21 Feb 2011 10:19:37 -0800 (PST)
Received-SPF: pass (google.com: domain of OROBOYZ@aol.com designates 64.12.206.41 as permitted sender) client-ip=64.12.206.41;
Received: from imo-da04.mx.aol.com (imo-da04.mx.aol.com [205.188.169.202])
	by imr-ma03.mx.aol.com (8.14.1/8.14.1) with ESMTP id p1LIJPHU015567
	for <classic-rendezvous-lightweight-vintage-bicycles@googlegroups.com>; Mon, 21 Feb 2011 13:19:25 -0500
Received: from OROBOYZ@aol.com
	by imo-da04.mx.aol.com  (mail_out_v42.9.) id r.fdc.c4e5a34 (43815)
	 for <classic-rendezvous-lightweight-vintage-bicycles@googlegroups.com>; Mon, 21 Feb 2011 13:19:22 -0500 (EST)
Received: from smtprly-dd03.mx.aol.com (smtprly-dd03.mx.aol.com [205.188.84.131]) by cia-dc01.mx.aol.com (v129.9) with ESMTP id MAILCIADC014-d4054d62aca6cf; Mon, 21 Feb 2011 13:19:21 -0500
Received: from Webmail-d107 (webmail-d107.sim.aol.com [205.188.171.201]) by smtprly-dd03.mx.aol.com (v129.9) with ESMTP id MAILSMTPRLYDD031-d4054d62aca6cf; Mon, 21 Feb 2011 13:19:18 -0500
To: classic-rendezvous-lightweight-vintage-bicycles@googlegroups.com
Subject: {Classic Rendezvous} Moving the CR list to Google groups
Date: Mon, 21 Feb 2011 13:19:18 -0500
X-MB-Message-Source: WebUI
X-AOL-IP: 174.98.97.4
X-MB-Message-Type: User
MIME-Version: 1.0
From: oroboyz@aol.com
X-Mailer: AOL Webmail 33222-STANDARD
Received: from 174.98.97.4 by Webmail-d107.sysops.aol.com (205.188.171.201) with HTTP (WebMailUI); Mon, 21 Feb 2011 13:19:18 -0500
Message-Id: <8CDA00AFD472A37-D34-102C@Webmail-d107.sysops.aol.com>
X-Spam-Flag: NO
X-AOL-SENDER: OROBOYZ@aol.com
X-Original-Sender: oroboyz@aol.com
X-Original-Authentication-Results: gmr-mx.google.com; spf=pass (google.com:
 domain of OROBOYZ@aol.com designates 64.12.206.41 as permitted sender) smtp.mail=OROBOYZ@aol.com
Reply-To: classic-rendezvous-lightweight-vintage-bicycles@googlegroups.com
Precedence: list
Mailing-list: list classic-rendezvous-lightweight-vintage-bicycles@googlegroups.com;
 contact classic-rendezvous-lightweight-vintage-bicycles+owners@googlegroups.com
List-ID: <classic-rendezvous-lightweight-vintage-bicycles.googlegroups.com>
List-Post: <http://groups.google.com/group/classic-rendezvous-lightweight-vintage-bicycles/post?hl=en_US>,
 <mailto:classic-rendezvous-lightweight-vintage-bicycles@googlegroups.com>
List-Help: <http://groups.google.com/support/?hl=en_US>, <mailto:classic-rendezvous-lightweight-vintage-bicycles+help@googlegroups.com>
List-Archive: <http://groups.google.com/group/classic-rendezvous-lightweight-vintage-bicycles?hl=en_US>
Sender: classic-rendezvous-lightweight-vintage-bicycles@googlegroups.com
List-Unsubscribe: <http://groups.google.com/group/classic-rendezvous-lightweight-vintage-bicycles/subscribe?hl=en_US>,
 <mailto:classic-rendezvous-lightweight-vintage-bicycles+unsubscribe@googlegroups.com>
Content-Type: multipart/alternative;
 boundary="--------MB_8CDA00AFD4BECFB_D34_23E9_Webmail-d107.sysops.aol.com"
Return-Path: classic-rendezvous-lightweight-vintage-bicycles+bncCLO0uJroCxDt2YrrBBoEnaFj1w@googlegroups.com
X-OriginalArrivalTime: 21 Feb 2011 23:01:53.0092 (UTC) FILETIME=[5453D040:01CBD21B]

----------MB_8CDA00AFD4BECFB_D34_23E9_Webmail-d107.sysops.aol.com
Content-Transfer-Encoding: quoted-printable
Content-Type: text/html; charset=ISO-8859-1

<font color=3D'rgb(25, 25, 112)' size=3D'2' face=3D'Verdana, Arial, Helveti=
ca, sans-serif'><font class=3D"Apple-style-span" color=3D"#191970" face=3D"=
Verdana, Arial, Helvetica, sans-serif" size=3D"2">Hi folks:</font>
<div style=3D"color: rgb(25, 25, 112); font-family: Verdana, Arial, Helveti=
ca, sans-serif; font-size: 10pt; "><br>
</div>

<div style=3D"color: rgb(25, 25, 112); font-family: Verdana, Arial, Helveti=
ca, sans-serif; font-size: 10pt; ">The process has begun. &nbsp;It looks li=
ke there will be definite advantages... I just successfully attached a pict=
ure to a message there, so that will be a huge step up!&nbsp;</div>

<div style=3D"color: rgb(25, 25, 112); font-family: Verdana, Arial, Helveti=
ca, sans-serif; font-size: 10pt; "><br>
</div>

<div><font class=3D"Apple-style-span" color=3D"#191970" face=3D"Verdana, Ar=
ial, Helvetica, sans-serif" size=3D"2">Request: Please put your first and l=
ast name in the Google group "Nick name" box when signing up. This has been=
 a&nbsp;</font><font class=3D"Apple-style-span" color=3D"#191970" face=3D"V=
erdana, Arial, Helvetica, sans-serif">requirement</font><font class=3D"Appl=
e-style-span" color=3D"#191970" face=3D"Verdana, Arial, Helvetica, sans-ser=
if" size=3D"2">&nbsp;all along so this will carry over to this new format.<=
/font></div>

<div><font class=3D"Apple-style-span" color=3D"#191970" face=3D"Verdana, Ar=
ial, Helvetica, sans-serif" size=3D"2"><br>
</font></div>

<div><font class=3D"Apple-style-span" color=3D"#191970" face=3D"Verdana, Ar=
ial, Helvetica, sans-serif" size=3D"2">Here is the new email list home page=
:</font></div>

<div><font class=3D"Apple-style-span" color=3D"#191970" face=3D"Verdana, Ar=
ial, Helvetica, sans-serif" size=3D"2"><br>
</font></div>

<div><font class=3D"Apple-style-span" color=3D"#191970" face=3D"Verdana, Ar=
ial, Helvetica, sans-serif" size=3D"2"><a href=3D"http://groups.google.com/=
group/classic-rendezvous-lightweight-vintage-bicycles?hl=3Den_US">http://gr=
oups.google.com/group/classic-rendezvous-lightweight-vintage-bicycles?hl=3D=
en_US</a></font></div>

<div style=3D"color: rgb(25, 25, 112); font-family: Verdana, Arial, Helveti=
ca, sans-serif; font-size: 10pt; "><br>
</div>

<div style=3D"color: rgb(25, 25, 112); font-family: Verdana, Arial, Helveti=
ca, sans-serif; font-size: 10pt; ">Thanks</div>

<div style=3D"color: rgb(25, 25, 112); font-family: Verdana, Arial, Helveti=
ca, sans-serif; font-size: 10pt; ">Dale<br>
<br>

<div style=3D"clear:both"><font color=3D"black" face=3D"arial" size=3D"2"><=
font size=3D"2"><font face=3D"Arial, Helvetica, sans-serif">Dale Brown<br>
cycles de ORO, Inc.<br>
Greensboro, North Carolina &nbsp;USA<br>
www.classicrendezvous.com<br>
</font></font></font><br>
<font color=3D"black" face=3D"arial" size=3D"2"><font size=3D"2"><font face=
=3D"Arial, Helvetica, sans-serif"><br>
</font></font></font></div>
</div>
</font>

<p></p>

-- <br />
You received this message because you are subscribed to the Google Groups "=
Classic Rendezvous lightweight vintage bicycles" group.<br />
To post to this group, send email to classic-rendezvous-lightweight-vintage=
-bicycles@googlegroups.com.<br />
To unsubscribe from this group, send email to classic-rendezvous-lightweigh=
t-vintage-bicycles+unsubscribe@googlegroups.com.<br />

For more options, visit this group at http://groups.google.com/group/classi=
c-rendezvous-lightweight-vintage-bicycles?hl=3Den.<br />



----------MB_8CDA00AFD4BECFB_D34_23E9_Webmail-d107.sysops.aol.com--
"""


def test_empty_payload(client):
    with client.application.app_context():
        msg = read_message_string(EMPTY_MAIL)
        payload = msg.get_payload(decode=True)
        payload = msg.decode(payload)
        payload = strip_footers(payload)
        assert not payload, payload

def test_subject_fix(client):
    with client.application.app_context():
        msg = read_message(eml_file(2000, 11, 1036))
        assert msg["Subject"] == "[CR] Danger, items for sale"

def test_long_url_fix(client):
    with client.application.app_context():
        msg = read_message(eml_file(2010, 5, 1410))
        payload = msg.get_payload(decode=True)
        payload = msg.decode(payload)
        payload = strip_footers(payload)
        msg.set_payload(payload)
        html = msg.as_html()
        assert "/<wbr>FoldingATubularTire" in html

def test_extract_text_mixed(client):
    with client.application.app_context():
        # main type is multipart/mixed with one part being text/html and
        # another image/jpeg
        msg = read_message(eml_file(2011, 2, 1425))
        assert msg["content-type"].split(";")[0] == "multipart/mixed"
        payload = msg.extract_text()
        assert payload.count("I am in need of a Mafac") == 1

def test_extract_related(client):
    with client.application.app_context():
        msg = read_message(eml_file(2011, 2, 1408))
        assert msg["content-type"].split(";")[0] == "multipart/related"
        payload = msg.extract_text()
        assert payload.count("Any a youse ever seen this before?") == 1

def test_extract_htmltext(client):
    with client.application.app_context():
        # main type is multipart/alternative, but I've removed the text/plain
        # section, leaving the text/html section.
        msg = read_message_string(MULTIPART_NO_TEXT_EMAIL)
        assert msg["content-type"].split(";")[0] == "multipart/alternative"
        payload = msg.extract_text()
        assert payload.count("The process has begun.") == 1

def test_unknown_content_type():
    msg = read_message_string(EMPTY_MAIL)
    maintype = msg.get_content_maintype()
    assert maintype not in ("image", "text", "multipart")
    try:
        _x = msg.as_html()
    except ValueError:
        pass


def test_open_():
    eprint("Hello World!", file=open_(os.devnull, "w"))
    fd, name = tempfile.mkstemp()
    os.close(fd)
    with open_(f"{name}.gz", "wb") as fobj:
        fobj.write(b"Hello World!")
    os.unlink(f"{name}")
    os.unlink(f"{name}.gz")

def test_open_invalid_encoding():
    fd, name = tempfile.mkstemp()
    os.close(fd)
    try:
        with pytest.raises(ValueError):
            with open_(f"{name}", "rb", encoding="ascii") as fobj:
                assert fobj.read() == b"Hello World!"
    finally:
        os.unlink(f"{name}")

def test_have_term(client):
    eprint("Hello World!", file=open_(os.devnull, "w"), dt="")
    with client.application.app_context():
        rowid = 0
        cur = SRCHDB.cursor()
        try:
            key = "skip m"
            assert SRCHDB.have_term(key) == 0
            cur.execute("insert into search_terms VALUES (?)", (key,))
            assert (rowid := SRCHDB.have_term(key)) > 0
        finally:
            cur.execute("delete from search_terms where rowid = ?",
                        (rowid,))


def test_patch_word_breaks(client):
    with client.application.app_context():
        msg = read_message(eml_file(2005, 7, 921))
        raw_body = msg.decode(msg.get_payload(decode=True))
        patched_body = msg.extract_text()
        assert " approa\r\nch " in raw_body
        assert (" approa\r\nch " not in patched_body and
                " approach " in patched_body)


def test_words_exceptions():
    exc = list(EXCEPTIONS)[0]
    assert exc not in all_words(keep_odd=True)


def test_rewrite_ebay_urls():
    for url in (
        "http://cgi.ebay.com/1974-Masi-Prestige-Cronometro-Campagnolo_W0QQitemZ120316303908QQcmdZViewItem?hash=item120316303908&_trkparms=72%3A1423%7C39%3A1%7C66%3A2%7C65%3A12%7C240%3A1318&_trksid=p3286.c0.m14",
        ):
        line = f"pfx{url}sfx\r\npfx"
        assert rewrite_ebay_urls(line) == "pfxhttp://ebay.com/<blah>\r\npfx"
