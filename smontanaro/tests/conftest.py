#!/usr/bin/env python

import pytest
from smontanaro import app as _app

@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()

    with _app.app_context():
        pass

    yield app

@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
