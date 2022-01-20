#!/bin/bash

export CRDIR=/home/skip/src/smontanaro.net
export FLASK_APP=smontanaro
export FLASK_ENV=development

cd smontanaro

flask run -h 0.0.0.0 -p 8080
