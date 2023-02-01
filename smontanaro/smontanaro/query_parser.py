#!/usr/bin/env python3

"Parse search queries into a structured form"

# Queries can be simple strings (including "from:" or "subject:" prefixes)
# which can be connected by AND and OR and surrounded by parens.
#
# For example:
#
#    from:Brian Baylis AND (subject:Masi OR subject:Confente)

from sprdpl import lex, parse

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
        ('STRING', lambda p: ["search", p[0]]),
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
    query = query.replace("AND", "&&").replace("OR", "||")
    return _PARSER.parse(_LEXER.input(query))
