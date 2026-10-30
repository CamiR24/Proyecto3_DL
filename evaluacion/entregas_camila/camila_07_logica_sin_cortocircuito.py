def emitir_and(destino, emitir_izquierda, emitir_derecha):
    codigo_a, valor_a = emitir_izquierda()
    codigo_b, valor_b = emitir_derecha()
    return codigo_a + codigo_b + [f"{destino} = {valor_a} && {valor_b}"]
