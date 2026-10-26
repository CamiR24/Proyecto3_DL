"""Solo ejecuta un perfil predefinido en Docker. No hay fallback en el host."""
import json
import os
import selectors
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from threading import Lock

RUN_LOCK = Lock()
TIMEOUT = 35
MAX_OUTPUT = 96 * 1024


def readiness():
    if os.getenv('ENABLE_RUNNER') != '1':
        return {'available': False, 'reason': 'Ejecución desactivada. Activa ENABLE_RUNNER después de preparar Docker.'}
    if not shutil.which('docker'):
        return {'available': False, 'reason': 'Docker no está instalado o no está en PATH.'}
    return {'available': True, 'reason': 'Docker encontrado; la imagen y el motor se comprobarán al ejecutar.'}


def command(project, name):
    image = os.getenv('RUNNER_IMAGE', 'revisor-compiscript:v1')
    return ['docker', 'run', '--rm', '--pull=never', '--name', name,
            '--network', 'none', '--read-only', '--user', '65534:65534',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--memory', '256m', '--memory-swap', '256m', '--cpus', '1',
            '--pids-limit', '32', '--ulimit', 'nofile=128:128',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=32m,mode=1777',
            '--mount', f'type=bind,src={project},dst=/submission,readonly',
            '--workdir', '/submission', image]


def bounded_process(args, timeout):
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = bytearray()
    reason = None
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + timeout
            while selector.get_map():
                if time.monotonic() >= deadline:
                    reason = 'timeout'
                    break
                for key, _ in selector.select(timeout=min(.2, max(0, deadline-time.monotonic()))):
                    block = os.read(key.fileobj.fileno(), 4096)
                    if not block:
                        selector.unregister(key.fileobj)
                    else:
                        output.extend(block)
                        if len(output) > MAX_OUTPUT:
                            reason = 'output_limit'
                            break
                if reason:
                    break
        if reason:
            process.kill()
        process.wait(timeout=2)
        return process.returncode, output[:MAX_OUTPUT].decode('utf-8', errors='replace'), reason
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()


def run_checks(files, profile='compiscript-v1'):
    if profile != 'compiscript-v1':
        raise ValueError('Perfil de ejecución no permitido.')
    ready = readiness()
    if not ready['available']:
        return {'status': 'unavailable', 'executed': False, 'cases': [], 'message': ready['reason']}
    if not files or 'src/compiler.py' not in files:
        return {'status': 'incompatible', 'executed': False, 'cases': [],
                'message': 'El ZIP no contiene el árbol src de Compiscript admitido.'}
    if not RUN_LOCK.acquire(blocking=False):
        return {'status': 'busy', 'executed': False, 'cases': [], 'message': 'Ya hay una ejecución en curso.'}
    started = time.monotonic()
    name = 'revisor-' + uuid.uuid4().hex
    try:
        with tempfile.TemporaryDirectory(prefix='revisor-') as folder:
            project = Path(folder)
            project.chmod(0o755)
            for path, data in files.items():
                relative = Path(path)
                if relative.is_absolute() or '..' in relative.parts or relative.parts[0] != 'src' or relative.suffix != '.py':
                    raise ValueError('Archivo fuera del perfil permitido.')
                dest = project / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                dest.chmod(0o444)
            for directory in project.rglob('*'):
                if directory.is_dir():
                    directory.chmod(0o755)
            code, text, stopped = bounded_process(command(project, name), TIMEOUT)
            if stopped:
                return {'status': stopped, 'executed': False, 'cases': [],
                        'message': 'Ejecución detenida por límite de tiempo o salida.', 'log': text}
            if code != 0:
                return {'status': 'error', 'executed': False, 'cases': [],
                        'message': 'No se completó el perfil. Revisa Docker, imagen y dependencias.', 'log': text}
            try:
                result = json.loads(text)
                expected = {'valid_tac', 'lexical_blocks_tac', 'syntax_blocks_tac',
                            'semantic_blocks_tac', 'multiple_errors'}
                cases = result['cases']
                if not isinstance(cases, list) or {c['id'] for c in cases} != expected or len(cases) != 5:
                    raise ValueError('Resultados incompletos.')
                if any(type(c['passed']) is not bool for c in cases):
                    raise ValueError('Resultado inválido.')
            except (ValueError, TypeError, KeyError) as exc:
                return {'status': 'error', 'executed': False, 'cases': [],
                        'message': 'El perfil no produjo resultados válidos.', 'log': text}
            return {'status': 'completed', 'executed': True, 'cases': cases,
                    'duration_seconds': round(time.monotonic()-started, 3),
                    'profile': profile,
                    'message': 'Resultados limitados a estos cinco casos; no prueban corrección general.'}
    finally:
        # Matar el cliente no garantiza detener el contenedor: siempre se elimina.
        try:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        RUN_LOCK.release()
