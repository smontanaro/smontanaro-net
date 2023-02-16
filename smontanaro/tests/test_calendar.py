
import datetime
import regex as re

from _test_helper import client


def test_calendar(client):
    with client.application.app_context():
        rv = client.get("/calendar/2023")
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
        assert checklines == "2023 Jan May Aug Feb Jun Sep Apr".split()

def test_calendar_anotheryear(client):
    with client.application.app_context():
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
        assert checklines[0] == "1989"

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
