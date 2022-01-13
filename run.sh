#!/bin/bash

export FLASK_APP=hello
export FLASK_ENV=development

flask run -h localhost -p 8080
