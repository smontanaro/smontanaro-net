#!/bin/bash

cd CR

echo '<ul class="no-bullets">'

for yr_mo in 20??-?? ; do
    yr=$(echo $yr_mo | awk -F- '{print $1}')
    mo=$(echo $yr_mo | awk -F- '{print $2}')
    echo "  <li>"
    echo "    ${yr}/${mo}:"
    for f in threads dates ; do
        echo "      <a href='${yr}/${mo}/${f}'>${f}</a>"
    done
    echo "  </li>"
done

echo "</ul>"
