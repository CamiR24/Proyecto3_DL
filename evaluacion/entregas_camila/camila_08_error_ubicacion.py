def error_lexico(caracter, linea, columna):
    return {
        "tipo": "lexico",
        "mensaje": f"Carácter no permitido: {caracter!r}",
        "linea": linea,
        "columna": columna,
    }
