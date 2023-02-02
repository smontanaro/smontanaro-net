"low-level query tests"

import time

from smontanaro.query import execute_query, parse_query, execute_structured_query
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
        filenames = execute_query("bartali OR coppi").pages()
        assert "CR/2000-10/eml-files/classicrendezvous.10010.0885.eml" in filenames
        assert "CR/2000-10/eml-files/classicrendezvous.10010.0169.eml" in filenames
        assert "CR/2001-12/eml-files/classicrendezvous.10112.0582.eml" in filenames

def test_transitive_complex_query(client):
    with client.application.app_context():
        assert (execute_query("coppi AND bartali").pages() ==
                execute_query("bartali AND coppi").pages())

def test_invalid_not_and_query(client):
    with client.application.app_context():
        try:
            execute_query("NOT coppi AND NOT bartali")
        except ValueError:
            pass
        else:
            raise ValueError("Failed to catch NOT AND NOT")

def test_invalid_not_or_query(client):
    with client.application.app_context():
        try:
            execute_query("coppi OR NOT bartali")
        except ValueError:
            pass
        else:
            raise ValueError("Failed to catch OR NOT")

def test_complex_query2(client):
    with client.application.app_context():
        # CR/2000/10/0885 (bartali and coppi)
        # CR/2000/10/0169 (coppi only)
        # CR/2001/12/0582 (bartali only)
        result = execute_query("bartali AND coppi")
        assert "CR/2000-10/eml-files/classicrendezvous.10010.0885.eml" in result
        assert "CR/2000-10/eml-files/classicrendezvous.10010.0169.eml" not in result
        assert "CR/2001-12/eml-files/classicrendezvous.10112.0582.eml" not in result

def test_complex_query3(client):
    with client.application.app_context():
        # CR/2000/10/0885 (bartali and coppi)
        # CR/2001/12/0582 (bartali only)
        result = execute_query("bartali AND NOT coppi")
        assert "CR/2000-10/eml-files/classicrendezvous.10010.0885.eml" not in result
        assert "CR/2001-12/eml-files/classicrendezvous.10112.0582.eml" in result

def test_query_cache(client):
    # hopefully none of these will already be cached.
    queries = [
        "from:aldoross4@siscom.net",
        "from:brianbaylis@juno.com",
        "126mm",
        "80s bikes",
        "mid-range components",
        "fausto coppi",
        "bartali AND coppi",
        "NOT bartali AND coppi",
        "from:dale brown AND (silk hope OR McClean)",
        "from:brian baylist AND richard moon",
        ]

    result1 = [0.0, {}]
    result2 = [0.0, {}]
    with client.application.app_context():
        for result in (result1, result2):
            start = time.time()
            for query in queries:
                result[1][query] = execute_query(query)
            result[0] = time.time() - start
    # Caching should return the same results ...
    assert result1[1] == result2[1]
    # ... but more quickly
    assert result1[0] > result2[0]


def test_from_query(client):
    with client.application.app_context():
        result = execute_query("from:mark petry")
        try:
            assert result.data
        except AssertionError:
            raise ValueError("no search results")
        assert set(result.data.values()) == set([""])

def test_trailing_space_from(client):
    with client.application.app_context():
        no_space = execute_query("from:dale brown")
        tr_space = execute_query("from:dale brown ")
        assert tr_space and tr_space == no_space


def test_parse_simple_query():
    assert parse_query("giovanni valetti") == ["search", "giovanni valetti"]

def test_parse_and_query():
    assert parse_query("Valetti AND Bartali") == \
        ["intersect", ["search", "bartali"], ["search", "valetti"]]

def test_parse_or_query():
    assert parse_query("Valetti OR Bartali") == \
        ["union", ["search", "bartali"], ["search", "valetti"]]

def test_parse_and_or_query():
    assert parse_query("Valetti OR Bartali AND NOT Coppi") == \
        ["union",
         ["intersect",
          ["not", ["search", "coppi"]],
          ["search", "bartali"],
         ],
         ["search", "valetti"],
         ]

def test_parse_parens_query():
    assert parse_query("(Valetti OR Bartali) AND Coppi") == \
        ["intersect",
         ["search", "coppi"],
         ["union",
          ["search", "bartali"],
          ["search", "valetti"],
         ],
        ]

def test_parse_not_and_not_query():
    assert parse_query("(NOT coppi) AND (NOT bartali)") == \
        ["intersect",
         ["not", ["search", "bartali"]],
         ["not", ["search", "coppi"]],
         ]

def test_invalid_parse1():
    parsed_query = parse_query("bartali")
    parsed_query[0] = "fred"
    try:
        execute_structured_query(parsed_query)
    except ValueError:
        pass
    else:
        raise ValueError("Failed to reject bad parse")

def test_invalid_parse():
    parsed_query = parse_query("bartali AND coppi")
    parsed_query[0] = "fred"
    try:
        execute_structured_query(parsed_query)
    except ValueError:
        pass
    else:
        raise ValueError("Failed to reject bad parse")

def test_deeply_nested_parse1():
    q = parse_query("subject:For Sale OR subject:wtt OR subject:wtb OR subject:fs")
    assert q == \
        ['union',
         ['search', 'subject:fs'],
         ['union',
          ['search', 'subject:wtb'],
          ['union',
           ['search', 'subject:wtt'],
           ['search', 'subject:for sale']]]]

def test_deeply_nested_parse2():
    q = parse_query("(subject:For Sale OR subject:fs) AND NOT (subject:wtt OR subject:wtb)")
    assert q == \
        ['intersect',
         ['not',
          ['union',
           ['search', 'subject:wtb'],
           ['search', 'subject:wtt'],
          ],
         ],
         ['union',
          ['search', 'subject:fs'],
          ['search', 'subject:for sale'],
         ],
        ]
