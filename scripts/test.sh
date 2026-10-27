#!/bin/bash

. venv/bin/activate

if [ "x$CRDIR" = "x" ] ; then
    export CRDIR=$(pwd)
fi
if [ "x$PYTHONPATH" = "x" ] ; then
    export PYTHONPATH=$(pwd)/smontanaro
fi

export TESTING=/tmp/$$.pid

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
trap "rm -f ${TESTING} ${TRASH} ${DB} localhost.comments /tmp/$$.tmp" EXIT

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

run () {
    echo "run: $1" 1>&2
    python "$@"
}

VERBOSE=
export DOCOVER=
export DOPROFILE=
while getopts 'vhcp' OPTION; do
    case "$OPTION" in
        c)
	    export DOCOVER=true
            RUNCOV='coverage run -a --rcfile=.coveragerc'
            run () {
                echo "cover: $1" 1>&2
                ${RUNCOV} "$@"
            }
            ;;
        p)
            export DOPROFILE=true
            RUNPROF='python3 -m profiling.sampling run'
            run () {
                echo "profile: $1" 1>&2
                ${RUNPROF} "$@"
            }
            ;;
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

if [ "x${DOPROFILE}${DOCOVER}" = "xtruetrue" ] ; then
    echo "Can't profile and cover in the same run" 1>&2
    exit 2
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
(bash $(dirname $0)/run.sh 2>&1 | dateit > /tmp/$$.tmp) &
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

kill $(cat ${TESTING})

flask routes \
    | egrep --color=never 'GET|POST' \
    | sed -e 's/[ ]*$//' > $ACT

# The HTTP/1.?1 pattern is because it appears Google Photos sometimes
# sends back HTTP/11... ¯\_(ツ)_/¯
sort localhost.comments /tmp/$$.tmp \
    | sed -e 's/^[0-9][0-9]:[0-9][0-9]:[0-9][0-9][.0-9]* //' \
          -e 's:HTTP/1[.]*1" \([2-5][0-9][0-9]\) [0-9][0-9]*:HTTP/1.1" \1 <size>:' \
          -e "s:~/:${HOME}/:" \
          -e "s:${CRDIR}:CRDIR:" \
          -e 's/ERROR:root://' \
          -e 's:"curl/[0-9][0-9.]*.*:curl:' \
          -e 's/[[][^]]*] //g' \
	  -e 's:Starting gunicorn .*:Starting gunicorn:' \
          -e "s:${HOME}:~:" \
    | egrep -v '^WORKER TIMEOUT|^Debug mode enabled|^DEBUG:urllib3.connectionpool' \
    | awk -f scripts/filter.awk \
    >> $ACT

# Run our official unit tests
run $(which pytest) $VERBOSE smontanaro
PYT=$?

# cover crcachectl script
find search_cache -name 'tmp*' | head -1 | xargs rm
run scripts/crcachectl.py -l > /dev/null
run scripts/crcachectl.py -l -v -d 126mm > /dev/null
run scripts/crcachectl.py --empty > /dev/null
run scripts/crcachectl.py -d bartali -q
run scripts/crcachectl.py -lq --delete-all > /dev/null
run scripts/crcachectl.py --delete-all
run scripts/crcachectl.py -lv > /dev/null
run scripts/crcachectl.py -qv

# The dates module is only used by a couple auxiliary scripts.
run scripts/listbydate.py CR/2000-03 >/dev/null
run scripts/generate_date_index.py -d references.db 2000 3 >/dev/null

# Exercise the thread index generator
run scripts/generate_thread_index.py -d references.db 2000 3 >/dev/null

# Exercise findlinks...
run scripts/findlinks.py CR/2004-01/eml-files/*.eml >/dev/null

# Exercise training...
echo 'yes
yes
retrain

foo
quit' | run scripts/training.py 'CR/2001-01/eml-files/*.eml' 15 >/dev/null

# Exercise listbydate...
run scripts/listbydate.py 'CR/2001-01/eml-files' >/dev/null

# makesitemap
run scripts/makesitemap.py

# idwj
find CR/2004-11/eml-files -name '*.eml' \
    | head -300 \
    | run scripts/idwj.py > /dev/null

if [ -r syslog.www ] ; then
    # extracttbfromsyslog
    run scripts/extracttbfromsyslog.py < syslog.www > /dev/null
fi

# abs2rel
### To Do: need a better directory & html file(s) for the test
SCANDIR=smontanaro/smontanaro/static/bikes/43bikes/fortythree/merlin-web
run scripts/abs2rel.py -n ${SCANDIR}
run scripts/abs2rel.py ${SCANDIR}
for old in ${SCANDIR}/old*.html ; do
    new=$(sed -e 's:/old-::' <<<${old})
    mv ${old} ${new}
done

if [ -d /var/log/nginx ] ; then
    files="/var/log/nginx/access.log.1 /var/log/nginx.access.log"
else
    files="/Users/skip/tmp/access.log.1 /Users/skip/tmp/access.log"
fi
run scripts/watchaccesslog.py -s -n 500 ${files} 2>/tmp/trash < /dev/null

# Small refdb run to exercise one or two functions only it uses.
run scripts/makerefsdb.py -d %{DB} CR/2000-10
run scripts/makerefsdb.py -c -d %{DB} --one \
       CR/2001-01/eml-files/classicrendezvous.10101.0001.eml
cp -p /etc/hosts ${TRASH}
run scripts/makerefsdb.py -d %{DB} --one ${TRASH}

run scripts/getua.py < sample.log > /dev/null
run scripts/extracttbfromsyslog.py < sample-syslog > /dev/null
head -100 sample-syslog | run scripts/extracttbfromsyslog.py > /dev/null

# Exercise some bits only csv2topic uses
run scripts/csv2topic.py references.db < topic.csv > /dev/null

# Exercise the code used to build the sqlite search database
echo "CR/2007-11" | \
    CRDIR=$(pwd) run scripts/buildindex.py -t train.csv srch.db.test

n=$(echo "select * from search_terms where term = 'from:dale brown'" | sqlite3 srch.db.test | wc -l)
m=$(echo "select * from search_terms where term like 'from:% '" | sqlite3 srch.db.test | wc -l)
rm -f srch.db.test
if [ $n -eq 0 -o $m -gt 0 ] ; then
    echo "$(tput bold)Error generating from: terms$(tput sgr0)" 1>&2
fi

if [ "x$DOCOVER" != "x" ] ; then
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
fi

diff -wub localhost.exp $ACT && test $PYT -eq 0 && echo "success" || echo "failure"
