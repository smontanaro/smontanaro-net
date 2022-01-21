#!/bin/bash

export CRDIR=/home/skip/src/smontanaro.net
export FLASK_APP=smontanaro
export FLASK_ENV=development

PORT=${PORT:-8080}
HOST=${HOST:-0.0.0.0}

cd smontanaro

flask run -h 0.0.0.0 -p $PORT
