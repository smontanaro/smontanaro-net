#!/usr/bin/env python3

"display text for a random sample of emails"

import glob
import os
import random
import sys

from textblob import TextBlob
from textblob.classifiers import NaiveBayesClassifier

from smontanaro.util import read_message

BOLD = "\x1B[1m"
NORM = "\x1B[m"

def train():
    with open("train.csv", "r", encoding="utf-8") as fp:
        cl = NaiveBayesClassifier(fp, format="csv")
    return cl


def process_one(f, cl):
    msg = read_message(f)
    print("From:", msg["from"])
    print("Subject:", msg["subject"])
    print()

    text = msg.extract_text()
    blob = TextBlob(text)
    upper = 0.65
    lower = 0.35
    for sent in blob.sentences:
        print("-" * 25)
        prob_dist = cl.prob_classify(sent)
        pos_prob = round(prob_dist.prob("pos"), 2)
        neg_prob = round(prob_dist.prob("neg"), 2)
        unsure = lower < pos_prob < upper
        score = prob_dist.max()
        sent = str(sent).replace(" \n", " ")
        if unsure:
            print(BOLD, end="")
        print("score:", score, "pos:", pos_prob, "neg:", neg_prob)
        print(">", sent.replace("\n", " ").replace("\r ", " ").replace("\r", ""))
        if unsure:
            print(NORM, end="")

def view_subset(pattern, n):
    cl = train()
    files = glob.glob(pattern)
    random.shuffle(files)

    result = 0
    for f in files[:n]:
        os.system("clear")                # nosec
        print(f)
        print()

        process_one(f, cl)

        match (response := input("continue [y]/q/r(etrain)? ").lower()): # nosec
            case "q" | "quit":
                break
            case "r" | "retrain":
                cl = train()
                process_one(f, cl)
                input("press RET to continue... ")
            case "y" | "yes" | "":
                pass
            case _:
                print(f"unrecognized response: {response}", file=sys.stderr)
                continue

    return result


if __name__ == "__main__":
    try:
        sys.exit(view_subset(sys.argv[1], int(sys.argv[2])))
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
