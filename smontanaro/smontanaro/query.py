#!/usr/bin/env python3

"Parse search queries into a structured form"

# Queries can be simple strings (including "from:" or "subject:" prefixes)
# which can be connected by AND and OR and surrounded by parens. Terms can be
# prefixed by NOT as well, though it's use is limited.
#
# For example:
#
#    from:Brian Baylis AND (subject:Masi OR subject:Confente)

from dataclasses import dataclass, field as datafield

import regex as re
from sprdpl import lex, parse

from .srchdb import SRCHDB


_TABLE = {
    'NOT':        r'~',
    'AND':        r'&&',
    'OR':         r'[|][|]',
    'LPAREN':     r'[(]',
    'RPAREN':     r'[)]',
    'STRING':     r'[-_.:@a-zA-Z0-9/]+(?:\s+[-_.:@a-zA-Z0-9/]+)*',
    'SPACE':      (r'\s+', lambda t: None),

}
_LEXER = lex.Lexer(_TABLE)

def reduce_binop(op, p):
    result = p[0]
    for element in p[1]:
        result = [op, element[1], result]
    return result

_RULES = [
    [
        'atom',
        ('STRING', lambda p: ["search", p[0].lower()]),
        ('LPAREN expr RPAREN', lambda p: p[1]),
        ('NOT atom', lambda p: ["not", p[1]]),
    ],
    [
        'term',
        ('atom (AND atom)*', lambda p: reduce_binop("intersect", p)),
    ],
    [
        'expr',
        ('term (OR term)*', lambda p: reduce_binop("union", p)),
    ],
]

_PARSER = parse.Parser(_RULES, 'expr')

def parse_query(query):
    query = re.sub(r"\bOR\b", "||", query)
    query = re.sub(r"\bAND\b", "&&", query)
    query = re.sub(r"\bNOT\b", "~", query)
    return _PARSER.parse(_LEXER.input(query))

def execute_query(query):
    "parse and execute parts of a possibly compound query"
    parsed_query = parse_query(query)
    return execute_structured_query(parsed_query)

@dataclass
class SearchResult:
    "result of a search (compound or simple)"
    data: dict = datafield(default_factory=dict)
    negate: bool = False

    def pages(self):
        return set(self.data.keys())

    def get(self, key):
        return self.data.get(key)

    def __getitem__(self, key):
        return self.data[key]

    def __contains__(self, fname):
        return fname in self.data

    def __eq__(self, other):
        return self.data == other.data and self.negate == other.negate

    def __len__(self):
        return len(self.data)

def execute_structured_query(query):
    "execute a structured query"
    # query is a list. The first word in each list element is one of:
    # 'search' - perform search for the second element (a string)
    # 'intersect' - perform searches for the second and third elements (lists),
    #     then intersect them
    # 'union' - perform searches for the second and third elements (lists),
    #     then combine them

    match query:
        case ["search", search]:
            records = {}
            for (fname, frag, subj, sender) in SRCHDB.get_page_fragments(search):
                records[fname] = (frag, subj, sender)
            result = SearchResult(records)
        case ["not", search]:
            result = execute_structured_query(search)
            result.negate = True
        case [action, query1, query2]:
            res1 = execute_structured_query(query1)
            res2 = execute_structured_query(query2)
            match action:
                case "intersect":
                    # intersect the filenames - page fragments are secondary here
                    if res1.negate and res2.negate:
                        raise ValueError("NOT may only be used with one of the AND queries")
                    if res1.negate:
                        pages = res2.pages() - res1.pages()
                    elif res2.negate:
                        pages = res1.pages() - res2.pages()
                    else:
                        pages = res1.pages() & res2.pages()
                    data = {}
                    for page in pages:
                        data[page] = res1.get(page) or res2.get(page)
                    result = SearchResult(data)
                case "union":
                    if res1.negate or res2.negate:
                        raise ValueError("NOT may only be used with AND queries")
                    data = {}
                    for page in res1.pages() | res2.pages():
                        data[page] = res1.get(page) or res2.get(page)
                    result = SearchResult(data)
                case _:
                    raise ValueError(f"Unrecognized query structure: {query}")
        case _:
            raise ValueError(f"Unrecognized simple query verb: {query}")

    return result
