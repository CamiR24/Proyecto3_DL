"""Casos de evaluación: carga, entrega asociada y comprobación de las referencias."""
import hashlib
import json
from pathlib import Path

from .documents import ingest_submission

ROOT = Path(__file__).resolve().parent.parent
STATES = {'cumplido', 'parcial', 'faltante', 'no_verificable'}
EVIDENCE_TYPES = {'codigo', 'documentacion', 'prueba_escrita', 'ejecucion', 'ninguna'}
SPLITS = {'dev', 'test'}
CATEGORIES = {'tipico', 'dificil', 'informacion_insuficiente', 'fuera_de_alcance', 'inyeccion_prompt'}
CONFIDENCE = {'alta', 'media'}
REQUIRED = ('id', 'split', 'category', 'submission', 'criterion', 'reference_state', 'acceptable_states',
            'evidence_type', 'evidence', 'rationale', 'reference_confidence', 'author',
            'human_validated', 'validated_by')


def load_manifest():
    return json.loads((ROOT / 'evaluacion/submissions.json').read_text())


def load_cases(path):
    cases = []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if line.strip():
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f'{path}:{number}: JSON inválido ({exc.msg}).') from exc
    return cases


def assignment_text(manifest=None, submission_key=None):
    """Instrucciones de la entrega; conserva el enunciado global si no hay uno propio."""
    manifest = manifest or load_manifest()
    spec = manifest['enunciado']
    if submission_key is not None:
        spec = manifest[submission_key].get('enunciado', spec)
    text = (ROOT / spec['instrucciones']).read_text(encoding='utf-8')
    if spec.get('rubrica'):
        text += '\n\nRÚBRICA:\n' + (ROOT / spec['rubrica']).read_text(encoding='utf-8')
    return text


def load_submission(key, manifest=None):
    """Lee y procesa la entrega con el mismo ingestor que usa la aplicación."""
    manifest = manifest or load_manifest()
    path = ROOT / manifest[key]['archivo']
    data = path.read_bytes()
    submission = ingest_submission(path.name, data)
    return {**submission, 'sha256': hashlib.sha256(data).hexdigest(), 'name': path.name}


def check_case(case, manifest, cache):
    """Devuelve la lista de problemas del caso; vacía si es coherente."""
    problems = [f'falta el campo «{k}»' for k in REQUIRED if k not in case]
    if problems:
        return problems
    if case['split'] not in SPLITS:
        problems.append(f"split «{case['split']}» no válido")
    if case['category'] not in CATEGORIES:
        problems.append(f"categoría «{case['category']}» no válida")
    if case['reference_confidence'] not in CONFIDENCE:
        problems.append('reference_confidence debe ser alta o media')
    criterion = case['criterion']
    if (not isinstance(criterion, dict) or not str(criterion.get('text', '')).strip()
            or criterion.get('kind') not in {'rubrica', 'restriccion'}):
        problems.append('criterion necesita text y kind (rubrica|restriccion)')
    state, acceptable = case['reference_state'], case['acceptable_states']
    if state not in STATES:
        problems.append(f'reference_state «{state}» no válido')
    if (not isinstance(acceptable, list) or not set(acceptable) <= STATES or state not in acceptable):
        problems.append('acceptable_states debe ser una lista de estados que incluya reference_state')
    if case['evidence_type'] not in EVIDENCE_TYPES:
        problems.append(f"evidence_type «{case['evidence_type']}» no válido")
    if case['submission'] not in manifest or case['submission'] == 'enunciado':
        problems.append(f"entrega «{case['submission']}» no está en submissions.json")
        return problems
    if case['submission'] not in cache:
        cache[case['submission']] = load_submission(case['submission'], manifest)
    submission = cache[case['submission']]
    sources = {d['path']: d for d in submission['documents']}
    evidence = case['evidence']
    if not isinstance(evidence, list):
        return problems + ['evidence debe ser una lista']
    for item in evidence:
        source = sources.get(item.get('path')) if isinstance(item, dict) else None
        if not source:
            problems.append(f"la cita apunta a un archivo que el revisor no ve: {item.get('path') if isinstance(item, dict) else item}")
            continue
        start, end, quote = item.get('line_start'), item.get('line_end'), item.get('quote')
        lines = source['text'].splitlines()
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines) or end - start > 30:
            problems.append(f"{item['path']}: rango de líneas inválido {start}-{end}")
        elif not isinstance(quote, str) or not quote.strip() or quote not in '\n'.join(lines[start - 1:end]):
            problems.append(f"{item['path']}:{start}-{end}: la cita no aparece en esas líneas")
    if evidence and case['evidence_type'] == 'ninguna':
        problems.append('hay citas pero evidence_type es «ninguna»')
    if not evidence and case['evidence_type'] != 'ninguna':
        problems.append('evidence_type indica evidencia pero evidence está vacío')
    if state in {'cumplido', 'parcial'} and not evidence:
        problems.append(f'«{state}» exige al menos una cita')
    if state == 'faltante' and submission['warnings']:
        problems.append('«faltante» exige cobertura completa y esta entrega tiene advertencias de cobertura')
    return problems
