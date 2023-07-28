
import re
import urllib.parse

from _test_helper import client


def test_photo_post_arg(client):
    url = "https://photos.app.goo.gl/qXkghhtQ2rPBhwZp7"
    with client.application.app_context():
        rv = client.post("/photolink", data={
            "fmt": "HTML",
            "width": 1200,
            "url": url,
        })
        assert rv.status_code == 200
        assert url in rv.text

def test_photo_bad_url(client):
    url = "https://www.flickr.com/photos/49705339@N00/albums/72177720297786696"
    with client.application.app_context():
        rv = client.post("/photolink", data={
            "fmt": "HTML",
            "width": 1200,
            "url": url,
        })
        assert rv.status_code == 200

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

def test_photo_get_raw_arg(client):
    url = urllib.parse.quote_plus("https://photos.app.goo.gl/qXkghhtQ2rPBhwZp7")
    with client.application.app_context():
        rv = client.get(f"/photolink?url={url}&width=200&fmt=Raw")
        assert (rv.status_code == 200 and
                "https://lh3.googleusercontent.com/" in rv.text and
                re.search("=w200", rv.text) is not None)

def test_photo_get_raw_zero_width(client):
    url = urllib.parse.quote_plus("https://photos.app.goo.gl/qXkghhtQ2rPBhwZp7")
    with client.application.app_context():
        rv = client.get(f"/photolink?url={url}&fmt=Raw")
        assert (rv.status_code == 200 and
                "https://lh3.googleusercontent.com/" in rv.text and
                re.search("=w[0-9][0-9][0-9]", rv.text) is None)

def test_photo_get_no_arg(client):
    with client.application.app_context():
        rv = client.get("/photolink")
        assert rv.status_code == 200
