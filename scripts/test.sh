#!/bin/bash

# Run Flask server and throw a bunch of URLs at it. Compare with
# expected output.

# We diddle with localhost.exp toward the end. Make sure it's in
# a pristine state when we start.
ACT=localhost.act
RAW=/tmp/localhost.raw
WARNINGS=localhost.warnings

if [ "x$(which gdate | egrep -v 'not found')" = "x" ] ; then
    DATE=date
else
    DATE=gdate
fi

dateit () {
    while read line ; do
        echo "$($DATE +%T.%N) ${line}"
    done
}

if [ -d search_cache ] ; then
    rm -r search_cache
fi

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
    gsleep 0.03
done  > $RAW

sleep 1

pkill -f gunicorn

PYTHONPATH=smontanaro flask routes | egrep --color=never 'GET|POST' | sort > $ACT

sort localhost.comments /tmp/$$.tmp \
    | sed -e 's/^[0-9][0-9]:[0-9][0-9]:[0-9][0-9][.0-9]* //' \
          -e 's;.../.../....:..:..:.. -..... ;;' \
          -e 's;^.[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9] -[0-9]*. .[0-9]*. .INFO.;[INFO];' \
          -e 's:HTTP/1.1" \([2-5][0-9][0-9]\) [0-9][0-9]*:HTTP/1.1" \1 <size>:' \
          -e 's:"curl/7[.][0-9][0-9].*:curl/7.NN:' \
          -e 's:/[^/]*/skip:~:' \
    | awk -f $(dirname $0)/filter.awk \
          >> $ACT
rm localhost.comments /tmp/$$.tmp

# Run our official unit tests
coverage run -a --rcfile=.coveragerc $(which pytest) -v
PYT=$?

# The dates module is only used by a couple auxiliary scripts.
coverage run -a --rcfile=.coveragerc scripts/listbydate.py CR/2000-03 >/dev/null
coverage run -a --rcfile=.coveragerc scripts/generate_date_index.py -d references.db 2000 3 >/dev/null

# Small refdb run to exercise one or two functions only it uses.

coverage run -a --rcfile=.coveragerc scripts/makerefsdb.py -d ref.db.test CR/2000-10
rm -f ref.db.test

# Exercise some bits only csv2topic uses
coverage run -a --rcfile=.coveragerc scripts/csv2topic.py references.db < topic.csv > /dev/null

# Exercise the code used to build the sqlite search database
find CR/2007-11/eml-files -name 'class*eml' \
    | head -1100 \
    | CRDIR=$(pwd) PYTHONPATH=smontanaro coverage run -a scripts/buildindex.py srch.db.test
n=$(echo "select * from search_terms where term = 'from:dale brown'" | sqlite3 srch.db.test | wc -l)
m=$(echo "select * from search_terms where term like 'from:% '" | sqlite3 srch.db.test | wc -l)
rm -f srch.db.test
if [ $n -eq 0 -o $m -gt 0 ] ; then
    echo "$(tput bold)Error generating from: terms$(tput sgr0)" 1>&2
fi

if [ -r .coverage -a -r smontanaro/.coverage ] ; then
    echo combine multiple .coverage files
    coverage combine .coverage smontanaro/.coverage
elif [ -r smontanaro/.coverage ] ; then
     echo rename smontanaro/.coverage to the top level
     mv smontanaro/.coverage .coverage
else
    echo only ./.coverage found - nothing to combine or rename
fi

rm -rf htmlcov
coverage html

diff -u localhost.exp $ACT && test $PYT -eq 0 && echo "success" || echo "failure"
