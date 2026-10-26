"""Entradas y expectativas controladas; importar el proyecto ocurre solo aquí."""
import json
import resource
import sys

resource.setrlimit(resource.RLIMIT_FSIZE, (24 * 1024, 24 * 1024))
resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
sys.path[:0] = ['/submission/src/generated', '/submission/src']
name = sys.argv[1]
inputs = {
    'valid_tac': 'function f(a: integer): integer { return a + 1; }\nprint(f(1));\n',
    'lexical_blocks_tac': 'let a@ = 1;\n',
    'syntax_blocks_tac': 'let a: integer = ;\n',
    'semantic_blocks_tac': 'let x: integer = "a";\nprint(y);\n',
    'multiple_errors': 'let a@ = 1;\nlet b: integer = 2;\nlet c# = 3;\n',
}
try:
    from antlr4 import InputStream
    from compiler import analyze
    result = analyze(InputStream(inputs[name]))
    errors = result.get('errors', [])
    tac = result.get('tac')
    if name == 'valid_tac':
        passed = not errors and isinstance(tac, list) and bool(tac)
    elif name == 'multiple_errors':
        passed = len(errors) >= 2 and tac is None
    else:
        expected_kind = {'lexical_blocks_tac': 'léxico', 'syntax_blocks_tac': 'sintáctico',
                         'semantic_blocks_tac': 'semántico'}[name]
        passed = bool(errors) and tac is None and any(expected_kind in str(e).lower() for e in errors)
    print(json.dumps({'id': name, 'passed': bool(passed), 'input': inputs[name],
                      'errors': [str(e)[:500] for e in errors[:10]],
                      'tac_present': tac is not None,
                      'tac_preview': [str(t)[:200] for t in (tac or [])[:12]]}, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({'id': name, 'passed': False, 'error': str(exc)[:500]}, ensure_ascii=False))
