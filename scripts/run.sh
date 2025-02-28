#!/bin/bash

export CRDIR=${HOME}/src/smontanaro.net
export FLASK_APP=smontanaro:create_app
export FLASK_DEBUG=True
PORT=${PORT:-8080}
HOST=${HOST:-localhost}

RCFILE=$PWD/.coveragerc

if [ "x$DOCOVER" = "xtrue" ] ; then
    COV="coverage run -a --rcfile=$RCFILE"
fi

${COV} $(which gunicorn) --pythonpath=$(pwd)/smontanaro \
       --error-logfile=/dev/stderr --access-logfile=/dev/stderr \
       --bind $HOST:$PORT wsgi:app
