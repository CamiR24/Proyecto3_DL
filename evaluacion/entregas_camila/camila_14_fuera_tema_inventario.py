def total_inventario(productos):
    return sum(producto["precio"] * producto["cantidad"] for producto in productos)
