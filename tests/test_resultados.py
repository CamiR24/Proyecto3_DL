"""Validación del formato de salida del modelo y lógica pura de web/resultados.js."""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from revisor.llm import manual_criteria, normalize_review, validation_summary

ROOT = Path(__file__).resolve().parents[1]
DOCS = [{'path': 'compiler.py', 'text': 'if not errors:\n    generate_tac()\n', 'truncated': False}]
GOOD = {'path': 'compiler.py', 'line_start': 1, 'line_end': 2, 'quote': 'if not errors:\n    generate_tac()'}


class ValidacionDeSalida(unittest.TestCase):
    def setUp(self):
        self.criteria = manual_criteria('Uno\nDos\nTres')

    def run_review(self, rows):
        return normalize_review({'results': rows}, self.criteria, DOCS, None)

    def test_criterio_sin_respuesta_se_marca_y_se_cuenta(self):
        results = self.run_review([{'criterion_id': 'C01', 'state': 'parcial', 'evidence_type': 'codigo', 'evidence': [GOOD]}])
        self.assertEqual([r['answered'] for r in results], [True, False, False])
        self.assertTrue(any('no devolvió una evaluación' in w for w in results[1]['warnings']))
        self.assertEqual(results[1]['state'], 'no_verificable')
        self.assertEqual(validation_summary(results)['unanswered'], 2)

    def test_estado_desconocido_se_corrige_y_se_avisa(self):
        results = self.run_review([{'criterion_id': 'C01', 'state': 'aprobado'}])
        self.assertTrue(results[0]['invalid_state'])
        self.assertEqual(results[0]['state'], 'no_verificable')
        self.assertTrue(any('estado desconocido' in w for w in results[0]['warnings']))
        self.assertEqual(validation_summary(results)['invalid_states'], 1)

    def test_citas_descartadas_se_cuentan_y_no_se_ocultan(self):
        fake = {**GOOD, 'quote': 'codigo inventado'}
        results = self.run_review([{'criterion_id': 'C01', 'state': 'parcial', 'evidence_type': 'codigo', 'evidence': [GOOD, fake, 'texto']}])
        self.assertEqual(results[0]['citations_dropped'], 2)
        self.assertEqual(len(results[0]['evidence']), 1)
        self.assertTrue(any('2 cita(s)' in w for w in results[0]['warnings']))
        summary = validation_summary(results)
        self.assertEqual((summary['citations_kept'], summary['citations_dropped']), (1, 2))

    def test_respuesta_correcta_no_genera_avisos_de_formato(self):
        results = self.run_review([{'criterion_id': f'C0{i}', 'state': 'parcial', 'evidence_type': 'codigo', 'evidence': [GOOD]} for i in (1, 2, 3)])
        self.assertEqual(sum(len(r['warnings']) for r in results), 0)
        self.assertEqual(validation_summary(results), {'criteria': 3, 'unanswered': 0, 'invalid_states': 0,
                                                      'citations_kept': 3, 'citations_dropped': 0})


NODE = shutil.which('node')
SCRIPT = r"""
const fs = require('fs'), vm = require('vm');
const ctx = vm.createContext({});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8').split('/* ---------- espera y errores')[0], ctx);
const out = vm.runInContext(process.argv[2], ctx);
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(NODE, 'Node no está instalado; se omiten las pruebas de resultados.js')
class LogicaDeResultados(unittest.TestCase):
    def js(self, expression):
        done = subprocess.run([NODE, '-e', SCRIPT, str(ROOT / 'web/resultados.js'), expression],
                              capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_respaldo_depende_de_citas_verificadas_no_de_la_confianza_del_modelo(self):
        niveles = self.js("""[
          supportOf(safeResult({evidence_type:'ejecucion',test_ids:['a'],evidence:[]})).level,
          supportOf(safeResult({evidence_type:'codigo',evidence:[{path:'a',line_start:1,line_end:1,quote:'x'}]})).level,
          supportOf(safeResult({evidence_type:'documentacion',evidence:[{path:'a',line_start:1,line_end:1,quote:'x'}]})).level,
          supportOf(safeResult({evidence_type:'codigo',evidence:[]})).level]""")
        self.assertEqual(niveles, [3, 2, 1, 0])

    def test_resultado_incompleto_no_rompe_la_pantalla(self):
        r = self.js("safeResult({state:'inventado', evidence:'no es lista', warnings:null})")
        self.assertEqual((r['state'], r['evidence'], r['warnings'], r['evidence_type']), ('no_verificable', [], [], 'ninguna'))
        self.assertEqual(self.js('safeResult(null).kind'), 'rubrica')

    def test_prioridad_pone_primero_lo_que_hay_que_corregir_y_las_restricciones(self):
        orden = self.js("""sortByPriority([
          {id:'a',state:'cumplido',kind:'restriccion'},{id:'b',state:'parcial',kind:'rubrica'},
          {id:'c',state:'faltante',kind:'rubrica'},{id:'d',state:'faltante',kind:'restriccion'},
          {id:'e',state:'no_verificable',kind:'rubrica'}]).map(r=>r.id)""")
        self.assertEqual(orden, ['d', 'c', 'b', 'e', 'a'])

    def test_markdown_de_pendientes_agrupa_marca_revisados_y_omite_cumplidos(self):
        md = self.js("""pendingMarkdown({metrics:{model:'m'},prompt_version:'v',results:[
          {id:'C01',text:'Usar  ANTLR',kind:'restriccion',state:'faltante',suggestion:'Agregar generador',evidence:[]},
          {id:'C02',text:'Reciclar temporales',kind:'rubrica',state:'parcial',suggestion:'Liberar',needs_verification:'Ver gen_core',
           evidence:[{path:'emitter.py',line_start:56,line_end:67,quote:'x'}]},
          {id:'C03',text:'Interfaz',kind:'rubrica',state:'no_verificable',suggestion:'Probar',evidence:[]},
          {id:'C04',text:'Hecho',kind:'rubrica',state:'cumplido',evidence:[]}]}, new Set(['C02']))""")
        self.assertIn('## Corregir: no se encontró el requisito (1)', md)
        self.assertIn('- [ ] **[Restricción]** Usar ANTLR', md)
        self.assertIn('- [x] Reciclar temporales', md)
        self.assertIn('`emitter.py:56-67`', md)
        self.assertIn('1 criterio(s) cumplido(s) no se incluyen', md)
        self.assertNotIn('Hecho', md)

    def test_sin_pendientes_lo_dice(self):
        md = self.js("pendingMarkdown({results:[{id:'C01',text:'x',state:'cumplido',evidence:[]}]})")
        self.assertIn('No hay pendientes.', md)

    def test_pistas_de_error_segun_el_proveedor(self):
        self.assertIn('LLM_API_KEY', self.js("errorHint('El proveedor devolvió HTTP 401. Revisa')"))
        self.assertIn('espera', self.js("errorHint('El proveedor devolvió HTTP 429.')"))
        self.assertEqual(self.js("errorHint('otro error')"), '')

    def test_reloj_de_espera(self):
        self.assertEqual(self.js("[formatClock(5), formatClock(65), formatClock(600)]"), ['0:05', '1:05', '10:00'])


if __name__ == '__main__':
    unittest.main()
