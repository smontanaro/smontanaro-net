BEGIN {
    end = 0;
}

/end - place new lines/ {
    end = 1;
}
/ 200 .*curl/ {
    if (end == 1)
        next
}
/.*/ {
    print
}
