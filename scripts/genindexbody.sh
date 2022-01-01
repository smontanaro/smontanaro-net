#!/bin/bash

cd CR

echo "<ul>"

for f in 20??-??/html/threads.html ; do
    yr_mo=$(dirname $(dirname $f))
    yr=$(echo $yr_mo | awk -F- '{print $1}')
    mo=$(echo $yr_mo | awk -F- '{print $2}')
    echo "  <li>"
    echo "    ${yr}/${mo}:"
    for pair in threads.html/threads maillist.html/dates ; do
        f=$(dirname $pair)
        txt=$(basename $pair)
        echo "      <a href='${yr}/${mo}/${f}'>${txt}</a>"
    done
    echo "  </li>"
done

echo "</ul>"
