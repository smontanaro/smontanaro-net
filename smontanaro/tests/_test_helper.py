import os
import tempfile

import pytest

from smontanaro import create_app
from smontanaro.refdb import ensure_db

@pytest.fixture
def client():
    topic_fd, topic_path = tempfile.mkstemp()
    app = create_app(
        {"DEBUG": True,
         "TESTING": True,
         "REFDB": "references.db",
         "WTF_CSRF_ENABLED": False,
         "TOPICFILE": topic_path,
         "SERVER_NAME": "smontanaro.net",
         }
    )

    with app.test_client() as client:
        with app.app_context():
            ensure_db(app.config["REFDB"])
        yield client

    os.close(topic_fd)
    os.unlink(topic_path)
