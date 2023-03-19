from smontanaro.util import read_message, eml_file
from smontanaro.views import MessageFilter

from _test_helper import client

def test_message_strip(client):
    "verify the yellowpages footer disappears"
    with client.application.app_context():
        msg = read_message(eml_file(2005, 10, 508))
        filt = MessageFilter(msg)
        filt.filter_message(msg)
        assert "yellowpages.lycos.com" not in msg.get_payload()

def test_message_strip_same_header_footer(client):
    "virginmedia stripper uses the same header and footer"
    with client.application.app_context():
        msg = read_message(eml_file(2007, 7, 4))
        filt = MessageFilter(msg)
        filt.filter_message(msg)
        assert "virginmedia.com" not in msg.as_string()

def test_bikelist_strip(client):
    with client.application.app_context():
        msg = read_message(eml_file(2011, 2, 1))
        assert "Classicrendezvous@bikelist.org" not in msg.extract_text()
