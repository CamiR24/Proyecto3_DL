import copy
import unittest
from pathlib import Path

from revisor.casos import ROOT, check_case, load_cases, load_manifest


class CasosEvaluacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_manifest()
        cls.cache = {}
        cls.cases = load_cases(ROOT / 'evaluacion/casos_marines.jsonl')

    def problems(self, case):
        return check_case(case, self.manifest, self.cache)

    def test_los_casos_de_marines_son_coherentes(self):
        for case in self.cases:
            self.assertEqual(self.problems(case), [], case['id'])

    def test_veinte_casos_con_ids_unicos_y_division_15_5(self):
        self.assertEqual(len(self.cases), 20)
        self.assertEqual(len({c['id'] for c in self.cases}), 20)
        self.assertEqual(sorted(c['split'] for c in self.cases).count('test'), 5)

    def test_los_casos_cubren_las_categorias_pedidas(self):
        found = {c['category'] for c in self.cases}
        self.assertTrue({'tipico', 'dificil', 'informacion_insuficiente', 'fuera_de_alcance', 'inyeccion_prompt'} <= found)

    def test_la_validacion_humana_tiene_identidad_coherente(self):
        # Permite avanzar la revisión humana sin que una prueba exija false para siempre.
        for path in sorted((ROOT / 'evaluacion').glob('casos_*.jsonl')):
            for case in load_cases(path):
                self.assertIs(type(case['human_validated']), bool, case['id'])
                if case['human_validated']:
                    reviewer = case['validated_by']
                    self.assertIsInstance(reviewer, str, case['id'])
                    self.assertTrue(reviewer.strip(), case['id'])
                    self.assertNotEqual(reviewer.strip().casefold(), case['author'].strip().casefold(), case['id'])
                else:
                    self.assertIsNone(case['validated_by'], case['id'])

    def test_detecta_cita_inexistente(self):
        case = copy.deepcopy(self.cases[0])
        case['evidence'][0]['quote'] = 'texto que no existe'
        self.assertTrue(any('no aparece' in p for p in self.problems(case)))

    def test_detecta_archivo_que_el_revisor_no_ve(self):
        case = copy.deepcopy(self.cases[0])
        case['evidence'][0]['path'] = 'otra/ruta.py'
        self.assertTrue(any('no ve' in p for p in self.problems(case)))

    def test_cumplido_exige_evidencia(self):
        case = copy.deepcopy(self.cases[0])
        case['evidence'], case['evidence_type'] = [], 'ninguna'
        self.assertTrue(any('exige al menos una cita' in p for p in self.problems(case)))

    def test_faltante_no_se_admite_con_cobertura_parcial(self):
        case = copy.deepcopy(self.cases[4])  # entrega con archivos omitidos
        case['reference_state'], case['acceptable_states'] = 'faltante', ['faltante']
        self.assertTrue(any('cobertura completa' in p for p in self.problems(case)))

    def test_estado_de_referencia_debe_estar_entre_los_aceptables(self):
        case = copy.deepcopy(self.cases[0])
        case['acceptable_states'] = ['parcial']
        self.assertTrue(self.problems(case))


if __name__ == '__main__':
    unittest.main()
