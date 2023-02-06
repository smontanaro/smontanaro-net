
import urllib.parse

from _test_helper import client


def test_photo_post_arg(client):
    url = "https://photos.app.goo.gl/qXkghhtQ2rPBhwZp7"
    with client.application.app_context():
        rv = client.post("/photolink", data={
            "fmt": "html",
            "width": 1200,
            "url": url,
        })
        assert rv.status_code == 200
        assert url in rv.text

def test_photo_post_no_arg(client):
    with client.application.app_context():
        rv = client.post("/photolink", data={})
        assert rv.status_code == 200

def test_photo_get_arg(client):
    url = "https://photos.app.goo.gl/qXkghhtQ2rPBhwZp7"
    with client.application.app_context():
        rv = client.get(f"/photolink?url={urllib.parse.quote_plus(url)}&width=200&fmt=bbcode")
        assert rv.status_code == 200
        assert url in rv.text

def test_photo_get_no_arg(client):
    with client.application.app_context():
        rv = client.get("/photolink")
        assert rv.status_code == 200
