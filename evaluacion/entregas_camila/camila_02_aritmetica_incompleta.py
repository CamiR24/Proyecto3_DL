def emitir_binaria(destino, izquierda, operador, derecha):
    if operador == "+":
        return f"{destino} = {izquierda} + {derecha}"
    if operador == "-":
        return f"{destino} = {izquierda} - {derecha}"
    raise NotImplementedError("Multiplicación y división pendientes")
