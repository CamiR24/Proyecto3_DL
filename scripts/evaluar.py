"""Corre el revisor sobre los casos de evaluación y guarda configuración, respuestas y métricas.

Sin --yes solo estima el costo y no llama a la API. La partición reservada (test) exige --final.
Ejemplos:
  python scripts/evaluar.py --prompt v2 --split dev            # estimación
  python scripts/evaluar.py --prompt v2 --split dev --yes      # llamada real
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import load_env  # noqa: E402
from revisor import llm  # noqa: E402
from revisor.evaluacion import (estimate, format_estimate, format_summary, group_by_submission,  # noqa: E402
                                load_all_cases, run_evaluation, save_run)

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('--prompt', choices=sorted(llm.PROMPTS), required=True, help='baseline, improved (review-v1) o v2')
parser.add_argument('--split', choices=['dev', 'test'], required=True)
parser.add_argument('--cases', nargs='*', type=Path, help='archivos casos_*.jsonl (por defecto, todos los de evaluacion/)')
parser.add_argument('--only', help='ids separados por coma, para pruebas parciales')
parser.add_argument('--label', default='', help='texto corto para el nombre del archivo, por ejemplo r2')
parser.add_argument('--out', type=Path, help='carpeta de salida (por defecto evaluacion/corridas)')
parser.add_argument('--yes', action='store_true', help='confirma la llamada real a la API (gasta dinero)')
parser.add_argument('--final', action='store_true', help='confirma que la configuración está cerrada para usar la partición test')
args = parser.parse_args()

load_env()
if args.split == 'test' and not args.final:
    raise SystemExit('La partición test está reservada: no se usa para elegir prompts. '
                     'Agrega --final solo cuando la configuración esté cerrada.')
paths = args.cases or sorted((ROOT / 'evaluacion').glob('casos_*.jsonl'))
try:
    cases, manifest, cache = load_all_cases(paths, args.split, set(args.only.split(',')) if args.only else None)
except ValueError as exc:
    raise SystemExit(str(exc))
prompt_file = llm.PROMPTS[args.prompt]
print(format_estimate(estimate(group_by_submission(cases), manifest, cache, prompt_file,
                               os.getenv('LLM_MODEL', 'claude-haiku-5-5'))))
if not args.yes:
    raise SystemExit('\nNo se llamó a la API. Agrega --yes para ejecutar la corrida.')
if not llm.model_configured():
    raise SystemExit('Falta LLM_API_KEY o LLM_MODEL en .env.')
run = run_evaluation(cases, manifest, cache, prompt_file, args.split, args.label)
path = save_run(run, args.out)
shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
print('\n' + format_summary(run) + f'\n  Guardado en {shown}')
