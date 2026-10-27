"""Verifica el flujo HTTP real sin gastar API ni ejecutar material del alumno."""
import base64
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class HTTPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        app.PORT = cls.server.server_port
        cls.base = f'http://127.0.0.1:{app.PORT}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def tearDown(self):
        app.SESSIONS.clear()

    def post(self, path, payload, authorized=True, origin=None):
        headers = {'Content-Type': 'application/json'}
        if authorized:
            headers['X-Revisor-Token'] = app.TOKEN
        if origin:
            headers['Origin'] = origin
        request = urllib.request.Request(self.base+path, data=json.dumps(payload).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    def ingest(self):
        source = 'if not errors:\n    generate_tac()\n'
        status, result = self.post('/api/ingest', {
            'instructions': 'No generar TAC si hay errores.',
            'submission': {'name': 'compiler.py', 'data': base64.b64encode(source.encode()).decode()}})
        self.assertEqual(status, 200)
        return result

    def test_requires_local_token_and_rejects_foreign_origin(self):
        status, _ = self.post('/api/example', {}, authorized=False)
        self.assertEqual(status, 403)
        status, _ = self.post('/api/example', {}, origin='https://another-site.example')
        self.assertEqual(status, 403)

    def test_real_upload_review_and_delete_with_mocked_llm(self):
        session = self.ingest()
        raw = {'results': [{'criterion_id': 'C01', 'state': 'parcial', 'evidence_type': 'codigo',
                           'explanation': 'Control encontrado, falta ejecución.', 'suggestion': 'Ejecutar prueba.',
                           'evidence': [{'path': 'compiler.py', 'line_start': 1, 'line_end': 2,
                                         'quote': 'if not errors:\n    generate_tac()'}]}]}
        with patch('revisor.llm.completion', return_value=({'content': json.dumps(raw)}, {'prompt_tokens': 12, 'completion_tokens': 8})):
            status, report = self.post('/api/review', {'session_id': session['session_id'],
                                                     'criteria_text': '[R] No TAC con errores'})
        self.assertEqual(status, 200)
        self.assertEqual(report['results'][0]['state'], 'parcial')
        self.assertEqual(report['metrics']['total_tokens'], 20)
        self.assertEqual(len(report['results'][0]['evidence']), 1)
        status, deleted = self.post('/api/delete', {'session_id': session['session_id']})
        self.assertEqual(status, 200)
        self.assertTrue(deleted['deleted'])
        self.assertNotIn(session['session_id'], app.SESSIONS)

    def test_example_contains_real_context_without_fabricated_execution(self):
        status, session = self.post('/api/example', {})
        self.assertEqual(status, 200)
        self.assertTrue(session['runner_compatible'])
        self.assertEqual(len(session['criteria_text'].splitlines()), 24)
        self.assertNotIn('execution', session)
        with patch.dict(os.environ, {'ENABLE_RUNNER': '0'}):
            status, result = self.post('/api/run', {'session_id': session['session_id']})
        self.assertEqual(status, 200)
        self.assertFalse(result['executed'])

    def test_serves_every_page_asset_the_html_references(self):
        for path, kind in [('/', 'text/html'), ('/app.js', 'text/javascript'), ('/resultados.js', 'text/javascript'),
                           ('/style.css', 'text/css'), ('/resultados.css', 'text/css')]:
            with urllib.request.urlopen(self.base + path) as response:
                self.assertEqual(response.status, 200, path)
                self.assertTrue(response.headers['Content-Type'].startswith(kind), path)

    def test_review_report_includes_format_validation(self):
        session = self.ingest()
        raw = {'results': [{'criterion_id': 'C01', 'state': 'raro'}]}
        with patch('revisor.llm.completion', return_value=({'content': json.dumps(raw)}, {})):
            status, report = self.post('/api/review', {'session_id': session['session_id'], 'criteria_text': 'Criterio'})
        self.assertEqual(status, 200)
        self.assertEqual(report['validation']['invalid_states'], 1)
        self.assertEqual(report['results'][0]['state'], 'no_verificable')

    def test_missing_api_key_returns_actionable_error(self):
        session = self.ingest()
        with patch.dict(os.environ, {'LLM_API_KEY': '', 'LLM_MODEL': ''}):
            status, result = self.post('/api/review', {'session_id': session['session_id'], 'criteria_text': 'Criterio'})
        self.assertEqual(status, 400)
        self.assertIn('LLM_API_KEY', result['error'])


if __name__ == '__main__':
    unittest.main()
