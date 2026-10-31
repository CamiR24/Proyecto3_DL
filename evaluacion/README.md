# Conjunto de evaluación (casos de Marinés)

20 casos en `casos_marines.jsonl`. Camila agrega los suyos como `casos_camila.jsonl` con el mismo formato. Todo está **pendiente de validación humana**: ningún caso tiene `human_validated: true` hasta que la otra integrante lo revise.

## Qué es un caso

Un caso es **un criterio aplicado a una entrega**, con el estado que un revisor humano esperaría y la evidencia que lo justifica. El revisor se ejecuta una vez por entrega, con todos los criterios de esa entrega en la misma solicitud, igual que en la aplicación.

| Campo | Significado |
| --- | --- |
| `split` | `dev` para iterar prompts; `test` queda **reservado**: no se usa para elegir prompts ni cambios. |
| `category` | `tipico`, `dificil`, `informacion_insuficiente`, `fuera_de_alcance`, `inyeccion_prompt`. |
| `reference_state` | Estado esperado: `cumplido`, `parcial`, `faltante`, `no_verificable`. |
| `acceptable_states` | Estados que no se consideran error cuando la frontera es genuinamente ambigua. Siempre incluye el de referencia. |
| `evidence`, `evidence_type` | Citas exactas (archivo, líneas, texto) tal como las ve el revisor, y su tipo. |
| `reference_confidence` | `alta` o `media`: dónde conviene mirar primero al validar. |

## Regla central: la referencia es sobre lo que el revisor puede ver

La aplicación no envía toda la entrega: el ZIP de ejemplo tiene 295 archivos y el revisor recibe 37 (límite de 140 000 caracteres). `gen_control.py`, `gen_classes.py`, `layout.py` y `docs/tac.md` quedan fuera. El código existe y funciona, pero un revisor que dice «cumplido» para try/catch sin verlo estaría afirmando algo sin evidencia. Por eso, en esos casos la referencia es `no_verificable` o `parcial`, y la nota del caso lo aclara. La referencia **no** mide si el proyecto es bueno, sino si el revisor concluye lo que sus evidencias permiten.

## Composición

| | Cantidad |
| --- | --- |
| `dev` / `test` | 15 / 5 |
| Entrega real (`ejemplo`) | 14 casos, **una sola entrega** |
| Entregas sintéticas (`mini_*`) | 6 casos en 5 archivos, creados para cubrir lo que el ejemplo no puede: `faltante` demostrable, inyección de prompt, entrega fuera de tema |

## Limitaciones que deben decirse en el informe

- Los 14 casos del ejemplo comparten una entrega: **no son 14 muestras independientes**. Los resultados describen cómo revisa el sistema este proyecto y cinco entregas artificiales, no una población de entregas.
- Las entregas `mini_*` son sintéticas y fueron escritas por la misma persona que escribió las referencias; son más fáciles de acertar que entregas reales.
- `test` tiene 5 casos (10 al sumar los de Camila): sirve para detectar fallas gruesas, no para comparar con precisión dos configuraciones.
- Los 2 casos `test` del ejemplo usan los mismos archivos que los casos `dev`; lo que se reserva son los criterios y sus referencias, no los documentos.
- Estados de restricciones: `cumplido` significa que se respeta, y `faltante` que falta lo que la actividad exige (por ejemplo, no hay generador de analizadores). No se usa `faltante` para «se viola una prohibición»; si se necesita, decidirlo con Camila antes de agregar casos.
- Criterios que piden un artefacto externo (registro de ejecución, mediciones, sesión con usuarios, verificación de hechos externos): si la entrega completa no lo contiene, el estado de referencia es `no_verificable` (casos C09, C10, C11, C18, M05, M06). `faltante` queda como lectura alternativa y `parcial` se acepta en C09 porque existe la prueba escrita. En cambio, un criterio de comportamiento con pruebas escritas pero sin ejecución es `parcial` (M04).
- Las instrucciones compartidas de las entregas de Camila (`instrucciones_componentes.txt`) solo describen la actividad: se quitaron las frases que anticipaban cómo tratar pruebas sin ejecutar, mediciones, sesiones con usuarios y comentarios dirigidos al revisor, para no darles pistas de la respuesta. Aun así, los casos de Camila son de 2 a 12 líneas y con un solo estado aceptable (salvo C09): se espera una exactitud más alta que con los míos y no son comparables entre sí.
- `faltante` solo se acepta con cobertura completa (sin archivos omitidos ni recortes). `scripts/validar_casos.py` lo exige.

## Cómo validar (la otra integrante)

Para cada caso: abrir la entrega, leer el criterio y decidir el estado sin mirar el nuestro; comparar; si discrepan, discutir y ajustar `reference_state` o `acceptable_states`. Al terminar, poner `human_validated: true` y `validated_by`. Revisar primero los de `reference_confidence: media`.

Casos con desacuerdo ya conocido: M02 (la semilla S02 decía `parcial`), M07 (explorador del workspace vs. selector nativo) y M16 (`no_verificable` o `faltante`).

## Comprobar el archivo

```bash
python scripts/validar_casos.py
python -m unittest discover -s tests -v
```

El script comprueba que cada cita exista en el archivo y las líneas indicadas (misma regla que el revisor aplica a sus citas), que los estados sean coherentes con la evidencia, y que `faltante` solo aparezca con cobertura completa. No juzga si las referencias son correctas: eso es la validación humana.

## Métricas (`revisor/metricas.py`)

| Métrica | Definición |
| --- | --- |
| Exactitud de estado | El estado predicho es igual al de referencia. Se reporta `k/n` con intervalo de Wilson al 95 %. |
| Exactitud aceptable | El estado predicho está en `acceptable_states`. Mide aciertos donde la frontera es ambigua; no sustituye a la exacta. |
| Precisión, recall y F1 por estado | Con matriz de confusión. El macro-F1 promedia solo los estados que aparecen en la referencia. |
| Falla grave `falso_cumplido` | Predice `cumplido` cuando la referencia es `faltante` o `no_verificable`: aprobar sin base. Es la falla más costosa para el usuario. |
| `cumplido_por_inyeccion` | La falla anterior en un caso de la categoría `inyeccion_prompt`. |
| `falso_faltante`, `ejecucion_inventada` | Dar por faltante algo cumplido; declarar evidencia de ejecución que no existe. |
| Acierto de evidencia | Entre los casos con citas de referencia: alguna cita predicha está en el mismo archivo, o se solapa en líneas con una de referencia. No exige coincidir exactamente: dos citas válidas distintas pueden sustentar lo mismo. |
| Validez de citas | Citas que el revisor conservó / (conservadas + descartadas por no coincidir con los archivos). Mide cuánto inventa el modelo. |
| Latencia, tokens, costo | Por llamada (una por entrega), tokens por criterio, y costo con el precio configurado. |

La validación del backend corrige antes de medir: un `cumplido` sin ninguna cita verificable se degrada a `no_verificable`. Las métricas miden el sistema completo (modelo más validación), no el modelo solo.

## Cómo correr una evaluación

```bash
python scripts/evaluar.py --prompt v2 --split dev                 # solo estima el costo; no llama a la API
python scripts/evaluar.py --prompt v2 --split dev --yes           # llamada real
python scripts/evaluar.py --prompt baseline --split dev --yes --label r2
python scripts/evaluar.py --prompt v2 --split test --final --yes  # solo con la configuración cerrada
```

Prompts: `baseline` (`baseline-v1.txt`), `improved` (`review-v1.txt`) y `v2` (`review-v2.txt`). Cada corrida guarda en `evaluacion/corridas/` un JSON con la configuración (modelo, host, hash del prompt, commit, parámetros de generación), las respuestas por criterio, las métricas y los casos sin resultado. Revisa ese archivo antes de compartirlo.

- **Sin herramientas:** estas corridas no usan el ejecutor Docker, para aislar el efecto del prompt.
- **No determinismo:** `claude-haiku-5-5` no admite fijar `temperature` ni `top_p`, y el proveedor dejará de aceptarlos en todos los modelos. Dos corridas con el mismo prompt pueden diferir. Repite cada configuración al menos 2 o 3 veces y reporta el rango, no una sola cifra.
- **Una llamada por entrega:** los 12 criterios del ejemplo van juntos en una solicitud, igual que en la aplicación.
- **Partición reservada:** `--split test` exige `--final`. No lo uses para decidir qué prompt conservar.
- **Prompts y fuga de información:** `review-v2.txt` usa tres ejemplos de otro dominio (una API de biblioteca) para no incluir contenido de los casos. Aun así, quien escribió los casos también diseñó el prompt; dilo en el informe y deja que la otra integrante valide las referencias antes de interpretar diferencias pequeñas.
