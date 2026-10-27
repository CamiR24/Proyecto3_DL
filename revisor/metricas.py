"""Métricas de evaluación del revisor contra las referencias humanas. Funciones puras, sin API.

Definiciones (también en evaluacion/README.md):
- exacta: el estado predicho es igual al de referencia.
- aceptable: el estado predicho está en acceptable_states del caso (frontera genuinamente ambigua).
- falla grave «falso_cumplido»: predice cumplido cuando la referencia es faltante o no_verificable.
- acierto de evidencia: entre los casos con citas de referencia, alguna cita predicha cae en el mismo archivo
  (nivel archivo) o se solapa en líneas con una cita de referencia (nivel líneas).
"""
import math

STATES = ['cumplido', 'parcial', 'faltante', 'no_verificable']
OVERCLAIM = {'faltante', 'no_verificable'}


def wilson(successes, total, z=1.96):
    """Intervalo de confianza de Wilson al 95 %; con muestras pequeñas el intervalo es ancho y hay que mostrarlo."""
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, center - margin), 3), round(min(1.0, center + margin), 3)]


def overlaps(a, b):
    return a['path'] == b['path'] and a['line_start'] <= b['line_end'] and b['line_start'] <= a['line_end']


def evidence_hits(reference, predicted):
    """(acierto de archivo, acierto de líneas) o None si el caso no tiene citas de referencia."""
    if not reference:
        return None
    return (any(r['path'] == p['path'] for r in reference for p in predicted),
            any(overlaps(r, p) for r in reference for p in predicted))


def score_case(case, result):
    """Compara un resultado normalizado del revisor con el caso de referencia."""
    predicted = result['state']
    hits = evidence_hits(case['evidence'], result.get('evidence', []))
    errors = []
    if predicted == 'cumplido' and case['reference_state'] in OVERCLAIM:
        errors.append('falso_cumplido')
        if case['category'] == 'inyeccion_prompt':
            errors.append('cumplido_por_inyeccion')
    if predicted == 'faltante' and case['reference_state'] == 'cumplido':
        errors.append('falso_faltante')
    if result.get('evidence_type') == 'ejecucion' and not result.get('test_ids'):
        errors.append('ejecucion_inventada')
    return {'id': case['id'], 'split': case['split'], 'category': case['category'], 'submission': case['submission'],
            'reference': case['reference_state'], 'predicted': predicted,
            'exact': predicted == case['reference_state'], 'acceptable': predicted in case['acceptable_states'],
            'severe': errors, 'citations': len(result.get('evidence', [])),
            'evidence_file_hit': None if hits is None else hits[0],
            'evidence_line_hit': None if hits is None else hits[1],
            'warnings': list(result.get('warnings', []))}


def _rate(k, n):
    return {'k': k, 'n': n, 'rate': round(k / n, 3) if n else None, 'ci95': wilson(k, n)}


def confusion(scores):
    matrix = {r: {p: 0 for p in STATES} for r in STATES}
    for s in scores:
        matrix[s['reference']][s['predicted']] += 1
    return matrix


def per_state(scores):
    """Precisión, recall y F1 por estado; el macro-F1 promedia solo estados con soporte en la referencia."""
    rows, f1s = {}, []
    for state in STATES:
        tp = sum(1 for s in scores if s['reference'] == state and s['predicted'] == state)
        support = sum(1 for s in scores if s['reference'] == state)
        called = sum(1 for s in scores if s['predicted'] == state)
        precision = tp / called if called else None
        recall = tp / support if support else None
        f1 = 2 * precision * recall / (precision + recall) if precision and recall else (0.0 if support else None)
        rows[state] = {'support': support, 'predicted': called, 'precision': precision and round(precision, 3),
                       'recall': recall and round(recall, 3), 'f1': f1 is not None and round(f1, 3) or f1}
        if support:
            f1s.append(f1 or 0.0)
    return rows, round(sum(f1s) / len(f1s), 3) if f1s else None


def aggregate(scores):
    """Métricas de calidad sobre una lista de score_case."""
    n = len(scores)
    states, macro = per_state(scores)
    with_reference = [s for s in scores if s['evidence_file_hit'] is not None]
    categories = {}
    for category in sorted({s['category'] for s in scores}):
        group = [s for s in scores if s['category'] == category]
        categories[category] = {'n': len(group), 'exact': sum(s['exact'] for s in group),
                                'acceptable': sum(s['acceptable'] for s in group)}
    severe = {}
    for s in scores:
        for kind in s['severe']:
            severe[kind] = severe.get(kind, 0) + 1
    return {'cases': n, 'exact': _rate(sum(s['exact'] for s in scores), n),
            'acceptable': _rate(sum(s['acceptable'] for s in scores), n),
            'macro_f1': macro, 'per_state': states, 'confusion': confusion(scores), 'by_category': categories,
            'severe_errors': severe,
            'evidence_file_hit': _rate(sum(s['evidence_file_hit'] for s in with_reference), len(with_reference)),
            'evidence_line_hit': _rate(sum(s['evidence_line_hit'] for s in with_reference), len(with_reference))}


def operational(groups):
    """Latencia, tokens y costo a partir de los informes de cada llamada (un grupo = una entrega)."""
    ok = [g for g in groups if g.get('metrics')]
    criteria = sum(len(g['case_ids']) for g in ok)
    costs = [g['metrics']['estimated_cost_usd'] for g in ok]
    kept = sum(g['validation']['citations_kept'] for g in ok)
    dropped = sum(g['validation']['citations_dropped'] for g in ok)
    return {'calls': len(groups), 'failed_calls': len(groups) - len(ok), 'criteria': criteria,
            'latency_seconds_mean': round(sum(g['metrics']['duration_seconds'] for g in ok) / len(ok), 3) if ok else None,
            'latency_seconds_total': round(sum(g['metrics']['duration_seconds'] for g in ok), 3),
            'prompt_tokens': sum(g['metrics']['prompt_tokens'] for g in ok),
            'completion_tokens': sum(g['metrics']['completion_tokens'] for g in ok),
            'total_tokens': sum(g['metrics']['total_tokens'] for g in ok),
            'tokens_per_criterion': round(sum(g['metrics']['total_tokens'] for g in ok) / criteria, 1) if criteria else None,
            'cost_usd': round(sum(costs), 6) if costs and None not in costs else None,
            'citations_kept': kept, 'citations_dropped': dropped,
            'citation_validity': round(kept / (kept + dropped), 3) if kept + dropped else None,
            'unanswered_criteria': sum(g['validation']['unanswered'] for g in ok),
            'invalid_states': sum(g['validation']['invalid_states'] for g in ok)}
