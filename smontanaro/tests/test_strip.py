from smontanaro.util import read_message
from smontanaro.views import MessageFilter

from _test_helper import client

def test_message_strip(client):
    "verify the yellowpages footer disappears"
    msg = read_message("CR/2005-10/eml-files/classicrendezvous.10510.0508.eml")
    with client.application.app_context():
        filt = MessageFilter(msg)
        filt.filter_message(msg)
        assert "yellowpages.lycos.com" not in msg.get_payload()

def test_message_strip_same_header_footer(client):
    "virginmedia stripper uses the same header and footer"
    msg = read_message("CR/2007-07/eml-files/classicrendezvous.10707.0004.eml")
    with client.application.app_context():
        filt = MessageFilter(msg)
        filt.filter_message(msg)
        assert "virginmedia.com" not in msg.as_string()
