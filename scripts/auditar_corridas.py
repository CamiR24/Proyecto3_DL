"""Recalcula respuestas guardadas con las referencias actuales, sin API ni Docker."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from revisor.casos import load_cases, load_manifest, assignment_text
from revisor.metricas import aggregate, score_case


def audit():
    paths = sorted((ROOT / 'evaluacion').glob('casos_*.jsonl'))
    cases = {}
    for path in paths:
        for case in load_cases(path):
            if case['id'] in cases:
                raise ValueError('Id repetido: ' + case['id'])
            cases[case['id']] = case
    manifest = load_manifest()
    runs = []
    for path in sorted((ROOT / 'evaluacion/corridas').glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if not {'config', 'groups', 'scores'} <= data.keys():
            continue
        scores, context_changes, criterion_changes, unmapped = [], [], [], []
        for group in data['groups']:
            ids, results = group.get('case_ids', []), group.get('results', [])
            if not results:
                continue
            if len(ids) != len(results):
                unmapped.append(group.get('submission'))
                continue
            for index, (cid, result) in enumerate(zip(ids, results)):
                case = cases[cid]
                criteria = group.get('criteria', [])
                if index < len(criteria) and any(criteria[index].get(k) != case['criterion'][k] for k in ('text', 'kind')):
                    criterion_changes.append(cid)
                scores.append(score_case(case, result))
            old_hash = group.get('assignment_sha256')
            if old_hash:
                current_hash = hashlib.sha256(assignment_text(manifest, group['submission']).encode()).hexdigest()
                if current_hash != old_hash:
                    context_changes.append(group['submission'])
        old = {s['id']: s for s in data['scores']}
        changed = [s['id'] for s in scores if s != old.get(s['id'])]
        prompt = ROOT / 'prompts' / data['config']['prompt_file']
        runs.append({
            'file': path.relative_to(ROOT).as_posix(),
            'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'prompt': data['config']['prompt_file'],
            'prompt_matches_current': prompt.is_file() and hashlib.sha256(prompt.read_bytes()).hexdigest() == data['config']['prompt_sha256'],
            'split': data['config']['split'], 'model': data['config']['model'],
            'recorded_python': data['config'].get('python'),
            'cases_without_result': data.get('cases_without_result'),
            'unmapped_groups': unmapped, 'changed_criteria': criterion_changes,
            'changed_assignment_groups': context_changes,
            'scores_changed': changed, 'original_quality': data.get('quality'),
            'rescored_quality': aggregate(scores) if scores else None,
            'rescored_scores': scores})
    return {'method': 'Respuestas originales puntuadas con las referencias actuales. No repite llamadas ni demuestra que se usó el contexto actual.',
            'case_files_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'runs': runs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='Salida nueva, fuera de evaluacion/corridas/. No sobrescribe archivos.')
    args = parser.parse_args()
    result = audit()
    for run in result['runs']:
        q = run['rescored_quality']
        k = q['exact']['k'] if q else 0
        n = q['cases'] if q else 0
        print(f"{Path(run['file']).name}: {k}/{n}; cambios en puntuación: {','.join(run['scores_changed']) or 'ninguno'}")
    if args.out:
        path = args.out.resolve()
        runs_dir = (ROOT / 'evaluacion/corridas').resolve()
        if path == runs_dir or runs_dir in path.parents:
            raise SystemExit('Guarda la auditoría fuera de corridas/ para no confundirla con una corrida.')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        print(f'Auditoría guardada: {path}')


if __name__ == '__main__':
    main()
