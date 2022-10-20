#!/bin/bash

export CRDIR=${HOME}/src/smontanaro.net
export FLASK_APP=smontanaro:create_app
export FLASK_ENV=development
PORT=${PORT:-8080}
HOST=${HOST:-localhost}

RCFILE=$PWD/.coveragerc

CMD="$(which gunicorn) --error-logfile=/dev/stderr --access-logfile=/dev/stderr --bind $HOST:$PORT wsgi:app"
if [ "x$DOCOVER" = "xtrue" ] ; then
    coverage run -a --rcfile=$RCFILE $CMD
else
    $CMD
fi
