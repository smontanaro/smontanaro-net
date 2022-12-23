#!/usr/bin/env python

"""An attempt at implementing JWZ's threading algorithm

https://www.jwz.org/doc/threading.html
"""

import glob
import pprint
import sys

import regex as re

from smontanaro.util import (Message, read_message, clean_msgid,
                             trim_subject_prefix, eprint)

class TMessage:
    "JWZ's Message object"
    def __init__(self, message: Message):
        # save for debugging...
        self.message = message
        self.references = []
        self.subject = str(message["Subject"]).strip()
        self.clean_subject = trim_subject_prefix(self.subject)
        self.is_reply = self.subject.lower().startswith("re:")
        self.msgid = message["Message-ID"]
        self.source = None

        self.build_references(message)

    def build_references(self, message):
        for field in ("References", "In-Reply-To"):
            for tgt_msgid in re.findall(r"<[^>]+>", (message[field] or "")):
                ref = clean_msgid(tgt_msgid)
                if ref not in self.references:
                    print("add", ref)
                    self.references.append(ref)

    def __str__(self):
        return (f"""<Message subject={self.subject} is_reply={self.is_reply}"""
                f""" msgid={self.msgid} references={self.references}>""")
    __repr__ = __str__

class Container:
    "JWZ's Container object"
    def __init__(self, tmsg: TMessage=None, parent: 'Container'=None, child: 'Container'=None,
                 next_: 'Container'=None):
        self.tmsg = tmsg
        self.parent = parent
        self.child = child
        self.next = next_

    def __str__(self):
        return (f"""<Container parent={hex(id(self.parent))}"""
                f""" message={self.tmsg}""")
    #__repr__ = __str__

    def empty(self):
        return self.tmsg is None

class ThreadTable:
    "encapsulate logic for incremental exploration of JWZ's algorithm"
    def __init__(self):
        self.id_table = {}
        self.messages = {}

    def add_message(self, eml_file):
        if eml_file not in self.messages:
            msg = TMessage(read_message(eml_file))
            msg.source = eml_file
            self.messages[eml_file] = msg
        return self.messages[eml_file]

    def contain_message(self, msg):
        cont = self.id_table.get(msg.msgid)
        if cont is None:
            cont = Container(msg)
            self.id_table[msg.msgid] = cont
        else:
            if cont.empty():
                cont.message = msg

        containers = []
        for ref in msg.references:
            c = self.id_table.get(ref)
            if c is None:
                c = self.id_table[ref] = Container()
            if c.parent is None and containers:
                # provisional parent
                c.parent = containers[-1]
            containers.append(c)
        if containers:
            cont.parent = containers[-1]

    def build_table(self, pattern):
        n = 0
        for eml_file in glob.glob(pattern):
            n += 1
            if n % 1000 == 0:
                print(n, end=" ")
                sys.stdout.flush()

            tmsg = self.add_message(eml_file)
            self.contain_message(tmsg)
        print(n)

    def container_chain(self, container):
        "return list of constructed parent message ids"
        message_ids = []
        seen = set()
        while container is not None:
            assert container not in seen, (container, seen) # nosec
            seen.add(container)
            if container.message is not None:
                msgid = container.message.msgid
            else:
                msgid = None
            print("c", container, msgid)
            if msgid is not None and msgid in message_ids:
                eprint(">>", msgid, "already in chain!")
                break
            message_ids.append(msgid)
            pprint.pprint(message_ids)
            assert container is not container.parent # nosec
            container = container.parent
        return message_ids[::-1]
