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
