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

if [ "x$(which gunicorn)" = "x" ] ; then
    echo "Gunicorn not found. Make sure you're running an appropriate virtual environment." 1>&2
    exit 1
fi

${COV} $(which gunicorn) --pythonpath=$(pwd)/smontanaro \
       --error-logfile=/dev/stderr --access-logfile=/dev/stderr \
       --bind $HOST:$PORT wsgi:app
