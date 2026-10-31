#!/usr/bin/env python3
"""Servidor local sin framework; el material cargado no se ejecuta en este proceso."""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from revisor.documents import ingest_submission, plain_document, read_upload
from revisor.llm import PROMPTS, extract_criteria, manual_criteria, model_configured, review
from revisor.runner import readiness, run_checks

ROOT = Path(__file__).resolve().parent


def load_env():
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text().splitlines():
            key, separator, value = line.strip().partition('=')
            if separator and key and not key.startswith('#'):
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
PORT = int(os.getenv('PORT', '8000'))
TOKEN = secrets.token_urlsafe(32)
SESSIONS = {}
STORE_LOCK = threading.Lock()
MODEL_LOCK = threading.Lock()
MAX_BODY = 115 * 1024 * 1024


def new_session(assignment, name, data):
    if not assignment.strip() or len(assignment) > 40_000:
        raise ValueError('Agrega instrucciones y rúbrica (máximo 40 000 caracteres).')
    submission = ingest_submission(name, data)
    value = {'assignment': assignment, 'submission': submission,
             'submission_sha256': hashlib.sha256(data).hexdigest(),
             'created': time.monotonic(), 'lock': threading.Lock()}
    with STORE_LOCK:
        expired = [key for key, session in SESSIONS.items() if time.monotonic()-session['created'] > 7200]
        for key in expired:
            del SESSIONS[key]
        if len(SESSIONS) >= 8:
            raise ValueError('Hay ocho revisiones abiertas. Elimina una revisión o reinicia la aplicación.')
        key = secrets.token_urlsafe(24)
        SESSIONS[key] = value
    return session_public(key, value)


def session_public(key, value):
    submission = value['submission']
    return {'session_id': key, 'assignment': value['assignment'],
            'documents': submission['documents'], 'warnings': submission['warnings'],
            'runner_compatible': submission['runner_compatible']}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # No registrar datos de entregas ni cuerpos de solicitudes.

    def send(self, value, status=200, content_type='application/json; charset=utf-8'):
        data = json.dumps(value, ensure_ascii=False).encode() if content_type.startswith('application/json') else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}

    def do_GET(self):
        if not self.valid_host():
            return self.send({'error': 'Acceso solo desde localhost.'}, 403)
        path = urlsplit(self.path).path
        if path == '/api/config':
            return self.send({'token': TOKEN, 'model_configured': model_configured(),
                              'model': os.getenv('LLM_MODEL', ''), 'runner': readiness()})
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8'),
                 '/resultados.js': ('resultados.js', 'text/javascript; charset=utf-8'),
                 '/resultados.css': ('resultados.css', 'text/css; charset=utf-8')}
        if path in files:
            name, kind = files[path]
            return self.send((ROOT / 'web' / name).read_bytes(), content_type=kind)
        return self.send({'error': 'Ruta no encontrada.'}, 404)

    def do_POST(self):
        if not self.valid_host() or self.headers.get('X-Revisor-Token') != TOKEN:
            return self.send({'error': 'Solicitud no autorizada.'}, 403)
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'}:
            return self.send({'error': 'Origen no permitido.'}, 403)
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.send({'error': 'Se requiere JSON.'}, 415)
        try:
            self.connection.settimeout(120)
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BODY:
                return self.send({'error': 'Solicitud vacía o demasiado grande.'}, 413)
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Se esperaba un objeto JSON.')
            path = urlsplit(self.path).path
            if path == '/api/ingest':
                assignment = str(data.get('instructions', ''))
                if data.get('rubric'):
                    name, raw = read_upload(data['rubric'])
                    if name.lower().endswith('.zip'):
                        raise ValueError('La rúbrica debe ser PDF, TXT o MD.')
                    assignment += '\n\nRÚBRICA:\n' + plain_document(name, raw)
                name, raw = read_upload(data.get('submission', {}))
                return self.send(new_session(assignment, name, raw))
            if path == '/api/example':
                example = ROOT / 'examples'
                assignment = (example / 'instrucciones_compiladores.md').read_text()
                assignment += '\n\nRÚBRICA:\n' + (example / 'rubrica_compiladores.txt').read_text()
                result = new_session(assignment, 'compiscript-ejemplo.zip', (example / 'compiscript-ejemplo.zip').read_bytes())
                result['criteria_text'] = (example / 'criterios_compiladores.txt').read_text()
                return self.send(result)
            with STORE_LOCK:
                session = SESSIONS.get(data.get('session_id', ''))
            if not session or time.monotonic()-session['created'] > 7200:
                raise ValueError('La revisión expiró. Vuelve a cargar los archivos.')
            if path == '/api/delete':
                with STORE_LOCK:
                    SESSIONS.pop(data['session_id'], None)
                return self.send({'deleted': True})
            if not session['lock'].acquire(blocking=False):
                return self.send({'error': 'Esta revisión ya tiene una operación en curso.'}, 409)
            try:
                if path == '/api/run':
                    if not session['submission']['runner_compatible']:
                        raise ValueError('La entrega no corresponde al perfil Compiscript admitido.')
                    session['execution'] = run_checks(session['submission']['runner_files'])
                    session['execution_origin'] = 'manual'
                    return self.send(session['execution'])
                if path not in {'/api/criteria', '/api/review'}:
                    return self.send({'error': 'Ruta no encontrada.'}, 404)
                if not MODEL_LOCK.acquire(blocking=False):
                    return self.send({'error': 'Ya hay una solicitud al modelo. Espera antes de iniciar otra.'}, 409)
                try:
                    if path == '/api/criteria':
                        return self.send(extract_criteria(session['assignment']))
                    criteria = manual_criteria(str(data.get('criteria_text', '')))
                    prompt_file = PROMPTS.get(data.get('mode'), PROMPTS['improved'])
                    return self.send(review(session, criteria, data.get('allow_execution') is True,
                                            prompt_file=prompt_file))
                finally:
                    MODEL_LOCK.release()
            finally:
                session['lock'].release()
        except (ValueError, KeyError, TypeError) as exc:
            return self.send({'error': str(exc)}, 400)
        except Exception:
            return self.send({'error': 'No se pudo completar la operación. Revisa el archivo o la configuración local.'}, 500)


if __name__ == '__main__':
    print(f'Revisor listo en http://127.0.0.1:{PORT} — Ctrl+C para detener.')
    print('Los archivos cargados se conservan en memoria hasta eliminarlos o cerrar el servidor.')
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
