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
