#!/bin/bash

if [ $USER = "root" ] ; then
    basedir=/var/opt/website

    # refresh venv & website code
    cd /var/opt
    rsync -avs --exclude=CR --exclude='.git*' --exclude=__pycache__ \
          ~skip/website .
else
    basedir=/home/skip/website
fi

cd $basedir

source $basedir/bin/activate

export FLASK_APP=hello
export FLASK_ENV=development

if [ $USER = "root" ] ; then
    gunicorn -c ./gcfg.py hello:app
else
    flask run -h 0.0.0.0 -p 8080
fi
