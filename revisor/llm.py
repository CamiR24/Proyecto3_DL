"""Cliente HTTP, prompts versionados, herramienta restringida y citas verificadas."""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from .documents import context_documents
from .runner import run_checks

ROOT = Path(__file__).resolve().parent.parent
VALID_STATES = {'cumplido', 'parcial', 'faltante', 'no_verificable'}
TOOL = {'type': 'function', 'function': {
    'name': 'run_compiscript_checks',
    'description': 'Ejecuta cinco pruebas fijas en el contenedor Compiscript. No acepta código ni comandos.',
    'parameters': {'type': 'object', 'properties': {'profile': {
        'type': 'string', 'enum': ['compiscript-v1']}}, 'required': ['profile'],
        'additionalProperties': False}}}


def model_configured():
    return bool(os.getenv('LLM_MODEL') and os.getenv('LLM_API_KEY'))


def completion(messages, tools=None):
    if not model_configured():
        raise ValueError('Falta configurar LLM_API_KEY y LLM_MODEL en .env. Puedes cargar y explorar archivos sin LLM.')
    body = {
        'model': os.environ['LLM_MODEL'],
        'messages': messages,
        'max_completion_tokens': 6000,
    }

    if os.environ['LLM_MODEL'] == 'claude-haiku-5-5':
        body['thinking'] = {'type': 'disabled'}
    if tools:
        body.update(tools=tools, tool_choice='auto', parallel_tool_calls=False)
    url = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1').rstrip('/') + '/chat/completions'
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['LLM_API_KEY']})
    try:
        with urllib.request.urlopen(request, timeout=100) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError('La respuesta del proveedor excede el límite.')
            result = json.loads(raw)
    except urllib.error.HTTPError as exc:
        # No reenviar cuerpo, cabeceras o credenciales del proveedor al navegador.
        raise ValueError(f'El proveedor devolvió HTTP {exc.code}. Revisa modelo, saldo y compatibilidad con JSON/tools.') from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError('No se pudo conectar al modelo dentro del tiempo permitido.') from exc
    try:
        choice = result['choices'][0]
        if choice.get('finish_reason') == 'length':
            raise ValueError('El modelo alcanzó el límite de salida. Reduce los criterios o el contexto.')
        return choice['message'], result.get('usage', {})
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError('Respuesta del proveedor no compatible.') from exc


def parse_json(message):
    content = message.get('content')

    if not isinstance(content, str) or not content.strip():
        raise ValueError('El modelo devolvió una respuesta vacía.')

    content = content.strip()
    lines = content.splitlines()

    # Aceptar un bloque Markdown que contenga únicamente JSON.
    if (
        len(lines) >= 3
        and lines[0].strip().lower() in {'```json', '```'}
        and lines[-1].strip() == '```'
    ):
        content = '\n'.join(lines[1:-1]).strip()

    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        # Mostrar un fragmento en la terminal para diagnosticar el formato.
        preview = content[:600]
        key = os.getenv('LLM_API_KEY', '')
        if key:
            preview = preview.replace(key, '[LLAVE OCULTA]')
        print('Respuesta no interpretable:', repr(preview))

        raise ValueError(
            'La respuesta no tiene un formato JSON válido. '
            'Revisa el detalle en la terminal.'
        ) from exc

    if not isinstance(value, dict):
        raise ValueError('Se esperaba un objeto JSON.')

    return value


def metrics(usages, started):
    prompt = sum(u.get('prompt_tokens', 0) for u in usages)
    output = sum(u.get('completion_tokens', 0) for u in usages)
    cost = None
    try:
        cost = round((prompt * float(os.environ['LLM_INPUT_USD_PER_MILLION']) +
                      output * float(os.environ['LLM_OUTPUT_USD_PER_MILLION'])) / 1_000_000, 6)
    except (KeyError, ValueError):
        pass
    return {'model': os.getenv('LLM_MODEL'), 'prompt_tokens': prompt, 'completion_tokens': output,
            'total_tokens': prompt+output, 'duration_seconds': round(time.monotonic()-started, 3),
            'estimated_cost_usd': cost,
            'cost_note': 'Estimación con precios configurados; no considera descuentos de caché ni otros cargos.'}


def extract_criteria(text):
    if not text.strip() or len(text) > 40_000:
        raise ValueError('Las instrucciones y rúbrica deben contener entre 1 y 40 000 caracteres.')
    prompt = (ROOT / 'prompts/criteria-v1.txt').read_text()
    started = time.monotonic()
    message, usage = completion([{'role': 'system', 'content': prompt},
                                {'role': 'user', 'content': json.dumps({'assignment': text}, ensure_ascii=False)}])
    value = parse_json(message)
    criteria = value.get('criteria')
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 30:
        raise ValueError('El modelo debe devolver de 1 a 30 criterios. Puedes ingresarlos manualmente.')
    clean = []
    for index, item in enumerate(criteria, 1):
        if not isinstance(item, dict) or not isinstance(item.get('text'), str) or not item['text'].strip():
            raise ValueError('Criterio generado incompleto; ingrésalo manualmente.')
        clean.append({'id': f'C{index:02}', 'text': item['text'][:1500],
                      'kind': 'restriccion' if item.get('kind') == 'restriccion' else 'rubrica'})
    return {'criteria': clean, 'metrics': metrics([usage], started)}


def manual_criteria(text):
    lines = [line.strip().lstrip('- ').strip() for line in text.splitlines() if line.strip()]
    if not 1 <= len(lines) <= 30 or any(len(line) > 1500 for line in lines):
        raise ValueError('Escribe entre 1 y 30 criterios, uno por línea, de hasta 1500 caracteres cada uno.')
    return [{'id': f'C{i:02}', 'text': line.replace('[R]', '', 1).strip() if line.startswith('[R]') else line,
             'kind': 'restriccion' if line.startswith('[R]') else 'rubrica'} for i, line in enumerate(lines, 1)]


def normalize_review(raw, criteria, documents, execution, incomplete=False):
    rows = raw.get('results')
    if not isinstance(rows, list):
        raise ValueError('El modelo no devolvió resultados por criterio.')
    by_id = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get('criterion_id'), str):
            by_id[row['criterion_id']] = row
    sources = {d['path']: d for d in documents}
    actual_cases = {c['id']: c for c in (execution or {}).get('cases', [])} if (execution or {}).get('executed') else {}
    results = []
    for criterion in criteria:
        row = by_id.get(criterion['id'], {})
        state = row.get('state', 'no_verificable')
        if not isinstance(state, str) or state not in VALID_STATES:
            state = 'no_verificable'
        citations = []
        supplied = row.get('evidence', [])
        for evidence in supplied[:4] if isinstance(supplied, list) else []:
            if not isinstance(evidence, dict):
                continue
            path = evidence.get('path', '')
            source = sources.get(path) if isinstance(path, str) else None
            start, end = evidence.get('line_start'), evidence.get('line_end')
            quote = evidence.get('quote')
            if not source or type(start) is not int or type(end) is not int or not isinstance(quote, str):
                continue
            lines = source['text'].splitlines()
            if 1 <= start <= end <= len(lines) and end-start <= 30 and quote.strip() and quote in '\n'.join(lines[start-1:end]):
                citations.append({'path': source['path'], 'line_start': start, 'line_end': end, 'quote': quote[:2500]})
        ids = row.get('test_ids', [])
        ids = [i for i in ids if isinstance(i, str) and i in actual_cases] if isinstance(ids, list) else []
        evidence_type = row.get('evidence_type', 'ninguna')
        if not isinstance(evidence_type, str) or evidence_type not in {'codigo', 'documentacion', 'prueba_escrita', 'ejecucion', 'ninguna'}:
            evidence_type = 'ninguna'
        warnings = []
        if evidence_type == 'ejecucion' and not ids:
            warnings.append('No existe una ejecución registrada que respalde esta conclusión.')
            evidence_type = 'codigo' if citations else 'ninguna'
            if state == 'cumplido':
                state = 'no_verificable'
        if state in {'cumplido', 'parcial'} and not citations and not ids:
            state = 'no_verificable'
            warnings.append('No se pudo validar la evidencia citada por el modelo.')
        if state == 'faltante' and incomplete:
            state = 'no_verificable'
            warnings.append('La cobertura es parcial: no encontrar evidencia no demuestra que falte en toda la entrega.')
        if state == 'cumplido' and ids and any(not actual_cases[i]['passed'] for i in ids):
            state = 'parcial'
            warnings.append('Hay pruebas citadas que fallaron; revisar la interpretación del modelo.')
        results.append({**criterion, 'state': state, 'evidence_type': evidence_type,
                        'explanation': str(row.get('explanation', 'No se recibió una evaluación válida para este criterio.'))[:4000],
                        'suggestion': str(row.get('suggestion', 'Revisar manualmente.'))[:3000],
                        'needs_verification': str(row.get('needs_verification', ''))[:2000],
                        'evidence': citations, 'test_ids': ids, 'warnings': warnings})
    return results


def review(session, criteria, allow_execution=False, baseline=False):
    prompt_file = 'baseline-v1.txt' if baseline else 'review-v1.txt'
    prompt = (ROOT / 'prompts' / prompt_file).read_text()
    docs = session['submission']['documents']
    payload = {'assignment': session['assignment'], 'criteria': criteria,
               'documents': context_documents(docs), 'coverage_warnings': session['submission']['warnings'],
               'execution': session.get('execution'), 'runner_compatible': session['submission']['runner_compatible']}
    messages = [{'role': 'system', 'content': prompt},
                {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}]
    started = time.monotonic()
    usages = []
    can_call = bool(allow_execution and not baseline and session['submission']['runner_compatible'])
    message, usage = completion(messages, [TOOL] if can_call else None)
    usages.append(usage)
    if message.get('tool_calls'):
        calls = message['tool_calls']
        if not can_call or len(calls) != 1:
            raise ValueError('El modelo solicitó una herramienta no autorizada o demasiadas llamadas.')
        call = calls[0]
        function = call.get('function', {})
        if function.get('name') != 'run_compiscript_checks':
            raise ValueError('Herramienta no permitida.')
        try:
            arguments = json.loads(function.get('arguments', ''))
        except ValueError as exc:
            raise ValueError('Argumentos de herramienta inválidos.') from exc
        if arguments != {'profile': 'compiscript-v1'}:
            raise ValueError('La herramienta solo admite el perfil fijo compiscript-v1.')
        execution = session.get('execution') or run_checks(session['submission']['runner_files'])
        session['execution'] = execution
        messages.extend([{'role': 'assistant', 'content': message.get('content'), 'tool_calls': calls},
                         {'role': 'tool', 'tool_call_id': call['id'],
                          'content': json.dumps(execution, ensure_ascii=False)}])
        message, usage = completion(messages)
        usages.append(usage)
        if message.get('tool_calls'):
            raise ValueError('Se alcanzó el límite de una llamada a herramientas por revisión.')
    value = parse_json(message)
    results = normalize_review(value, criteria, docs, session.get('execution'),
                               bool(session['submission']['warnings']))
    return {'results': results, 'metrics': metrics(usages, started),
            'prompt_version': prompt_file, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
            'criteria': criteria, 'execution': session.get('execution'),
            'submission_sha256': session['submission_sha256'],
            'assignment_sha256': hashlib.sha256(session['assignment'].encode()).hexdigest(),
            'coverage': {'files': len(docs), 'warnings': session['submission']['warnings']},
            'notice': 'Revisión orientativa. Las citas se validan por coincidencia textual, no por corrección semántica. '
                      'Una prueba aprobada solo respalda el caso ejecutado. No se asigna nota automática.'}
