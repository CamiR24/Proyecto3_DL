def emitir_binaria(destino, izquierda, operador, derecha):
    if operador not in {"+", "-", "*", "/"}:
        raise ValueError("Operador aritmético no admitido")
    return f"{destino} = {izquierda} {operador} {derecha}"
