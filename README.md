# Antes de entregar

Primera versión del revisor de entregas de Camila y Marinés para el Proyecto 3 de Deep Learning. Compara instrucciones, rúbrica y archivos; muestra observaciones con citas verificadas; permite solicitar cinco pruebas fijas de un compilador Compiscript en Docker.

## Estado de esta entrega

- Interfaz local con inicio explicativo, entrega y rúbrica antes de instrucciones, texto ampliado y revisión de criterios, evidencia y pendientes.
- `review-v2.txt` es la selección inicial de la interfaz; v1 y baseline siguen disponibles. Se eligió v2 a partir de desarrollo, no ajustando a los errores de test.
- 40 casos registrados y validados por la otra integrante (30 dev / 10 test). La validación fue asistida y no ciega.
- 77 pruebas automatizadas aprobadas en la auditoría del ZIP con Python 3.12.14. Las corridas de Camila registran Python 3.12.5.
- Conexión real al modelo, cinco pruebas Docker aprobadas y solicitud real de herramienta desde la interfaz documentadas en `evaluacion/`.
- Dos usuarios dieron retroalimentación, se implementaron tres cambios y ambos valoraron positivamente la nueva versión. No se midieron tiempos ni éxito por tarea.
- Las corridas originales son evidencia histórica: algunas puntuaciones de Marinés requieren el recálculo contra referencias actuales, sin editar los originales. Ver `evaluacion/AUDITORIA_ENTREGA.md`.
- Prototipo local supervisado; no es un servicio público ni un entorno certificado para código adversarial.

## 1. Iniciar la aplicación (macOS o Linux, Python 3.12 recomendado)

La versión recomendada y comprobada en esta auditoría es Python 3.12. Se conserva 3.11 como requisito de instalación declarado; su límite mínimo no se certificó con una matriz de pruebas. Hay corridas históricas de API bajo 3.9.6, pero no demuestran que la versión actual completa y sus dependencias se hayan probado allí. No rebajar el requisito a 3.9 sin ejecutar la suite y la instalación en ese entorno.

Desde la carpeta que contiene este README:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python app.py
```

Abre **http://127.0.0.1:8000**. Para detenerla, Ctrl+C. Puedes cargar archivos y confirmar criterios sin configurar el LLM. El botón «Probar con el ejemplo de Compiscript» carga una copia reducida de los archivos aportados para este proyecto.

## 2. Configurar el LLM

Edita `.env` y completa `LLM_API_KEY` y `LLM_MODEL` con una llave y un ID de modelo disponible en su cuenta. No pegues la llave en el navegador, un commit o una captura. Reinicia `app.py` después de cambiar la configuración.

La integración usa `POST /chat/completions` del `LLM_BASE_URL` configurado; por defecto, `https://api.openai.com/v1`. Solicita JSON mediante el prompt y valida el formato después; actualmente no envía `response_format`. Requiere compatibilidad con `max_completion_tokens` y, para solicitar pruebas, function calling. La compatibilidad con otros proveedores debe comprobarse; no se garantiza solo porque anuncien compatibilidad parcial con OpenAI. No se eligió ni se cobró un modelo automáticamente.

Antes de llamar al modelo, marca en la interfaz la autorización para enviar el texto seleccionado. La extracción de criterios también consume tokens. Si no deseas usarla, escribe un criterio por línea. Una línea que comienza con `[R]` es una restricción obligatoria.

Opcionalmente configura precios reales en `LLM_INPUT_USD_PER_MILLION` y `LLM_OUTPUT_USD_PER_MILLION`. Sin ellos el costo aparece como no configurado. La estimación no incorpora descuentos de caché ni otros conceptos de facturación.

## 3. Preparar la ejecución aislada

Instala e inicia Docker Desktop o un motor Docker local compatible. Construye esta imagen de confianza **una vez**, con conexión a internet para descargar Python y ANTLR:

```bash
docker build -t revisor-compiscript:v1 sandbox
```

Configura `ENABLE_RUNNER=1` en `.env` y reinicia la aplicación. La imagen se solicita con `--pull=never`: no se descarga automáticamente mientras evalúas una entrega.

Carga el ejemplo y usa «Ejecutar 5 pruebas», disponible después de preparar los archivos, incluso sin LLM. Para que la IA solicite esas pruebas, marca la autorización correspondiente al revisar y usa el prompt mejorado. El baseline no tiene herramientas. Si ya hay un resultado de pruebas en la sesión, el LLM puede consultarlo; el botón manual permite repetirlas.

### Perfil compiscript-v1

Solo admite proyectos con `src/compiler.py`, `src/generated/CompiscriptLexer.py` y `src/generated/CompiscriptParser.py`, cuyo módulo `compiler` exponga `analyze(InputStream)`. El retorno debe contener `errors` y `tac`, como el proyecto de ejemplo. Las dependencias admitidas son la biblioteca estándar y `antlr4-python3-runtime==4.13.2`. Otros proyectos Python requieren un nuevo adaptador revisado por ustedes; no se adivinan comandos ni se instala `requirements.txt` del alumno automáticamente.

| Caso | Comprobación limitada |
| --- | --- |
| `valid_tac` | Entrada válida termina sin errores y produce una lista no vacía de TAC |
| `lexical_blocks_tac` | Entrada con error léxico reporta ese tipo de error y devuelve `tac=None` |
| `syntax_blocks_tac` | Entrada con error sintáctico reporta ese tipo de error y devuelve `tac=None` |
| `semantic_blocks_tac` | Entrada con error semántico reporta ese tipo de error y devuelve `tac=None` |
| `multiple_errors` | Entrada con dos errores independientes reporta al menos dos y no produce TAC |

Se ejecuta el compilador para analizar entradas y producir representación intermedia. **No se interpreta ni ejecuta el programa Compiscript y no se genera código objeto.** Los cinco casos no verifican toda la rúbrica ni garantizan corrección general del TAC.

### Límites de ejecución

Contenedor sin red, sin credenciales ni socket Docker montados, usuario sin privilegios, capacidades eliminadas, `no-new-privileges`, sistema raíz de solo lectura, fuente de solo lectura, /tmp de 32 MiB, 256 MiB de memoria, 1 CPU, 32 procesos, 35 segundos totales, 4 segundos por caso y salida acotada. Conserva el perfil seccomp predeterminado de Docker. El código subido solo se importa dentro del contenedor. Si Docker falla, no hay ejecución alternativa en el host. Se intenta eliminar el contenedor al terminar o exceder límites.

El aislamiento por contenedores no es una garantía absoluta. La prueba importa código del alumno: un proyecto deliberadamente malicioso puede intentar manipular sus retornos, el proceso de pruebas o la salida. No se presenta como prueba resistente al fraude. Para un servicio público se necesitarían aislamiento más fuerte, revisión de amenazas, cuotas, autenticación, almacenamiento seguro y supervisión de procesos externos. No expongas este servidor a internet.

## 4. Flujo de uso

1. Consulta Inicio y pulsa Comenzar. Carga entrega y rúbrica, agrega instrucciones si corresponde, o usa el ejemplo preparado.
2. Comprueba los archivos seleccionados y advertencias de cobertura. Los PDF escaneados requieren OCR fuera de esta versión.
3. Escribe criterios o autoriza una propuesta del LLM; corrige el resultado antes de revisar.
4. Opcionalmente ejecuta las pruebas desde el botón; también puedes permitir que el LLM las solicite.
5. Pide revisión con evidencia. Abre las citas y distingue código, documentación, prueba escrita y ejecución.
6. Descarga el JSON. Si ejecutaste pruebas después de revisar, vuelve a solicitar la revisión para incorporarlas; el informe anterior no se modifica silenciosamente.
7. Usa «Eliminar mi revisión» o cierra el servidor. El borrado local no revoca lo enviado al proveedor ni elimina descargas.

## 5. Arquitectura y archivos

```text
web/                  Interfaz HTML/CSS/JS; sin CDN ni dependencias de frontend
app.py                Servidor local, sesiones en memoria y rutas JSON
revisor/documents.py  Lectura y selección limitada de documentos; manifiesto de cobertura
revisor/llm.py        API, prompts, llamada a herramienta y validación de citas
revisor/runner.py     Único punto de ejecución: contenedor y perfil autorizados
sandbox/              Imagen y cinco pruebas controladas
prompts/              Baseline, revisión mejorada y extracción de criterios versionados
examples/             Caso Compiscript aportado, criterios y referencias iniciales
tests/                Pruebas de archivos, evidencia y control de herramientas
scripts/              Comparación de informes y prueba local del ejecutor
```

Entrada → extracción/selección de texto → confirmación humana de criterios → LLM → herramienta Docker opcional → LLM interpreta resultados → validación de citas/estados → interfaz y JSON.

No usa RAG, embeddings ni fine-tuning en esta versión. Se prioriza selección de archivos y prompting. El contexto de entrega se limita a 140 000 caracteres y las instrucciones a 40 000; no son conteos exactos de tokens ni garantizan caber en todos los modelos. Se registra el consumo real reportado por el proveedor y se debe elegir un modelo con ventana suficiente. Reducir contexto si la API rechaza la solicitud.

## 6. Reproducir verificaciones y comparación

Pruebas locales, sin API ni Docker:

```bash
python -m unittest discover -s tests -v
```

Cuando Docker esté preparado, el siguiente comando ejecuta el perfil sobre el ejemplo sin LLM:

```bash
python scripts/check_runner.py
```

Para comparar prompting, conserva exactamente los mismos archivos, criterios y estado de ejecución. Descarga una revisión con baseline y otra con el prompt mejorado **sin herramientas**; así el cambio de prompt queda separado del acceso a pruebas. Luego compara una revisión mejorada sin pruebas con otra usando las pruebas, como experimento adicional. La aplicación conserva el resultado de pruebas en la sesión: para una comparación sin ejecución utiliza una sesión nueva y no ejecutes antes el perfil.

```bash
python scripts/compare_reports.py baseline.json mejorado.json
```

El script resume cambios, tiempos, tokens y costo; **no mide exactitud sin referencias humanas**. `examples/casos_semilla.jsonl` contiene ocho observaciones iniciales sobre el ejemplo, no un conjunto final validado ni ocho entregas independientes. Se ampliaron a los 40 casos de `evaluacion/casos_camila.jsonl` y `evaluacion/casos_marines.jsonl`, con validación cruzada registrada. Separar desarrollo y prueba; no inflar el tamaño contando como independientes variantes casi idénticas del mismo proyecto. Posibles métricas: acuerdo por estado con referencias humanas, precisión de hallazgos y pertinencia de evidencia. Para UX, observar si compañeros completan la revisión y entienden los pendientes.

El JSON exportado incluye versiones y hash del prompt, hashes de entrega/instrucciones, criterios, evidencia seleccionada, resultados de ejecución y métricas. No se guardan automáticamente archivos ni revisiones en disco; exporta lo necesario para conservar experimentos y revísalo antes de compartir.

## 7. Reproducir la auditoría y cerrar la entrega

```bash
python scripts/validar_casos.py
python -m unittest discover -s tests -v
python scripts/auditar_corridas.py --out evaluacion/auditoria_corridas_nueva.json
```

El archivo de salida de auditoría debe ser nuevo y quedar fuera de `evaluacion/corridas/`. No llama a la API ni ejecuta Docker; puntúa respuestas históricas con las referencias actuales y conserva los originales.

Pendientes documentales: incorporar capturas reales, confirmar la fecha no registrada en el JSON de Docker, aportar los archivos de la segunda iteración si se reporta, y completar video y ensayo. Una validación ciega adicional es opcional y no se ha realizado.

## Precios y evidencia de ejecución

Consulta oficial: 30 de octubre de 2026. Claude Haiku 5.5: para prompts de hasta 100,000 tokens de entrada, 0.10 USD/millón de entrada y 0.50 USD/millón de salida; para prompts mayores, 0.50 y 2.50 USD/millón. El umbral se aplica por solicitud, no al total agregado de una revisión de dos llamadas. Caché y otras modalidades tienen tarifas específicas. El estimador actual usa precios configurados planos: verificar el tramo antes de utilizarlo con solicitudes largas.

Fuente: https://platform.claude.com/docs/en/models/haiku-5-5/overview#pricing

Docker directo: `evaluacion/runner_compiscript_v1.json`, cinco aprobadas, 0.969 s. Comando utilizado: `ENABLE_RUNNER=1 python scripts/check_runner.py > evaluacion/runner_compiscript_v1.json`. El JSON original no registra fecha; no deducirla de la hora de modificación del ZIP.

Herramienta solicitada por el modelo: `evaluacion/revision_v2_herramienta.json`, cinco aprobadas, origen `model_tool`, sin reutilización. `exported_at` registra la fecha de exportación, no necesariamente la hora exacta del ejecutor.

## Referencias técnicas consultadas

- https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
- https://developers.openai.com/api/docs/guides/function-calling?api-mode=chat
- https://docs.docker.com/reference/cli/docker/container/run/
- https://docs.docker.com/engine/containers/resource_constraints/

Los materiales de `examples/` provienen de los archivos que Camila adjuntó para esta conversación. La rúbrica aportada se llama Proyecto 02, pero su encabezado interno dice Proyecto 01; confirmar esa inconsistencia antes de usarla como referencia definitiva. Las fechas de esa actividad de Compiladores no son las fechas de entrega del Proyecto 3 de Deep Learning.
