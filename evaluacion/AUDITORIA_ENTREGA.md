# Auditoría de cierre del Proyecto 3

## Resultado comprobado

77 pruebas aprobadas con Python 3.12.14. Los 40 casos pasan el validador y están validados por la otra integrante. No se hicieron llamadas al modelo ni se volvió a ejecutar Docker durante esta auditoría.

| Pendiente | Estado y acción |
| --- | --- |
| Prompt | La interfaz selecciona v2; conservar la decisión tomada con desarrollo. No elegir a partir de test. |
| Usuarios | Dos usuarios, tres sugerencias implementadas y valoración positiva de la versión nueva, según Camila. No hay tiempos ni comprensión medida por estado. |
| Capturas | No hay capturas de interfaz en el ZIP. Incorporar inicio, carga, criterios y evidencia expandida reales. |
| Docker | Registro directo: cinco aprobadas, executed=true y 0.969 s. Falta fecha de ejecución en ese JSON. |
| Herramienta del LLM | Registro real en revision_v2_herramienta.json: origen model_tool, runner_invoked=true y sin reutilización. |
| Precios | Verificados en fuente oficial, consulta del 30 de octubre de 2026. Incorporar condiciones y enlace. |
| Python | Corridas históricas: 3.9.6. Camila: 3.12.5. Auditoría actual: 3.12.14. No hay matriz de ejecución de la versión actual en 3.9/3.11. |
| Problema y umbrales | Usuario y alternativas desarrollados. No se fijaron umbrales numéricos previos; no inventarlos retrospectivamente. |
| Estados | Convención registrada en evaluacion/README.md. Las alternativas aceptables son exclusivamente las de cada caso. |
| Validación ciega | Opcional y no realizada; la actual fue asistida y no ciega. |
| Corridas | 16 originales: 11 históricos de Marinés y cinco de Camila. Dos históricos v2 están incompletos. |
| Video y ensayo | No hay MP4 ni constancia de ensayo en el ZIP. Confirmar o completar. |

## Resultados y discrepancias con el borrador

- Desarrollo histórico de Marinés con referencias actuales: baseline 10/15, 8/15 y 8/15; v1 12/15, 9/15 y 10/15; v2 completo 12/15, 12/15 y 11/15.
- Dos baseline históricos guardaban 10/15 y pasan a 8/15 por las referencias acordadas. Otros aciertos de evidencia también cambian aunque no cambie la exactitud.
- Los dos primeros intentos de v2 solo tienen tres respuestas de quince. Usan otro hash del prompt y no deben compararse por porcentaje con corridas completas.
- Desarrollo inicial de Camila: baseline 11/15 en ambas repeticiones; v2 13/15 y 12/15. Puntuaciones sin cambios con las referencias actuales.
- Test de Camila: una corrida de v2, 3/5, macro-F1 0.542 y ninguna falla grave registrada.
- No están los JSON de la segunda iteración de Camila, tres repeticiones por configuración en test ni la comparación de baseline 6/10 contra v2 4/10. Esas cifras del borrador no quedan verificadas con este ZIP. Solicitar los originales o retirarlas del informe.
- El enunciado actual de componentes difiere en hash del usado en las cuatro corridas dev de Camila. Sus respuestas siguen siendo evidencia histórica de aquel contexto; no representan una ejecución con las instrucciones actuales. El test de Camila sí coincide con el enunciado actual. No interpretar dev frente a test como comparación controlada con instrucciones idénticas.

El detalle por corrida y las puntuaciones recalculadas están en auditoria_corridas_20261030.json. Conserva los originales: el recálculo no simula referencias o contextos que no existían al ejecutar.

## Tarifa verificada

Fuente: https://platform.claude.com/docs/en/models/haiku-5-5/overview#pricing

Consulta: 30 de octubre de 2026.

| Entrada por solicitud | USD/millón entrada | USD/millón salida |
| --- | --- | --- |
| Hasta 100,000 tokens | 0.10 | 0.50 |
| Más de 100,000 tokens | 0.50 | 2.50 |

El umbral se aplica por solicitud, no a la suma de una revisión con dos llamadas. Caché y otras modalidades tienen precios propios. El código actual estima costos con precios planos configurados: verificar el tramo si una solicitud supera el umbral. Las cifras no son una factura.

## Fecha y alcance de Docker

Comando utilizado:

```bash
ENABLE_RUNNER=1 python scripts/check_runner.py > evaluacion/runner_compiscript_v1.json
```

El JSON directo no registra fecha. Para conocer cuándo se guardó en Git:

```bash
git log --follow --format="%h %aI %s" -- evaluacion/runner_compiscript_v1.json
```

La fecha del commit acredita el registro y no necesariamente la hora de ejecución. No inventar una fecha basándose en el ZIP. exported_at del reporte de la interfaz fecha la exportación de otro experimento.

## Python

Se mantiene 3.11 como requisito declarado de instalación y se recomienda 3.12, que sí fue comprobado. El código pasa análisis sintáctico de 3.9, pero eso no sustituye instalar dependencias y ejecutar las 77 pruebas actuales allí. Las corridas registradas con 3.9.6 son evidencia de ese recorrido histórico, no de toda la versión actual. El contenedor del ejecutor usa Python 3.12 y es independiente del Python del host.

## Conservación y reproducción

Conservar los 16 originales, incluida la evidencia de fallos de formato, identificando los incompletos. Las auditorías se guardan fuera de corridas/.

```bash
python scripts/auditar_corridas.py --out evaluacion/auditoria_corridas_nueva.json
```

Un cambio de referencia requiere recalcular las métricas afectadas, sin repetir la API. Un cambio de prompt define otra configuración; no borra ni invalida las respuestas históricas. La validación de citas mide coincidencia textual y no garantiza pertinencia ni corrección semántica.

## Para cerrar el informe

1. Sustituir cifras antiguas por recálculos documentados, sin modificar originales.
2. Aportar los JSON de la segunda iteración o retirar sus afirmaciones.
3. Añadir capturas reales y la procedencia de la fecha de Docker.
4. Incorporar referencia de precios, uso de Python y validación asistida.
5. Completar o confirmar video de 1 a 3 minutos, material visual y ensayo.

## Detalle de exactitud por archivo

| Archivo | Original | Referencias actuales | Macro-F1 actual | Sin resultado |
| --- | --- | --- | --- | --- |
| 20261027T153251Z_baseline-v1_dev.json | 10/15 | 10/15 | 0.710 | 0 |
| 20261027T153326Z_review-v1_dev.json | 12/15 | 12/15 | 0.831 | 0 |
| 20261027T153349Z_review-v2_dev.json | 2/3 | 2/3 | 0.667 | 12 |
| 20261027T153445Z_review-v2_dev_r2.json | 3/3 | 3/3 | 1.000 | 12 |
| 20261027T153536Z_review-v2_dev_r3-formato.json | 12/15 | 12/15 | 0.825 | 0 |
| 20261027T153915Z_baseline-v1_dev_rep-r2.json | 10/15 | 8/15 | 0.583 | 0 |
| 20261027T153948Z_review-v1_dev_rep-r2.json | 9/15 | 9/15 | 0.660 | 0 |
| 20261027T154012Z_review-v2_dev_rep-r2.json | 12/15 | 12/15 | 0.826 | 0 |
| 20261027T154033Z_baseline-v1_dev_rep-r3.json | 10/15 | 8/15 | 0.566 | 0 |
| 20261027T154102Z_review-v1_dev_rep-r3.json | 10/15 | 10/15 | 0.665 | 0 |
| 20261027T154124Z_review-v2_dev_rep-r3.json | 11/15 | 11/15 | 0.771 | 0 |
| 20261030T235911Z_baseline-v1_dev_camila-r1.json | 11/15 | 11/15 | 0.705 | 0 |
| 20261030T235946Z_review-v2_dev_camila-r1.json | 13/15 | 13/15 | 0.860 | 0 |
| 20261031T000105Z_baseline-v1_dev_camila-r2.json | 11/15 | 11/15 | 0.709 | 0 |
| 20261031T000142Z_review-v2_dev_camila-r2.json | 12/15 | 12/15 | 0.802 | 0 |
| 20261031T012444Z_review-v2_test_camila-final.json | 3/5 | 3/5 | 0.542 | 0 |
