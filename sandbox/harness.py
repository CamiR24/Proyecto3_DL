"""Orquesta cinco procesos de prueba en el contenedor, nunca en el host."""
import json
import subprocess
import tempfile
import os

CASES = ['valid_tac', 'lexical_blocks_tac', 'syntax_blocks_tac',
         'semantic_blocks_tac', 'multiple_errors']
results = []
for case in CASES:
    with tempfile.TemporaryFile() as out:
        try:
            process = subprocess.run(['python', '-I', '/opt/case.py', case],
                                     stdout=out, stderr=subprocess.STDOUT, timeout=4)
            out.seek(0)
            raw = out.read(32 * 1024).decode('utf-8', errors='replace')
            result = json.loads(raw)
            if process.returncode != 0 or result.get('id') != case or type(result.get('passed')) is not bool:
                raise ValueError('La prueba no devolvió un resultado válido.')
            results.append(result)
        except (subprocess.TimeoutExpired, ValueError, TypeError, AttributeError) as exc:
            results.append({'id': case, 'passed': False, 'error': str(exc)[:500]})
print(json.dumps({'cases': results}, ensure_ascii=False))
