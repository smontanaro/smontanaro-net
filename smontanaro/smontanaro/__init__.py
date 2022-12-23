#!/usr/bin/env python

"top level of pkg"

import os
import toml

from flask import Flask

from . import util
from . import views
from . import exc

def create_app(test_config=None):
    "create and configure app"
    app = Flask(__name__)

    crdir = os.environ.get("CRDIR", os.getcwd())
    app.config.from_mapping({
        "CRDIR": crdir,
        "REFDB": os.path.join(crdir, "references.db"),
        "CR": os.path.join(crdir, "CR"),
        "DEBUG": os.environ.get("FLASK_DEBUG") == "True",
        "TOPICFILE": os.path.join(crdir, "topic.csv"),
    })

    app.config.from_file("../../env.toml", load=toml.load)

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    util.init_app(app)
    views.init_app(app)
    exc.init_app(app)

    return app
