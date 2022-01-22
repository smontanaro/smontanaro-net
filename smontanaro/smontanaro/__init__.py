#!/usr/bin/env python

"top level of pkg"

import os

from flask import Flask

FLASK_DEBUG = os.environ.get("FLASK_ENV") == "development"
CRDIR = os.environ["CRDIR"]
REFDB = os.path.join(CRDIR, "references.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = r"Aw6CNZn*GIEt8Aw6CNZn*GIEt8"

CR = os.path.join(CRDIR, "CR")

# This import forces definition of all the routes (must be at the end, see views.py)
#pylint: disable=wrong-import-position
from .views import index
