#!/bin/bash

if [ $USER = "root" ] ; then
    basedir=/var/opt/website

    # refresh venv & website code
    cd /var/opt
    rsync -avs --exclude=CR --exclude='.git*' ~skip/website .
else
    basedir=/home/skip/website
fi

cd $basedir

source $basedir/bin/activate

export FLASK_APP=hello
export FLASK_ENV=development

gunicorn -c ./gcfg.py hello:app
