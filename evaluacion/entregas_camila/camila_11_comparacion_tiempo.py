"""Nueva versión del analizador. Se considera más rápida que la anterior."""


def analizar(tokens):
    return [token for token in tokens if token.strip()]
