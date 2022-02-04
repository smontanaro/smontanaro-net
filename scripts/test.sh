#!/bin/bash

# Run Flask server and throw a bunch of URLs at it. Compare with
# expected output.

# We diddle with localhost.exp toward the end. Make sure it's in
# a pristine state when we start.
ACT=localhost.act
RAW=/tmp/localhost.raw
WARNINGS=localhost.warnings

dateit () {
    while read line ; do
        echo "$(date +%T.%N) ${line}"
    done
}

export PORT=5001 HOST=localhost
(DOCOVER=true bash $(dirname $0)/run.sh 2>&1 | dateit > /tmp/$$.tmp) &
sleep 2

rm -f localhost.comments
sed -e 's/localhost:[0-9][0-9]*/localhost:5001/' < localhost.urls \
    | while read line ; do
    if [ "x${line:0:1}" = "x#" ] ; then
        echo "${line}" | dateit >> localhost.comments
    else
        echo "*** $line ***"
        curl -s $line
    fi
done  > $RAW

# grab a few random pages

# Shuffle is a little Python script I wrote years ago. I'm sure there
# is a more standard line randomizer, but I'm too lazy to look for
# it...
for d in $(find CR/ -name '20??-??' \
               | shuffle \
               | head -7) ; do
    find $d -name '*.eml' \
        | shuffle \
        | head -3
done \
    | sed -e 's:/eml-files/classicrendezvous.[0-9]*.:/:' \
          -e 's/[.]eml//' \
    | tr -- '-' / \
    | while read uri ; do
    url="http://${HOST}:${PORT}/${uri}"
    echo "*** $url ***"
    curl -s $url
done >> $RAW

sleep 1

pkill -f gunicorn

sort localhost.comments /tmp/$$.tmp \
    | sed -e 's/^[0-9][0-9]:[0-9][0-9]:[0-9][0-9][.0-9]* //' \
          -e 's;.../.../....:..:..:.. -..... ;;' \
          -e 's;^.[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9] -[0-9]*. .[0-9]*. .INFO.;[INFO];' \
          -e 's:HTTP/1.1" \([2-5][0-9][0-9]\) [0-9][0-9]*:HTTP/1.1" \1 <size>:' \
    | awk -f $(dirname $0)/filter.awk \
          > $ACT
rm localhost.comments /tmp/$$.tmp

# The dates module is only used by a couple auxiliary scripts.
coverage run -a --rcfile=.coveragerc scripts/listbydate.py CR/2000-03 >/dev/null
coverage run -a --rcfile=.coveragerc scripts/generate_date_index.py -d references.db 2000 3 >/dev/null

# Run our official unit tests
coverage run -a --rcfile=.coveragerc $(which pytest)

if [ -r .coverage -a -r smontanaro/.coverage ] ; then
    echo combine
    coverage combine .coverage smontanaro/.coverage
elif [ -r smontanaro/.coverage ] ; then
     echo rename
     mv smontanaro/.coverage .coverage
else
    :
fi

rm -rf htmlcov
coverage html

diff -u localhost.exp $ACT && echo "success" || echo "failure"
