class Etiquetas:
    def __init__(self):
        self.contador = 0

    def nueva(self):
        nombre = f"L{self.contador}"
        self.contador += 1
        return nombre
