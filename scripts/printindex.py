#!/usr/bin/env python3

"""
trivial little script to check buildindex.py-generated keys
"""

import pickle
import sys

from smontanaro.util import open_

if __name__ == "__main__":
    with open_(sys.argv[1], "rb") as fobj:
        word_map = pickle.load(fobj)

    for key in sorted(word_map):
        print(f"{key}: {len(word_map[key])}")
