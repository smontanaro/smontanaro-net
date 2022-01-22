#!/bin/bash

export CRDIR=/home/skip/src/smontanaro.net
export FLASK_APP=smontanaro
export FLASK_ENV=development

PORT=${PORT:-8080}
HOST=${HOST:-0.0.0.0}

cd smontanaro

CMD="$(which flask) run -h 0.0.0.0 -p $PORT"
if [ "x$DOCOVER" = "xtrue" ] ; then
    coverage run $CMD
else
    $CMD
fi
