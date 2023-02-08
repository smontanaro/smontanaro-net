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
