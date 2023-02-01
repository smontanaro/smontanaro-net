"low-level query tests"

import time

from smontanaro.query import execute_query, parse_query
from smontanaro.srchdb import SRCHDB
from smontanaro.views import query_index

from _test_helper import client


def test_low_level_query(client):
    with client.application.app_context():
        for (filename, fragment) in SRCHDB.get_page_fragments("faliero masi"):
            assert filename
            assert fragment
            break
        else:
            raise ValueError("no search results")


def test_complex_query1(client):
    with client.application.app_context():
        # CR/2000/10/0885 (bartali and coppi)
        # CR/2000/10/0169 (coppi only)
        # CR/2001/12/0582 (bartali only)
        filenames = set(res[0] for res in execute_query("bartali OR coppi"))
        assert "CR/2000-10/eml-files/classicrendezvous.10010.0885.eml" in filenames
        assert "CR/2000-10/eml-files/classicrendezvous.10010.0169.eml" in filenames
        assert "CR/2001-12/eml-files/classicrendezvous.10112.0582.eml" in filenames
        q1 = set(fname for (fname, frag) in execute_query("bartali OR coppi"))
        q2 = set(fname for (fname, frag) in execute_query("coppi OR bartali"))
        assert q1 == q2

def test_complex_query2(client):
    with client.application.app_context():
        # CR/2000/10/0885 (bartali and coppi)
        # CR/2000/10/0169 (coppi only)
        # CR/2001/12/0582 (bartali only)
        filenames = set(res[0] for res in execute_query("bartali AND coppi"))
        assert "CR/2000-10/eml-files/classicrendezvous.10010.0885.eml" in filenames
        assert "CR/2000-10/eml-files/classicrendezvous.10010.0169.eml" not in filenames
        assert "CR/2001-12/eml-files/classicrendezvous.10112.0582.eml" not in filenames
        q1 = set(fname for (fname, frag) in execute_query("bartali AND coppi"))
        q2 = set(fname for (fname, frag) in execute_query("coppi AND bartali"))
        assert q1 == q2


def test_query_cache(client):
    # hopefully none of these will already be cached.
    queries = [
        "from:aldoross4@siscom.net",
        "from:brianbaylis@juno.com",
        "126mm",
        "80s bikes",
        "ambrosio stem",
        "ebay problems",
        "kof rivendell",
        "madonna del ghisallo",
        "mid-range components",
        "nervex masi",
        "fausto coppi",
        ]

    result1 = [0.0, {}]
    result2 = [0.0, {}]
    with client.application.app_context():
        for result in (result1, result2):
            start = time.time()
            for query in queries:
                result[1][query] = list(SRCHDB.get_page_fragments(query))
            result[0] = time.time() - start
    # Caching should return the same results ...
    assert result1[1] == result2[1]
    # ... but more quickly
    assert result1[0] > result2[0]


def test_from_query(client):
    with client.application.app_context():
        for (filename, fragment) in SRCHDB.get_page_fragments("from:mark petry"):
            assert filename
            assert not fragment
            break
        else:
            raise ValueError("no search results")

def test_trailing_space_from(client):
    with client.application.app_context():
        no_space = list(query_index("from:dale brown"))
        tr_space = list(query_index("from:dale brown "))
        assert tr_space and no_space and len(no_space) == len(tr_space)


def test_parse_simple_query():
    assert parse_query("giovanni valetti") == ["search", "giovanni valetti"]

def test_parse_and_query():
    assert parse_query("Valetti AND Bartali") == \
        ["intersect", ["search", "valetti"], ["search", "bartali"]]

def test_parse_or_query():
    assert parse_query("Valetti OR Bartali") == \
        ["union", ["search", "valetti"], ["search", "bartali"]]

def test_parse_and_or_query():
    assert parse_query("Valetti OR Bartali AND Coppi") == \
        ["union",
         ["search", "valetti"],
         ["intersect",
          ["search", "bartali"],
          ["search", "coppi"],
         ]]

def test_parse_parens_query():
    assert parse_query("(Valetti OR Bartali) AND Coppi") == \
        ["intersect",
         ["union",
          ["search", "valetti"],
          ["search", "bartali"],
         ],
         ["search", "coppi"],
        ]
