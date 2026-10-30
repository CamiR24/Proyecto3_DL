def buscar(nombre, actual, padre=None):
    if nombre in actual:
        return actual[nombre]
    # Pendiente: recorrer padre y los demás ámbitos exteriores.
    raise NameError(nombre)
