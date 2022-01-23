#!/bin/bash

# Run Flask server and throw a bunch of URLs at it. Compare with
# expected output.

# We diddle with localhost.exp toward the end. Make sure it's in
# a pristine state when we start.
git restore localhost.exp
ACT=/tmp/localhost.act
RAW=/tmp/localhost.raw
MSGIDS=/tmp/localhost.msgids

rm -f $ACT $MSGIDS $RAW

export PORT=5001 HOST=localhost
(DOCOVER=true bash run.sh > /tmp/$$.tmp 2>&1) &
sleep 2

sed -e 's/localhost:[0-9][0-9]*/localhost:5001/' < localhost.urls \
    | egrep -v '^ *#' \
    | while read url ; do
    echo "*** $url ***"
    curl -s $url
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
    # avoid spurious diffs
    echo '127.0.0.1 - - "GET /'${uri}' HTTP/1.1" 200 -' >> localhost.exp
done >> $RAW

sleep 1

pkill -f flask

egrep -v 'Running on|Debugger PIN|^INFO:werkzeug:127.0.0.1' < /tmp/$$.tmp \
    | sed -e 's;.../.../.... ..:..:... ;;' \
          -e 's/^.....-..-.. ..:..:..,.... //' \
          > $ACT

# More potentially deceptive diffs. Save these warnings, realizing we
# expect them on occasion.
egrep 'WARNING in views: failed to locate' $ACT > $MSGIDS
egrep -v 'WARNING in views: failed to locate' $ACT > /tmp/$$.tmp
mv /tmp/$$.tmp $ACT

if [ -s $MSGIDS ] ; then
    echo "Note warnings in localhost.msgids"
fi

# The dates module is only used by a couple auxiliary scripts.
PYTHONPATH=$PWD/smontanaro coverage run -a --rcfile=.coveragerc \
         scripts/listbydate.py CR/2000-03 >/dev/null
PYTHONPATH=$PWD/smontanaro coverage run -a --rcfile=.coveragerc \
         scripts/generate_date_index.py -d references.db 2000 3 >/dev/null

coverage html
