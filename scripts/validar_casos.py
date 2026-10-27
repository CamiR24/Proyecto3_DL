"""Comprueba que los casos de evaluación sean coherentes y que sus citas existan en la entrega."""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from revisor.casos import check_case, load_cases, load_manifest  # noqa: E402

paths = [Path(p) for p in sys.argv[1:]] or sorted((ROOT / 'evaluacion').glob('casos_*.jsonl'))
if not paths:
    raise SystemExit('No hay archivos casos_*.jsonl en evaluacion/.')
manifest, cache, cases, failed = load_manifest(), {}, [], False
for path in paths:
    cases += [(path.name, c) for c in load_cases(path)]
seen = Counter(c.get('id') for _, c in cases)
for source, case in cases:
    problems = check_case(case, manifest, cache)
    if seen[case.get('id')] > 1:
        problems.append('id repetido')
    for problem in problems:
        failed = True
        print(f"ERROR {source} {case.get('id', '?')}: {problem}")

rows = [c for _, c in cases]
print(f'{len(rows)} casos en {len(paths)} archivo(s).')
for field in ('split', 'category', 'reference_state', 'submission', 'author'):
    print(f'  {field}:', dict(sorted(Counter(c.get(field) for c in rows).items())))
pending = sum(1 for c in rows if not c.get('human_validated'))
print(f'  sin validar por la otra persona: {pending}/{len(rows)}')
if pending:
    print('AVISO: las referencias no son definitivas hasta que las valide la otra integrante (human_validated).')
sys.exit(1 if failed else 0)
