
import datetime
import regex as re

from _test_helper import client


def test_calendar(client):
    with client.application.app_context():
        today = datetime.date.today()
        rv = client.get("/calendar/")
        assert rv.status_code == 200
        checklines = []
        saving = False
        for line in rv.text.split("\n"):
            if saving and "<!-- end test support -->" in line:
                break
            if "<!-- start test support -->" in line:
                saving = True
            elif saving:
                checklines.append(re.search(">([^<]+)<", line).group(1).strip())
        assert checklines == f"{today.year} Jan May Aug Feb Jun Sep Apr".split()

def test_calendar_year(client):
    with client.application.app_context():
        today = datetime.date(1989, 1, 1)
        rv = client.get("/calendar/1989")
        assert rv.status_code == 200
        checklines = []
        saving = False
        for line in rv.text.split("\n"):
            if saving and "<!-- end test support -->" in line:
                break
            if "<!-- start test support -->" in line:
                saving = True
            elif saving:
                checklines.append(re.search(">([^<]+)<", line).group(1).strip())
        assert checklines == f"{today.year} Jan May Aug Feb Jun Sep Apr".split()

def test_today(client):
    date = datetime.date.today()

    with client.application.app_context():
        rv = client.get("/calendar/today")
        assert rv.status_code == 302
        rv = client.get(rv.headers["Location"])
        assert rv.status_code == 200
        checklines = []
        saving = False
        for line in rv.text.split("\n"):
            if saving and "<!-- end test support -->" in line:
                break
            if "<!-- start test support -->" in line:
                saving = True
            elif saving:
                checklines.append(re.search(">([^<]+)<", line).group(1).strip())
        assert checklines[0] == f"{date.year}"

def test_date(client):
    date = datetime.date.today()

    with client.application.app_context():
        rv = client.get("/calendar/1989/4/12")
        assert rv.status_code == 200
        check = []
        for line in rv.text.split("\n"):
            mat = re.search('"calendar calendar_today">([^<]+)', line)
            if mat is not None:
                check.append(mat.group(1))
        assert check == "Apr 12 Wed".split()

def test_bad_date(client):
    date = datetime.date.today()

    with client.application.app_context():
        rv = client.get("/calendar/2023/2/29")
        assert rv.status_code == 200
        assert "Invalid date" in rv.text
