"""Analizador léxico de Compiscript escrito a mano, sin herramientas generadoras."""
import re

TOKENS = [
    ('NUM', r'\d+(\.\d+)?'),
    ('ID', r'[A-Za-z_]\w*'),
    ('OP', r'[+\-*/%=<>!]=?|&&|\|\|'),
    ('SYM', r'[(){};,:\[\]]'),
    ('WS', r'\s+'),
]


def tokenize(source):
    """Recorre el texto y devuelve (tipo, lexema); se detiene en el primer error."""
    pos, result = 0, []
    while pos < len(source):
        for name, pattern in TOKENS:
            match = re.compile(pattern).match(source, pos)
            if match:
                if name != 'WS':
                    result.append((name, match.group()))
                pos = match.end()
                break
        else:
            raise SyntaxError(f'Carácter inesperado en la posición {pos}')
    return result
