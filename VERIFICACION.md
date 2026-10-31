# Verificación actual y registro histórico

## Auditoría del ZIP recibido

- Python 3.12.14: 77 pruebas automatizadas aprobadas, sin API ni Docker.
- Validador: 40 casos en dos archivos, 30 dev / 10 test, 0 pendientes de validación humana.
- Interfaz: v2 seleccionado; inicio, nuevo orden de campos y tamaños ampliados presentes.
- Docker: se verificó el registro aportado de cinco pruebas aprobadas; no se volvió a ejecutar aquí.
- Modelo real: se verificaron JSON de corridas y la traza de una solicitud de herramienta; no hubo nuevas llamadas.
- Se auditaron 16 corridas originales; dos de v2 están incompletas (3/15 resultados).
- Las cifras de Camila no cambian. Dos baseline de Marinés pasan de 10/15 a 8/15 con las referencias actuales.
- La “Iteración 2” global y la comparación baseline/v2 sobre diez test no están en este ZIP.
- El mínimo de Python no está certificado: 3.12 es la versión recomendada comprobada; 3.9.6 aparece en corridas históricas.
- Las capturas, el video y el ensayo no están acreditados en este paquete.

Ver `evaluacion/AUDITORIA_ENTREGA.md` y la auditoría de puntuaciones separada. Las verificaciones históricas siguientes describen el estado inicial y no los pendientes actuales.

---

# Verificación de la versión inicial

Fecha: 26 de octubre de 2026.

## Comprobado en el entorno de desarrollo

- 18 pruebas automatizadas aprobadas: lectura y filtrado de ZIP, rutas fuera de alcance, enlaces simbólicos, cobertura parcial, referencias inexistentes, ejecución inventada, pruebas fallidas, herramientas no permitidas y flujo HTTP real.
- El flujo HTTP se probó con un servidor local real y respuestas de modelo simuladas exclusivamente dentro de las pruebas automatizadas. No constituye una evaluación de calidad de un LLM real.
- Ejemplo de Compiscript: 295 archivos en el ZIP reducido; se seleccionan 37 documentos para contexto, con advertencias explícitas de recorte y archivos omitidos. Se conservan 43 archivos Python para el perfil aislado.
- Se cargan 24 criterios iniciales preparados manualmente. Las ocho referencias semilla siguen pendientes de validación humana.
- Lectura del PDF aportado mediante pypdf y comprobación sintáctica de Python y JavaScript.
- Sin Docker configurado, el ejecutor devuelve un estado no disponible y no ejecuta el código en el host.

## Pendiente antes de presentar

- Construir la imagen Docker y ejecutar `python scripts/check_runner.py` en la computadora de presentación. No se ejecutó ningún código del proyecto del alumno durante estas comprobaciones.
- Configurar un modelo real, verificar compatibilidad, costo, latencia, JSON y llamada a herramientas.
- Probar la interfaz en un navegador real de escritorio y móvil. El entorno no disponía de un binario de navegador para inspección visual automatizada.
- Validar calidad de las revisiones con referencias humanas y ampliar el conjunto de evaluación.
- Comprobar el flujo con compañeros, corregir problemas y preparar un video de respaldo de una ejecución real.

Los archivos entregados son un prototipo funcional de desarrollo; estas limitaciones no deben presentarse como verificaciones ya realizadas.
