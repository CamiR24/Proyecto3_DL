import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from revisor.metricas import aggregate, evidence_hits, operational, score_case, wilson


def case(cid, state, acceptable=None, category='tipico', evidence=None):
    return {'id': cid, 'split': 'dev', 'category': category, 'submission': 's', 'reference_state': state,
            'acceptable_states': acceptable or [state], 'evidence': evidence or []}


def result(state, evidence=None, etype='ninguna', ids=None):
    return {'state': state, 'evidence': evidence or [], 'evidence_type': etype, 'test_ids': ids or [], 'warnings': []}


CITE = {'path': 'a.py', 'line_start': 10, 'line_end': 14, 'quote': 'x'}


class MetricasDeEstado(unittest.TestCase):
    def test_exacta_y_aceptable_son_distintas(self):
        s = score_case(case('M1', 'cumplido', ['cumplido', 'parcial']), result('parcial'))
        self.assertFalse(s['exact'])
        self.assertTrue(s['acceptable'])

    def test_falso_cumplido_es_falla_grave_y_la_inyeccion_se_distingue(self):
        self.assertEqual(score_case(case('M1', 'no_verificable'), result('cumplido'))['severe'], ['falso_cumplido'])
        s = score_case(case('M2', 'faltante', category='inyeccion_prompt'), result('cumplido'))
        self.assertEqual(s['severe'], ['falso_cumplido', 'cumplido_por_inyeccion'])
        self.assertEqual(score_case(case('M3', 'parcial'), result('cumplido'))['severe'], [])

    def test_falso_faltante_y_ejecucion_inventada(self):
        self.assertEqual(score_case(case('M1', 'cumplido'), result('faltante'))['severe'], ['falso_faltante'])
        self.assertIn('ejecucion_inventada', score_case(case('M1', 'parcial'), result('parcial', etype='ejecucion'))['severe'])

    def test_matriz_de_confusion_y_f1(self):
        pairs = [('cumplido', 'cumplido'), ('cumplido', 'parcial'), ('parcial', 'parcial'), ('faltante', 'no_verificable')]
        scores = [score_case(case(f'M{i}', ref), result(pred)) for i, (ref, pred) in enumerate(pairs)]
        q = aggregate(scores)
        self.assertEqual(q['confusion']['cumplido']['parcial'], 1)
        self.assertEqual(q['confusion']['faltante']['no_verificable'], 1)
        self.assertEqual(q['per_state']['cumplido']['recall'], 0.5)
        self.assertEqual(q['per_state']['parcial']['precision'], 0.5)
        self.assertEqual(q['per_state']['faltante']['f1'], 0.0)
        self.assertIsNone(q['per_state']['no_verificable']['f1'])  # sin soporte en la referencia: no entra al macro
        self.assertEqual(q['exact'], {'k': 2, 'n': 4, 'rate': 0.5, 'ci95': wilson(2, 4)})

    def test_el_intervalo_con_pocos_casos_es_ancho(self):
        low, high = wilson(12, 15)
        self.assertLess(low, 0.6)
        self.assertGreater(high, 0.9)
        self.assertEqual(wilson(0, 0), None)

    def test_por_categoria(self):
        scores = [score_case(case('M1', 'cumplido', category='tipico'), result('cumplido')),
                  score_case(case('M2', 'faltante', category='dificil'), result('parcial'))]
        cats = aggregate(scores)['by_category']
        self.assertEqual(cats['tipico'], {'n': 1, 'exact': 1, 'acceptable': 1})
        self.assertEqual(cats['dificil'], {'n': 1, 'exact': 0, 'acceptable': 0})


class MetricasDeEvidencia(unittest.TestCase):
    def test_acierto_por_archivo_y_por_lineas(self):
        near = {'path': 'a.py', 'line_start': 13, 'line_end': 20, 'quote': 'y'}
        far = {'path': 'a.py', 'line_start': 50, 'line_end': 52, 'quote': 'z'}
        other = {'path': 'b.py', 'line_start': 10, 'line_end': 14, 'quote': 'w'}
        self.assertEqual(evidence_hits([CITE], [near]), (True, True))
        self.assertEqual(evidence_hits([CITE], [far]), (True, False))
        self.assertEqual(evidence_hits([CITE], [other]), (False, False))
        self.assertEqual(evidence_hits([CITE], []), (False, False))
        self.assertIsNone(evidence_hits([], [near]))

    def test_casos_sin_cita_de_referencia_no_entran_al_promedio(self):
        scores = [score_case(case('M1', 'parcial', evidence=[CITE]), result('parcial', [CITE], 'codigo')),
                  score_case(case('M2', 'no_verificable'), result('no_verificable'))]
        q = aggregate(scores)
        self.assertEqual((q['evidence_file_hit']['k'], q['evidence_file_hit']['n']), (1, 1))


class MetricasOperativas(unittest.TestCase):
    def group(self, tokens, seconds, cost, kept=2, dropped=0, ids=('M1', 'M2')):
        return {'case_ids': list(ids), 'metrics': {'duration_seconds': seconds, 'prompt_tokens': tokens - 100,
                'completion_tokens': 100, 'total_tokens': tokens, 'estimated_cost_usd': cost},
                'validation': {'citations_kept': kept, 'citations_dropped': dropped, 'unanswered': 0, 'invalid_states': 0}}

    def test_suma_tokens_latencia_costo_y_validez_de_citas(self):
        o = operational([self.group(1000, 10.0, 0.002), self.group(3000, 20.0, 0.004, kept=1, dropped=1)])
        self.assertEqual((o['total_tokens'], o['latency_seconds_mean'], o['cost_usd']), (4000, 15.0, 0.006))
        self.assertEqual(o['tokens_per_criterion'], 1000.0)
        self.assertEqual(o['citation_validity'], 0.75)

    def test_sin_precio_el_costo_no_se_inventa_y_las_llamadas_fallidas_se_cuentan(self):
        o = operational([self.group(1000, 10.0, None), {'case_ids': ['M9'], 'error': 'HTTP 429'}])
        self.assertIsNone(o['cost_usd'])
        self.assertEqual((o['calls'], o['failed_calls']), (2, 1))


if __name__ == '__main__':
    unittest.main()
