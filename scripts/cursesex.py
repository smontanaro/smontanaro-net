#!/usr/bin/env python3

import curses

def cursesex(scr):
    scr.clear()
    scr.addstr(0, 0, "hello world")
    scr.addstr(1, 0, "hit any key to exit")
    scr.refresh()
    scr.get_wch()

if __name__ == "__main__":
    curses.wrapper(cursesex)
