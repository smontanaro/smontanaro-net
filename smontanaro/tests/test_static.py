#!/usr/bin/env python3

"check static site redirects"

from _test_helper import client

def test_get_robots(client):
    rv = client.get("/robots.txt")
    assert rv.status_code == 302

def test_static_redirect(client):
    for path in ("/43bikes", "/vintage-trek"):
        rv = client.get(path)
        assert rv.status_code == 302 and rv.location == f"{path}/"

def test_python_redirect(client):
    rv = client.get("/python/fsm.py")
    assert rv.status_code == 302

def test_python_bad_redirect(client):
    path = "/python/junk00.py"
    rv = client.get(path)
    assert rv.status_code == 302 and rv.location == f"/static{path}"
    rv = client.get(rv.location)
    assert rv.status_code == 404
