import os
import tempfile

from smontanaro.srchdb import SRCHDB
from _test_helper import client


def test_post_search(client):
    rv = client.post("/search", data={
        "query": "Faliero",
        "engine": "Brave",
        })
    assert rv.status_code == 302

def test_reopen_database(client):
    sqldb = SRCHDB.sqldb
    (fdesc, fname) = tempfile.mkstemp()
    os.close(fdesc)
    SRCHDB.set_database(fname)
    SRCHDB.set_database(sqldb)
    os.unlink(fname)
