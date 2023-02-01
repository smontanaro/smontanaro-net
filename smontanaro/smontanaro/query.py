#!/usr/bin/env python3

"Parse search queries into a structured form"

# Queries can be simple strings (including "from:" or "subject:" prefixes)
# which can be connected by AND and OR and surrounded by parens.
#
# For example:
#
#    from:Brian Baylis AND (subject:Masi OR subject:Confente)

import regex as re
from sprdpl import lex, parse

from .srchdb import SRCHDB

_TABLE = {
    'AND':        r'&&',
    'OR':         r'[|][|]',
    'LPAREN':     r'[(]',
    'RPAREN':     r'[)]',
    'STRING':     r'[-_.:@a-zA-Z0-9]+(?:\s+[-_.:@a-zA-Z0-9]+)*',
    'SPACE':      (r'\s+', lambda t: None),

}
_LEXER = lex.Lexer(_TABLE)

def reduce_binop(op, p):
    # print(f">>> {op} {p[:]} {len(p[:])}")
    if not p[1]:
        # print(":::", p[0])
        return p[0]
    # print(f"::: {op}", [p[0], p[1][0][1]])
    return [op, p[0], p[1][0][1]]

_RULES = [
    [
        'atom',
        ('STRING', lambda p: ["search", p[0].lower()]),
        ('LPAREN expr RPAREN', lambda p: p[1]),
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
    query = re.sub(r"\bOR\b", "||", re.sub(r"\bAND\b", "&&", query))
    return _PARSER.parse(_LEXER.input(query))

def execute_query(query):
    "parse and execute parts of a possibly compound query"
    return execute_structured_query(parse_query(query))

def execute_structured_query(query):
    "execute a structured query"
    # query is a list. The first word in each list element is one of:
    # 'search' - perform search for the second element (a string)
    # 'intersect' - perform searches for the second and third elements (lists),
    #     then intersect them
    # 'union' - perform searches for the second and third elements (lists),
    #     then combine them

    results = []
    match query:
        case ["search", search]:
            results.extend(SRCHDB.get_page_fragments(search))
        case [action, query1, query2]:
            res1 = dict(execute_structured_query(query1))
            res2 = dict(execute_structured_query(query2))
            match action:
                case "intersect":
                    # intersect the filenames - page fragments are secondary here
                    for page in set(res1) & set(res2):
                        results.append((page, res1.get(page) or res2.get(page)))
                case "union":
                    # intersect the filenames - page fragments are secondary here
                    for page in set(res1) | set(res2):
                        results.append((page, res1.get(page) or res2.get(page)))
        case _:
            raise ValueError(f"Unrecognized query structure: {query}")
    return sorted(results)
