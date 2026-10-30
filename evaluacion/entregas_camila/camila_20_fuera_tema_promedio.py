def promedio_calificaciones(calificaciones):
    if not calificaciones:
        return 0
    return sum(calificaciones) / len(calificaciones)
