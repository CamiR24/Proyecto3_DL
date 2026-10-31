"""Trazabilidad de herramientas sin API ni Docker."""
import copy
import unittest
from unittest.mock import patch

from revisor import llm


class ToolTraceTests(unittest.TestCase):
    def setUp(self):
        self.session = {'submission': {'runner_compatible': True, 'runner_files': {},
                                      'documents': [], 'warnings': []},
                        'submission_sha256': 'submission', 'assignment': 'assignment'}
        self.execution = {'executed': True, 'cases': [{'id': 'valid_tac', 'passed': True}]}
        self.final = {'content': '{"results": []}'}
        self.call = {'tool_calls': [{'id': 'call_1', 'type': 'function', 'function': {
            'name': 'run_compiscript_checks', 'arguments': '{"profile":"compiscript-v1"}'}}]}
        self.messages = patch.object(llm, 'review_messages', return_value=('prompt', []))
        self.messages.start()
        self.addCleanup(self.messages.stop)

    def run_review(self, responses, allow=True, prompt='review-v2.txt'):
        with patch.object(llm, 'completion', side_effect=[(r, {}) for r in responses]) as api, \
             patch.object(llm, 'run_checks', return_value=copy.deepcopy(self.execution)) as runner:
            result = llm.review(self.session, [], allow_execution=allow, prompt_file=prompt)
            return result, api, runner

    def test_no_request_does_not_run_checks(self):
        result, api, runner = self.run_review([self.final])
        self.assertFalse(result['execution_trace']['tool_requested'])
        self.assertIsNone(result['execution'])
        runner.assert_not_called()
        self.assertEqual(api.call_args_list[0].args[1], [llm.TOOL])

    def test_model_request_runs_and_returns_tool_result(self):
        result, api, runner = self.run_review([self.call, self.final])
        trace = result['execution_trace']
        self.assertTrue(trace['tool_requested'])
        self.assertTrue(trace['runner_invoked'])
        self.assertFalse(trace['execution_reused'])
        self.assertEqual(trace['execution_origin'], 'model_tool')
        self.assertEqual(trace['tool_call_id'], 'call_1')
        runner.assert_called_once_with({})
        self.assertEqual(api.call_args_list[1].args[0][-1]['role'], 'tool')
        self.assertEqual(api.call_count, 2)

    def test_manual_results_are_available_without_tool_request(self):
        self.session.update(execution=self.execution, execution_origin='manual')
        result, api, runner = self.run_review([self.final])
        trace = result['execution_trace']
        self.assertTrue(trace['execution_available_before_review'])
        self.assertFalse(trace['tool_requested'])
        self.assertEqual(trace['execution_origin'], 'manual')
        runner.assert_not_called()

    def test_tool_request_reuses_manual_results(self):
        self.session.update(execution=self.execution, execution_origin='manual')
        result, api, runner = self.run_review([self.call, self.final])
        trace = result['execution_trace']
        self.assertTrue(trace['tool_requested'])
        self.assertTrue(trace['execution_reused'])
        self.assertFalse(trace['runner_invoked'])
        self.assertEqual(trace['execution_origin'], 'manual')
        self.assertEqual(result['execution'], self.execution)
        runner.assert_not_called()

    def test_request_flag_resets_but_origin_persists(self):
        self.run_review([self.call, self.final])
        result, api, runner = self.run_review([self.final])
        self.assertFalse(result['execution_trace']['tool_requested'])
        self.assertEqual(result['execution_trace']['execution_origin'], 'model_tool')
        runner.assert_not_called()

    def test_legacy_execution_does_not_invent_origin(self):
        self.session['execution'] = self.execution
        result, api, runner = self.run_review([self.final])
        self.assertEqual(result['execution_trace']['execution_origin'], 'unknown')
        runner.assert_not_called()

    def test_baseline_does_not_offer_tools(self):
        result, api, runner = self.run_review([self.final], prompt='baseline-v1.txt')
        self.assertFalse(result['execution_trace']['tools_enabled'])
        self.assertIsNone(api.call_args.args[1])
        runner.assert_not_called()

    def test_permission_and_compatibility_are_required(self):
        for allow, compatible in [(False, True), (True, False)]:
            with self.subTest(allow=allow, compatible=compatible):
                self.session['submission']['runner_compatible'] = compatible
                result, api, runner = self.run_review([self.final], allow=allow)
                self.assertFalse(result['execution_trace']['tools_enabled'])
                self.assertIsNone(api.call_args.args[1])
                runner.assert_not_called()

    def test_unauthorized_call_is_rejected(self):
        with patch.object(llm, 'completion', return_value=(self.call, {})), \
             patch.object(llm, 'run_checks') as runner:
            with self.assertRaises(ValueError):
                llm.review(self.session, [], allow_execution=False)
            runner.assert_not_called()


if __name__ == '__main__':
    unittest.main()
