import pytest

from _test_helper import client

#from smontanaro.util import parse_from_complex, decode_email_header
from smontanaro.util import decode_email_header

def _test_name_parse(client):
    # "Jose S. Villaluz" <jose@villaluz.net> ->
    #          ("Jose S. Villaluz", "jose@villaluz.net")
    for (sender, exp) in (
        ('''"Jose S. Villaluz" <jose@villaluz.net>''',
         ("Jose S. Villaluz", "jose@villaluz.net")),
        ('''Sean Flores <seaneee175@gmail.com>''',
         ("Sean Flores", "seaneee175@gmail.com")),
        ('''"brianbaylis@juno.com" <brianbaylis@juno.com>''',
         ("brianbaylis@juno.com", "brianbaylis@juno.com")),
        ):
        (matcher, name, addr) = parse_from_complex(sender)
        print(sender, matcher, name, addr)
        assert (name, addr) == exp, matcher

def test_decode_email_header(client):
    for (encoded, expected) in (
        ('''=?iso-8859-1?q?Michael=20Butler?= <pariscycles@yahoo.co.uk>''',
         '''Michael Butler <pariscycles@yahoo.co.uk>'''),
        ('''skip.montanaro@gmail.com''', '''skip.montanaro@gmail.com'''),
        ('''=?UTF-8?B?TWFyYyBPbGl2ZXIgS8O8bm5l?= <mo@devoti-kuenne.com>''',
         '''Marc Oliver Künne <mo@devoti-kuenne.com>''')
        ):
        assert decode_email_header(encoded) == expected
