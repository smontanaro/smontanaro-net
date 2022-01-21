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
(bash run.sh 2>&1 \
     | egrep -v 'Running on|Debugger PIN' \
     | sed -e 's;.../.../.... ..:..:... ;;' \
           -e 's/^.....-..-.. ..:..:..,.... //' \
     | tee $ACT) &
sleep 3

sed -e 's/localhost:[0-9][0-9]*/localhost:5001/' < localhost.urls \
    | while read url ; do
    echo "*** $url ***"
    curl -s $url
done  > $RAW

# grab a few random pages

for d in $(find CR/ -name '20??-??' \
               | shuffle \
               | head -13) ; do
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

sleep 2

# More potentially deceptive diffs. Save these warnings, realizing we
# expect them on occasion.
egrep 'WARNING in views: failed to locate' $ACT > $MSGIDS
egrep -v 'WARNING in views: failed to locate' $ACT > /tmp/$$.tmp
mv /tmp/$$.tmp $ACT

if [ -s $MSGIDS ] ; then
    echo "Note warnings in localhost.msgids"
fi

pkill -f flask
