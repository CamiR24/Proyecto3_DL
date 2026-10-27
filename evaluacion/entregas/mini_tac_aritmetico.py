"""Generador mínimo de código de tres direcciones para expresiones aritméticas con enteros."""


class Generador:
    def __init__(self):
        self.codigo = []
        self.contador = 0

    def nuevo_temporal(self):
        self.contador += 1
        return f'$t{self.contador}'

    def expresion(self, nodo):
        if isinstance(nodo, int):
            return str(nodo)
        operador, izquierda, derecha = nodo
        a = self.expresion(izquierda)
        b = self.expresion(derecha)
        destino = self.nuevo_temporal()
        self.codigo.append(f'{destino} = {a} {operador} {b}')
        return destino


def generar(arbol):
    generador = Generador()
    generador.expresion(arbol)
    return generador.codigo
