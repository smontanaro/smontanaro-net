import csv
import os
import re
import tempfile

import pytest

from smontanaro import create_app
from smontanaro.db import ensure_db


@pytest.fixture
def client():
    topic_fd, topic_path = tempfile.mkstemp()
    app = create_app(
        {'TESTING': True,
         'REFDB': "references.db",
         'WTF_CSRF_ENABLED': False,
         'TOPICFILE': topic_path,
         }
    )

    with app.test_client() as client:
        with app.app_context():
            ensure_db(app.config["REFDB"])
        yield client

    os.close(topic_fd)
    os.unlink(topic_path)

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
    rv = client.get(rv.headers["Location"])
    assert (re.search(b"ebay", rv.data, re.I) is None and
            re.search(b"01 Sep 2005", rv.data) is not None)

def test_keep_filter(client):
    "check that we keep stuff we ask to keep"
    rv = client.post("/CR/filter_date", data={
        "pattern": "Campagnolo",
        "in_out": "keep",
        "year": "2005",
        "month": "09",
        })
    assert rv.status_code == 302
    rv = client.get(rv.headers["Location"])
    assert (re.search(b"Campagnolo", rv.data) is not None and
            re.search(b"01 Sep 2005", rv.data) is not None)

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
