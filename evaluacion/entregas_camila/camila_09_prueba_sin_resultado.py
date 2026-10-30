def dividir(a, b):
    if b == 0:
        raise ValueError("División entre cero")
    return a / b


def test_division_cero():
    try:
        dividir(8, 0)
    except ValueError:
        return
    raise AssertionError("Debía rechazar división entre cero")
