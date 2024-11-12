#!/bin/bash

if [ "x$CRDIR" = "x" ] ; then
    export CRDIR=$(pwd)
fi
if [ "x$PYTHONPATH" = "x" ] ; then
    export PYTHONPATH=$(pwd)/smontanaro
fi

echo "+++++++++++++++++++++++++++"
type python
python --version
echo "+++++++++++++++++++++++++++"

# Run Flask server and throw a bunch of URLs at it. Compare with
# expected output.

# We diddle with localhost.exp toward the end. Make sure it's in
# a pristine state when we start.
ACT=localhost.act
RAW=/tmp/localhost.raw
WARNINGS=localhost.warnings

TRASH=/tmp/trash.$$
DB=ref.db.test
trap "rm -f ${TRASH} ${DB}" EXIT

# Mac requires gsleep for subsecond sleeps, Linux doesn't.
if [ "x$(which gsleep | egrep -v 'not found')" = "x" ] ; then
    SLEEP=sleep
else
    SLEEP=gsleep
fi

# Mac requires gdate for %N
if [ "x$(which gdate | egrep -v 'not found')" = "x" ] ; then
    DATE=date
else
    DATE=gdate
fi


VERBOSE=
while getopts 'vh' OPTION; do
    case "$OPTION" in
        v)
            VERBOSE=-v
            ;;
        h)
            echo "usage: $0 [ -v ]" 1>&2
            exit 0
            ;;
    esac
done
shift "$(($OPTIND -1))"

dateit () {
    while read line ; do
        echo "$($DATE +%T.%N) ${line}"
    done
}

RUNCOV='coverage run -a --rcfile=.coveragerc'

runcov () {
    echo "cover: $1"
    ${RUNCOV} "$@"
}

if [ -d search_cache ] ; then
    rm -r search_cache
fi

export PORT=5001 HOST=localhost
(DOCOVER=true bash $(dirname $0)/run.sh 2>&1 | dateit > /tmp/$$.tmp) &
$SLEEP 2

rm -f localhost.comments
sed -e 's/localhost:[0-9][0-9]*/localhost:5001/' < localhost.urls \
    | while read line ; do
    if [ "x${line:0:1}" = "x#" ] ; then
        echo "${line}" | dateit >> localhost.comments
    else
        echo -n "." 1>&2
        echo "*** $line ***"
        curl -s $line
    fi
    $SLEEP 0.03
done  > $RAW
echo 1>&2

$SLEEP 1

pkill -f gunicorn

flask routes \
    | egrep --color=never 'GET|POST' \
    | sort > $ACT

# The HTTP/1.?1 pattern is because it appears Google Photos sometimes
# sends back HTTP/11... ¯\_(ツ)_/¯
sort localhost.comments /tmp/$$.tmp \
    | sed -e 's/^[0-9][0-9]:[0-9][0-9]:[0-9][0-9][.0-9]* //' \
          -e 's;.../.../....:..:..:.. -..... ;;' \
          -e 's;^.[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9] -[0-9]*. .[0-9]*. .INFO.;[INFO];' \
          -e 's:HTTP/1[.]*1" \([2-5][0-9][0-9]\) [0-9][0-9]*:HTTP/1.1" \1 <size>:' \
          -e 's:"curl/[0-9][0-9.]*.*:curl:' \
          -e 's:Starting gunicorn .*:Starting gunicorn:' \
          -e 's:/[^/]*/skip:~:' \
    | awk -f $(dirname $0)/filter.awk \
          >> $ACT
rm localhost.comments /tmp/$$.tmp

# Run our official unit tests
runcov $(which pytest) $VERBOSE
PYT=$?

# cover crcachectl script
find search_cache -name 'tmp*' | head -1 | xargs rm
runcov scripts/crcachectl.py -l
runcov scripts/crcachectl.py -l -v -d 126mm
runcov scripts/crcachectl.py --empty
runcov scripts/crcachectl.py -d bartali -q
runcov scripts/crcachectl.py -lq --delete-all
runcov scripts/crcachectl.py --delete-all
runcov scripts/crcachectl.py -lv
runcov scripts/crcachectl.py -qv

# The dates module is only used by a couple auxiliary scripts.
runcov scripts/listbydate.py CR/2000-03 >/dev/null
runcov scripts/generate_date_index.py -d references.db 2000 3 >/dev/null

# Exercise the thread index generator
runcov scripts/generate_thread_index.py -d references.db 2000 3 >/dev/null

# Exercise findlinks...
runcov scripts/findlinks.py CR/2004-01/eml-files/*.eml >/dev/null

# Exercise training...
echo 'yes
yes
retrain

foo
quit' | runcov scripts/training.py 'CR/2001-01/eml-files/*.eml' 15 >/dev/null

# Exercise listbydate...
runcov scripts/listbydate.py 'CR/2001-01/eml-files' >/dev/null

# makesitemap
runcov scripts/makesitemap.py

# idwj
find CR/2004-11/eml-files -name '*.eml' \
    | head -300 \
    | runcov scripts/idwj.py > /dev/null

# extracttbfromsyslog
runcov scripts/extracttbfromsyslog.py < syslog.www > /dev/null

# abs2rel
runcov scripts/abs2rel.py -n smontanaro/smontanaro/static/bikes/43bikes/derosa-web

# Small refdb run to exercise one or two functions only it uses.
runcov scripts/makerefsdb.py -d %{DB} CR/2000-10
runcov scripts/makerefsdb.py -c -d %{DB} --one \
       CR/2001-01/eml-files/classicrendezvous.10101.0001.eml
cp -p /etc/hosts ${TRASH}
runcov scripts/makerefsdb.py -d %{DB} --one ${TRASH}

# Exercise some bits only csv2topic uses
runcov scripts/csv2topic.py references.db < topic.csv > /dev/null

# Exercise the code used to build the sqlite search database
echo "CR/2007-11" | \
    CRDIR=$(pwd) coverage run -a scripts/buildindex.py -t train.csv srch.db.test

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

diff -wu localhost.exp $ACT && test $PYT -eq 0 && echo "success" || echo "failure"
