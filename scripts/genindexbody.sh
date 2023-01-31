#!/bin/bash

cd CR

echo '<ul style="column-count: auto; column-width: 250px" class="no-bullets">'

for yr_mo in 20??-?? ; do
    yr=$(echo $yr_mo | awk -F- '{print $1}')
    mo=$(echo $yr_mo | awk -F- '{print $2}')
    echo -n "  <li> "
    if [ $mo = "01" ] ; then
        echo -n "<b>${yr}-${mo}</b>:"
    else
        echo -n "${yr}-${mo}:"
    fi
    for f in threads dates ; do
        echo -n " <a href='/CR/${yr}/${mo}/${f}'>${f}</a>"
    done
    echo -n "  </li>"
    echo
done

echo "</ul>"
