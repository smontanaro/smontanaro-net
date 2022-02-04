import os
import tempfile

import pytest

from smontanaro import create_app
from smontanaro.db import ensure_db


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app({'TESTING': True, 'REFDB': db_path})

    with app.test_client() as client:
        with app.app_context():
            ensure_db(db_path)
        yield client

    os.close(db_fd)
    os.unlink(db_path)
