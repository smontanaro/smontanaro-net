#!/usr/bin/env python

from flask import Flask

app = Flask(__name__)
app.config["SECRET_KEY"] = r"Aw6CNZn*GIEt8Aw6CNZn*GIEt8"

from .views import (favicon, robots, index, app_help)
