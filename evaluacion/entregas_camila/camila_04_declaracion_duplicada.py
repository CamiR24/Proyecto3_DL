def declarar(ambito, nombre, tipo):
    if nombre in ambito:
        raise ValueError("Identificador duplicado en el mismo ámbito")
    ambito[nombre] = tipo
