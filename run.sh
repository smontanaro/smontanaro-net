#!/bin/bash

basedir=/home/skip/website

cd $basedir

source $basedir/bin/activate

export FLASK_APP=hello
export FLASK_ENV=development

flask run -h 0.0.0.0 -p 8080
