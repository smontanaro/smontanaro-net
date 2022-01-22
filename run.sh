#!/bin/bash

export CRDIR=/home/skip/src/smontanaro.net
export FLASK_APP=smontanaro:create_app
export FLASK_ENV=development

PORT=${PORT:-8080}
HOST=${HOST:-localhost}

cd smontanaro

CMD="$(which flask) run -h $HOST -p $PORT"
if [ "x$DOCOVER" = "xtrue" ] ; then
    coverage run $CMD
else
    $CMD
fi
