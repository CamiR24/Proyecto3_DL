"""Ejecuta el revisor sobre los casos de evaluación y guarda configuración, respuestas y métricas."""
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from . import llm
from .casos import ROOT, assignment_text, check_case, load_cases, load_manifest, load_submission
from .metricas import aggregate, operational, score_case

# Precio de lista en USD por millón de tokens (entrada, salida) para prompts de hasta 100 000 tokens.
# Fuente: tabla de modelos de la referencia de la API de Claude (caché del 6 de octubre de 2026). Verificar antes
# de citar cifras de costo en el informe; LLM_INPUT_USD_PER_MILLION / LLM_OUTPUT_USD_PER_MILLION lo reemplazan.
LIST_PRICES = {'claude-haiku-5-5': (0.10, 0.50)}
# Supuestos del estimador, no mediciones: caracteres por token (texto en español y código) y tokens de salida por criterio.
CHARS_PER_TOKEN = (4.0, 2.8)
OUTPUT_PER_CRITERION = (120, 350)
OUTPUT_OVERHEAD = 80


def load_all_cases(paths, split, only=None):
    """Carga y valida los casos; un caso incoherente detiene la evaluación en vez de medir con una referencia rota."""
    manifest, cache, cases = load_manifest(), {}, []
    for path in paths:
        cases += load_cases(path)
    ids = [c['id'] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('Hay ids de caso repetidos entre los archivos.')
    problems = [f"{c['id']}: {p}" for c in cases for p in check_case(c, manifest, cache)]
    if problems:
        raise ValueError('Casos inválidos:\n' + '\n'.join(problems))
    selected = [c for c in cases if c['split'] == split and (not only or c['id'] in only)]
    if only and {c['id'] for c in selected} != set(only):
        raise ValueError(f'Ids no encontrados en la partición {split}: {sorted(set(only) - {c["id"] for c in selected})}')
    if not selected:
        raise ValueError(f'No hay casos en la partición {split}.')
    return sorted(selected, key=lambda c: c['id']), manifest, cache


def group_by_submission(cases):
    groups = {}
    for case in cases:
        groups.setdefault(case['submission'], []).append(case)
    return groups


def criteria_text(cases):
    """Un criterio por línea; [R] marca restricciones. El orden fija los ids C01, C02, …"""
    return '\n'.join(('[R] ' if c['criterion']['kind'] == 'restriccion' else '') + c['criterion']['text'] for c in cases)


def build_session(key, manifest, cache):
    if key not in cache:
        cache[key] = load_submission(key, manifest)
    submission = cache[key]
    return {'assignment': assignment_text(manifest), 'submission_sha256': submission['sha256'],
            'submission': {k: submission[k] for k in ('documents', 'warnings', 'runner_compatible', 'runner_files')}}


def prices(model):
    """(entrada, salida, origen) en USD por millón de tokens."""
    try:
        return (float(os.environ['LLM_INPUT_USD_PER_MILLION']), float(os.environ['LLM_OUTPUT_USD_PER_MILLION']),
                'variables de entorno')
    except (KeyError, ValueError):
        if model in LIST_PRICES:
            return (*LIST_PRICES[model], 'precio de lista de la referencia de la API (6 oct 2026)')
        return None, None, 'sin precio'


def estimate(groups, manifest, cache, prompt_file, model):
    """Costo estimado sin llamar a la API: tokens de entrada por caracteres y salida por criterio."""
    price_in, price_out, source = prices(model)
    rows = []
    for key, cases in groups.items():
        session = build_session(key, manifest, cache)
        criteria = llm.manual_criteria(criteria_text(cases))
        _, messages = llm.review_messages(session, criteria, prompt_file)
        chars = sum(len(m['content']) for m in messages)
        tokens_in = (round(chars / CHARS_PER_TOKEN[0]), round(chars / CHARS_PER_TOKEN[1]))
        tokens_out = tuple(min(llm.MAX_COMPLETION_TOKENS, OUTPUT_OVERHEAD + len(cases) * n) for n in OUTPUT_PER_CRITERION)
        cost = None if price_in is None else tuple(round((i * price_in + o * price_out) / 1_000_000, 5)
                                                  for i, o in zip(tokens_in, tokens_out))
        rows.append({'submission': key, 'criteria': len(cases), 'chars': chars, 'tokens_in': tokens_in,
                     'tokens_out': tokens_out, 'cost_usd': cost})
    total = None if price_in is None else [round(sum(r['cost_usd'][i] for r in rows), 5) for i in (0, 1)]
    return {'model': model, 'prompt': prompt_file, 'calls': len(rows), 'rows': rows, 'cost_usd_total': total,
            'price_usd_per_million': [price_in, price_out], 'price_source': source,
            'over_100k_tokens': [r['submission'] for r in rows if r['tokens_in'][1] > 100_000]}


def git_info():
    try:
        run = lambda *args: subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        return {'commit': run('rev-parse', '--short', 'HEAD'), 'uncommitted_changes': bool(run('status', '--porcelain'))}
    except (OSError, subprocess.SubprocessError):
        return None


def run_evaluation(cases, manifest, cache, prompt_file, split, label=''):
    """Una llamada al revisor por entrega, con todos los criterios de esa entrega; compara con las referencias."""
    model = os.getenv('LLM_MODEL')
    price_in, price_out, price_source = prices(model)
    if price_in is not None:
        os.environ.setdefault('LLM_INPUT_USD_PER_MILLION', str(price_in))
        os.environ.setdefault('LLM_OUTPUT_USD_PER_MILLION', str(price_out))
    prompt = (ROOT / 'prompts' / prompt_file).read_text()
    config = {'model': model, 'endpoint_host': urlsplit(os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')).netloc,
              'prompt_file': prompt_file, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
              'split': split, 'label': label, 'case_ids': [c['id'] for c in cases],
              'started_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'generation': {'max_completion_tokens': llm.MAX_COMPLETION_TOKENS,
                             'thinking': 'disabled' if model == 'claude-haiku-5-5' else 'por defecto del proveedor',
                             'sampling': 'valores por defecto del proveedor: temperature y top_p no se configuran, '
                                         'por lo que las corridas no son deterministas'},
              'tools': 'sin herramientas', 'price_usd_per_million': [price_in, price_out], 'price_source': price_source,
              'git': git_info(), 'python': platform.python_version()}
    groups, scores = [], []
    for key, group in group_by_submission(cases).items():
        criteria = llm.manual_criteria(criteria_text(group))
        entry = {'submission': key, 'case_ids': [c['id'] for c in group], 'criteria': criteria}
        try:
            report = llm.review(build_session(key, manifest, cache), criteria, allow_execution=False, prompt_file=prompt_file)
        except ValueError as exc:
            entry['error'] = str(exc)
        else:
            entry.update(results=report['results'], metrics=report['metrics'], validation=report['validation'],
                         coverage=report['coverage'], submission_sha256=report['submission_sha256'])
            scores += [score_case(case, result) for case, result in zip(group, report['results'])]
        groups.append(entry)
    return {'config': config, 'groups': groups, 'scores': scores, 'quality': aggregate(scores) if scores else None,
            'operational': operational(groups),
            'cases_without_result': sum(len(g['case_ids']) for g in groups if 'error' in g)}


def save_run(run, directory=None):
    directory = Path(directory or ROOT / 'evaluacion/corridas')
    directory.mkdir(parents=True, exist_ok=True)
    c = run['config']
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name = f"{stamp}_{Path(c['prompt_file']).stem}_{c['split']}{('_' + c['label']) if c['label'] else ''}.json"
    path = directory / name
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + '\n')
    return path


def format_estimate(est):
    lines = [f"Estimación sin llamar a la API · modelo {est['model']} · prompt {est['prompt']} · {est['calls']} llamada(s)"]
    for r in est['rows']:
        cost = '—' if r['cost_usd'] is None else f"${r['cost_usd'][0]:.4f}–${r['cost_usd'][1]:.4f}"
        lines.append(f"  {r['submission']:<22} {r['criteria']:>2} criterios · entrada ≈{r['tokens_in'][0]:,}–{r['tokens_in'][1]:,} tok · "
                     f"salida ≈{r['tokens_out'][0]:,}–{r['tokens_out'][1]:,} tok · {cost}")
    if est['cost_usd_total']:
        lines.append(f"  TOTAL de esta corrida: ${est['cost_usd_total'][0]:.4f}–${est['cost_usd_total'][1]:.4f} "
                     f"(precio {est['price_usd_per_million'][0]}/{est['price_usd_per_million'][1]} USD por millón; {est['price_source']})")
    else:
        lines.append('  Sin precio configurado: define LLM_INPUT_USD_PER_MILLION y LLM_OUTPUT_USD_PER_MILLION.')
    if est['over_100k_tokens']:
        lines.append(f"  AVISO: {est['over_100k_tokens']} podría pasar de 100 000 tokens y el precio por token sube.")
    lines.append('  Supuestos: entrada = caracteres / (4.0 a 2.8); salida = 120 a 350 tokens por criterio. Es una estimación, no una medición.')
    return '\n'.join(lines)


def format_summary(run):
    q, o, c = run['quality'], run['operational'], run['config']
    lines = [f"Corrida {c['prompt_file']} · partición {c['split']} · {c['model']} · {c['started_at']}"]
    if run['cases_without_result']:
        lines.append(f"AVISO: {run['cases_without_result']} caso(s) sin resultado por error de la llamada; las métricas no los incluyen.")
        for g in run['groups']:
            if 'error' in g:
                lines.append(f"  {g['submission']}: {g['error']}")
    if q:
        ex, ac, ev = q['exact'], q['acceptable'], q['evidence_line_hit']
        lines += [f"  Exactitud de estado: {ex['k']}/{ex['n']} IC95% {ex['ci95']} · aceptable: {ac['k']}/{ac['n']} IC95% {ac['ci95']} · macro-F1 {q['macro_f1']}",
                  f"  Fallas graves: {q['severe_errors'] or 'ninguna'}",
                  f"  Evidencia: mismo archivo {q['evidence_file_hit']['k']}/{q['evidence_file_hit']['n']} · líneas solapadas {ev['k']}/{ev['n']}"]
    lines.append(f"  Operativo: {o['calls']} llamada(s) · latencia media {o['latency_seconds_mean']} s · {o['total_tokens']:,} tokens "
                 f"({o['tokens_per_criterion']} por criterio) · costo {o['cost_usd'] if o['cost_usd'] is not None else 'sin precio'} USD · "
                 f"validez de citas {o['citation_validity']}")
    lines.append('  Con 15 casos o menos, los intervalos son anchos: una diferencia de 1 o 2 casos no es evidencia de mejora.')
    return '\n'.join(lines)
