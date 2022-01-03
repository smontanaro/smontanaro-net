#!/bin/bash

if [ $(id --user) -eq 0 ] ; then
    port=80
else
    port=8080
fi

cd ~skip/website

source ~skip/website/bin/activate

export FLASK_APP=hello
export FLASK_ENV=development

flask run --host=0.0.0.0 --port=$port --debugger
