#!/bin/bash

cd CR

echo '<ul style="column-count: 4" class="no-bullets">'

for yr_mo in 20??-?? ; do
    yr=$(echo $yr_mo | awk -F- '{print $1}')
    mo=$(echo $yr_mo | awk -F- '{print $2}')
    echo "  <li>"
    if [ $mo = "01" ] ; then
        echo "    <b>${yr}/${mo}</b>:"
    else
        echo "    ${yr}/${mo}:"
    fi
    for f in threads dates ; do
        echo "      <a href='${yr}/${mo}/${f}'>${f}</a>"
    done
    echo "  </li>"
done

echo "</ul>"
