#!/bin/bash

export CRDIR=/home/skip/src/smontanaro.net
export FLASK_APP=smontanaro
export FLASK_ENV=development

cd smontanaro

flask run -h localhost -p 8080
