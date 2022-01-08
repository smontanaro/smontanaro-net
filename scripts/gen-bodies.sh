#!/bin/bash

for yr_mo in CR/2???-?? ; do
    yr_mo=$(basename $yr_mo)
    yr=$(echo $yr_mo | awk -F- '{print $1}')
    mo=$(echo $yr_mo | awk -F- '{print $2}')
    echo ${yr}/${mo}
    outdir=CR/${yr_mo}/generated
    mkdir -p ${outdir}
    python scripts/generate_date_index.py -d references.db $yr $mo \
           > ${outdir}/dates.body
    python scripts/generate_thread_index.py -d references.db $yr $mo \
           > ${outdir}/threads.body
done
