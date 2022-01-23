#!/bin/bash

EXP="HTTP/1.1 200 OK"

ACT=$(curl -s --head https://www.smontanaro.net/CR/2008/09/0002 \
          | head -1)

if [ "$EXP" != "$ACT" ] ; then
    echo "Problem fetching URL head." 1>&2
    echo "Expected: $EXP" 1>&2
    echo "Actual: $ACT" 1>&2
    exit 99
fi

EXP="<p>Regards,   Toni Theilmeier, Belm, Germany."
ACT=$(curl -s https://www.smontanaro.net/CR/2008/09/0002 \
          | egrep 'Toni Theilmeier, Belm, Germany')

if [ "$EXP" != "$ACT" ] ; then
    echo "Problem fetching URL." 1>&2
    echo "Expected: $EXP" 1>&2
    echo "Actual: $ACT" 1>&2
    exit 99
fi

exit 0
