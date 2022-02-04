import os
import sys
import tempfile

import pytest

from smontanaro import create_app
from smontanaro.db import ensure_db


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app(
        {'TESTING': True,
         'REFDB': db_path,
         'WTF_CSRF_ENABLED': False,
         }
    )

    with app.test_client() as client:
        with app.app_context():
            ensure_db(db_path)
        yield client

    os.close(db_fd)
    os.unlink(db_path)

def test_get_robots(client):
    rv = client.get("/robots.txt")
    assert rv.status_code == 302

def test_post_search(client):
    rv = client.post("/search", data={
        "query": "Faliero",
        "engine": "Brave",
        })
    assert rv.status_code == 302
