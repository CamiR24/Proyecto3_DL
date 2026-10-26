"""Compara experimentos sin confundir cambios de respuesta con mejora de calidad."""
import json
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit('Uso: python scripts/compare_reports.py baseline.json mejorado.json')
a, b = [json.loads(Path(p).read_text()) for p in sys.argv[1:]]
if a['submission_sha256'] != b['submission_sha256'] or a['assignment_sha256'] != b['assignment_sha256'] or a['criteria'] != b['criteria']:
    raise SystemExit('Los informes no usan la misma entrega, instrucciones y criterios.')
if a.get('execution') != b.get('execution'):
    print('ADVERTENCIA: cambió la evidencia de ejecución; no se está aislando solo el efecto del prompt.')
if a['metrics']['model'] != b['metrics']['model']:
    print('ADVERTENCIA: también cambió el modelo.')
print('No se calcula exactitud: faltan referencias humanas validadas.')
for report in [a, b]:
    print(report['prompt_version'], json.dumps(report['metrics'], ensure_ascii=False))
before = {r['id']: r for r in a['results']}
for row in b['results']:
    old = before.get(row['id'])
    if old and old['state'] != row['state']:
        print(row['id'], old['state'], '->', row['state'], row['text'])
