#!/usr/bin/env python

"top level of pkg"

import os

from flask import Flask
from dynaconf import FlaskDynaconf

from . import util
from . import views

def create_app(_arg1, _arg2): # test_config=None):
    "create and configure app"
    app = Flask(__name__)
    FlaskDynaconf(app, settings_files=["settings.toml", ".secrets.toml"])

    crdir = os.environ.get("CRDIR", os.getcwd())
    app.config.from_mapping({
        "CRDIR": crdir,
        "REFDB": os.path.join(crdir, "references.db"),
        "CR": os.path.join(crdir, "CR"),
        "SECRET_KEY": r"Aw6CNZn*GIEt8Aw6CNZn*GIEt8",
        "DEBUG": os.environ.get("FLASK_ENV") == "development",
    })

    # if test_config is None:
    #     # load the instance config, if it exists, when not testing
    #     app.config.from_pyfile('config.py', silent=True)
    # else:
    #     # load the test config if passed in
    #     app.config.from_mapping(test_config)

    util.init_app(app)
    views.init_app(app)

    return app
