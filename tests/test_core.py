import base64
import io
import json
import os
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from revisor.documents import ingest_submission, read_upload
from revisor.llm import manual_criteria, normalize_review, review
from revisor.runner import command, run_checks


def archive(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        for name, data in entries:
            z.writestr(name, data)
    return stream.getvalue()


class DocumentsTest(unittest.TestCase):
    def test_rejects_zip_traversal_without_extracting(self):
        for name in ['../outside.py', '/outside.py', 'repo/../../evil.py', 'repo\\evil.py']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                ingest_submission('project.zip', archive([(name, 'print(1)')]))

    def test_filters_dependencies_and_keeps_sources_for_runner(self):
        data = archive([('repo/node_modules/malware.js', 'do not review'),
                        ('repo/.env', 'SECRET=private'),
                        ('repo/src/compiler.py', 'def analyze(s): return {}'),
                        ('repo/src/generated/CompiscriptParser.py', '# generated'),
                        ('repo/src/generated/CompiscriptLexer.py', '# generated'),
                        ('repo/README.md', 'A compiler')])
        value = ingest_submission('p.zip', data)
        self.assertTrue(value['runner_compatible'])
        self.assertTrue(value['warnings'])
        self.assertEqual(len(value['documents']), 2)
        self.assertNotIn('SECRET', str(value['documents']))
        self.assertIn('src/compiler.py', value['runner_files'])

    def test_symlink_is_not_materialized_or_used(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z:
            info = zipfile.ZipInfo('repo/src/link.py')
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            z.writestr(info, '/etc/passwd')
            z.writestr('repo/README.md', 'safe')
        result = ingest_submission('p.zip', stream.getvalue())
        self.assertFalse(result['runner_files'])
        self.assertEqual(result['documents'][0]['text'], 'safe')

    def test_reports_context_truncation(self):
        result = ingest_submission('p.md', ('X' * 150_000).encode())
        self.assertTrue(result['documents'][0]['truncated'])
        self.assertTrue(result['warnings'])

    def test_rejects_unsupported_and_bad_base64(self):
        with self.assertRaises(ValueError):
            ingest_submission('p.exe', b'123')
        with self.assertRaises(ValueError):
            read_upload({'name': 'x', 'data': 'not base64!!'})


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.criteria = manual_criteria('[R] No TAC con errores\nInterfaz usable')
        self.docs = [{'path': 'compiler.py', 'text': 'if not errors:\n    generate_tac()\n', 'truncated': False}]

    def test_invented_citation_cannot_mark_criterion_fulfilled(self):
        raw = {'results': [{'criterion_id': 'C01', 'state': 'cumplido', 'evidence_type': 'codigo',
                            'evidence': [{'path': 'compiler.py', 'line_start': 1, 'line_end': 2, 'quote': 'imaginary code'}]}]}
        result = normalize_review(raw, self.criteria, self.docs, None)
        self.assertEqual(result[0]['state'], 'no_verificable')
        self.assertEqual(result[1]['state'], 'no_verificable')

    def test_cannot_claim_execution_that_never_happened(self):
        raw = {'results': [{'criterion_id': 'C01', 'state': 'cumplido', 'evidence_type': 'ejecucion',
                            'test_ids': ['imaginary_test']}]}
        result = normalize_review(raw, self.criteria, self.docs, {'executed': False, 'cases': []})
        self.assertEqual(result[0]['state'], 'no_verificable')
        self.assertEqual(result[0]['evidence_type'], 'ninguna')

    def test_failed_test_cannot_be_reported_as_fully_compliant(self):
        raw = {'results': [{'criterion_id': 'C01', 'state': 'cumplido', 'evidence_type': 'ejecucion',
                            'test_ids': ['case1']}]}
        execution = {'executed': True, 'cases': [{'id': 'case1', 'passed': False}]}
        result = normalize_review(raw, self.criteria, self.docs, execution)
        self.assertEqual(result[0]['state'], 'parcial')

    def test_missing_with_partial_coverage_is_unknown(self):
        raw = {'results': [{'criterion_id': 'C01', 'state': 'faltante'}]}
        result = normalize_review(raw, self.criteria, self.docs, None, incomplete=True)
        self.assertEqual(result[0]['state'], 'no_verificable')

    def test_real_text_citation_is_kept(self):
        raw = {'results': [{'criterion_id': 'C01', 'state': 'parcial', 'evidence_type': 'codigo',
                            'evidence': [{'path': 'compiler.py', 'line_start': 1, 'line_end': 2,
                                          'quote': 'if not errors:\n    generate_tac()'}]}]}
        result = normalize_review(raw, self.criteria, self.docs, None)
        self.assertEqual(len(result[0]['evidence']), 1)
        self.assertEqual(result[0]['state'], 'parcial')


class RunnerTest(unittest.TestCase):
    def test_runner_disabled_never_falls_back_to_local_execution(self):
        with patch.dict(os.environ, {'ENABLE_RUNNER': '0'}), patch('subprocess.Popen') as popen:
            result = run_checks({'src/compiler.py': b'import os'})
        self.assertFalse(result['executed'])
        popen.assert_not_called()

    def test_rejects_arbitrary_profile(self):
        with self.assertRaises(ValueError):
            run_checks({}, profile='run-shell-command')

    def test_tool_call_is_restricted_and_real_result_returned_to_model(self):
        session = {'assignment': 'instructions', 'submission_sha256': 'abc',
                   'submission': {'documents': [], 'warnings': [], 'runner_compatible': True,
                                  'runner_files': {'src/compiler.py': b''}}}
        first = {'content': None, 'tool_calls': [{'id': 'call1', 'type': 'function',
                 'function': {'name': 'run_compiscript_checks', 'arguments': '{"profile":"compiscript-v1"}'}}]}
        final = {'content': '{"results":[]}'}
        actual = {'executed': False, 'status': 'unavailable', 'cases': []}
        with patch('revisor.llm.completion', side_effect=[(first, {}), (final, {})]) as comp, patch('revisor.llm.run_checks', return_value=actual) as run:
            report = review(session, manual_criteria('criterion'), allow_execution=True)
        run.assert_called_once()
        self.assertEqual(report['execution'], actual)
        self.assertEqual(comp.call_args_list[1].args[0][-1]['role'], 'tool')

    def test_tool_arguments_cannot_smuggle_command(self):
        session = {'assignment': 'x', 'submission_sha256': 'abc',
                   'submission': {'documents': [], 'warnings': [], 'runner_compatible': True, 'runner_files': {}}}
        tool = {'content': None, 'tool_calls': [{'id': 'c', 'function': {
            'name': 'run_compiscript_checks', 'arguments': '{"profile":"compiscript-v1","command":"rm -rf /"}'}}]}
        with patch('revisor.llm.completion', return_value=(tool, {})), patch('revisor.llm.run_checks') as run:
            with self.assertRaises(ValueError):
                review(session, manual_criteria('c'), allow_execution=True)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
