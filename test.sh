#!/bin/bash

# run Flask server and throw a bunch of URLs at it. Compare with
# expected output.

export PORT=5001 HOST=localhost
(bash run.sh 2>&1 \
     | egrep -v 'Running on|Debugger PIN' \
     | sed -e 's;.../.../.... ..:..:... ;;' \
           -e 's/^.....-..-.. ..:..:..,.... //' > localhost.act) &
sleep 3

sed -e 's/localhost:[0-9][0-9]*/localhost:5001/' < localhost.urls \
    | while read url ; do
    curl -s $url
done  2> localhost.act > localhost.raw
pkill -f flask
