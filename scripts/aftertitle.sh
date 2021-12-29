#/bin/bash

for file in "$@" ; do
    echo $file
    if [ ! -r ${file}.orig ] ; then
        cp -p ${file} ${file}.orig
    fi

    sed -e '/^<title>.*/a <meta http-equiv="content-type" content="text/html; charset="utf-8" />\n<link rel="stylesheet" type="text/css" href="/static/css/default.css" />' < ${file} > ${file}.new
    mv ${file}.new ${file}
done
