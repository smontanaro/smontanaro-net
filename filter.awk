BEGIN {
    end = 0;
}

/:5001|Booting worker|Handling signal: term|Worker exiting/ {
    next
}

/end - place new lines/ {
    end = 1;
}

/ 200 .*curl/ {
    if (end == 1)
        next
    else
        print
}

{ print }
