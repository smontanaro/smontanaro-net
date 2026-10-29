#!/usr/bin/env python3

import curses
import sys
import time

def cursesex(scr):
    n = 1
    while True:
        row = 0
        scr.clear()
        scr.addstr(row, 0, "hello world")
        out = f"{n:6d} {'record[0]':16s} {'record[1]':6s} {'botname':16s} {'name'}"
        scr.addstr(row+1, 0, out)
        scr.addstr(row+2, 0, f"sleeping... {n}")
        row += 3
        n += 1
        scr.refresh()
        time.sleep(5)

if __name__ == "__main__":
    try:
        res = curses.wrapper(cursesex)
    except KeyboardInterrupt:
        res = 0
    sys.exit(res)
