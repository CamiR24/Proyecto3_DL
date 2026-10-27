'use strict';
/* Espera, resultados, incertidumbre y acciones sobre la revisión. Se carga después de app.js y usa
   $, el, notice, report, session y caseNames de ese archivo. Las funciones puras no dependen del DOM. */
const STATE_ORDER = ['faltante', 'parcial', 'no_verificable', 'cumplido'];
const STATE_NAME = {cumplido: 'Cumplido', parcial: 'Parcial', faltante: 'Faltante', no_verificable: 'No verificable'};
const STATE_HELP = {
 cumplido: 'Hay evidencia suficiente para el alcance del criterio.',
 parcial: 'Hay avance demostrado, pero falta una parte.',
 faltante: 'No hay rastro del requisito en una entrega revisada por completo.',
 no_verificable: 'La evidencia enviada no basta para concluir. No significa que el requisito falte.'};
const EVIDENCE_TYPES = ['codigo', 'documentacion', 'prueba_escrita', 'ejecucion', 'ninguna'];
const EVIDENCE_NAME = {codigo: 'Código', documentacion: 'Documentación', prueba_escrita: 'Prueba escrita',
 ejecucion: 'Ejecución registrada', ninguna: 'Sin evidencia suficiente'};
const LONG_WAIT = [
 [60, 'Sigue en curso. Las revisiones con muchos criterios o archivos pueden tardar más.'],
 [150, 'Está tardando más de lo habitual. La espera se corta a los 4 minutos; si eso pasa, espera un poco antes de repetir porque el servidor puede seguir trabajando.']];
let reviewed = new Set(), stateFilter = 'all', onlyRestrictions = false, clock = null;

/* ---------- funciones puras ---------- */
function formatClock(seconds) {
 return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}
function asText(value, fallback = '') {
 return typeof value === 'string' ? value : fallback;
}
function oneLine(value) {
 return String(value).replace(/\s+/g, ' ').trim();
}
function safeResult(r) {
 // Defensa de la interfaz: un resultado incompleto no debe romper la pantalla.
 r = r && typeof r === 'object' ? r : {};
 return {id: asText(r.id), text: asText(r.text, '(criterio sin texto)'), kind: r.kind === 'restriccion' ? 'restriccion' : 'rubrica',
  state: STATE_ORDER.includes(r.state) ? r.state : 'no_verificable',
  evidence_type: EVIDENCE_TYPES.includes(r.evidence_type) ? r.evidence_type : 'ninguna',
  explanation: asText(r.explanation), suggestion: asText(r.suggestion), needs_verification: asText(r.needs_verification),
  evidence: Array.isArray(r.evidence) ? r.evidence.filter(e => e && typeof e === 'object') : [],
  test_ids: Array.isArray(r.test_ids) ? r.test_ids.map(String) : [],
  warnings: Array.isArray(r.warnings) ? r.warnings.map(String) : []};
}
/* Respaldo: lo calcula la aplicación con las citas verificadas. No es una probabilidad del modelo. */
function supportOf(r) {
 const n = r.evidence.length;
 if (r.evidence_type === 'ejecucion' && r.test_ids.length)
  return {level: 3, label: 'Respaldo alto', detail: `Ejecución registrada de ${r.test_ids.length} prueba(s). Solo cubre lo que esas pruebas comprueban.`};
 if (n && r.evidence_type === 'codigo')
  return {level: 2, label: 'Respaldo medio', detail: `${n} cita(s) de código verificadas en tus archivos. Leer el código no prueba que funcione.`};
 if (n)
  return {level: 1, label: 'Respaldo bajo', detail: 'Solo documentación o pruebas escritas: son declaraciones, no demuestran funcionamiento.'};
 return {level: 0, label: 'Sin respaldo', detail: 'No hay citas verificadas para esta conclusión.'};
}
function countStates(rows) {
 return Object.fromEntries(STATE_ORDER.map(s => [s, rows.filter(r => r.state === s).length]));
}
function sortByPriority(rows) {
 const rank = r => STATE_ORDER.indexOf(r.state);
 return [...rows].sort((a, b) => rank(a) - rank(b) || (a.kind === 'restriccion' ? 0 : 1) - (b.kind === 'restriccion' ? 0 : 1));
}
function citationLabel(e) {
 return `${asText(e.path, '(archivo)')}:${e.line_start}-${e.line_end}`;
}
function errorHint(message) {
 if (/HTTP (401|403)/.test(message)) return 'Revisa LLM_API_KEY y LLM_MODEL en .env y reinicia app.py.';
 if (/HTTP 429/.test(message)) return 'Límite de uso o saldo del proveedor: espera un momento antes de reintentar.';
 if (/HTTP 5\d\d/.test(message)) return 'El proveedor tuvo un problema temporal; reintentar suele funcionar.';
 if (/JSON/.test(message)) return 'El modelo no devolvió un formato utilizable. Reintentar suele funcionar; si se repite, reduce el número de criterios.';
 if (/tiempo/.test(message)) return 'Espera un poco antes de repetir: la operación anterior puede seguir en curso.';
 return '';
}
/* Lista de pendientes en Markdown: lo que el usuario puede llevarse y marcar. */
function pendingMarkdown(rep, done = new Set()) {
 const rows = sortByPriority((rep.results || []).map(safeResult));
 const m = rep.metrics || {};
 const out = ['# Pendientes antes de entregar', '',
  `Revisión orientativa${m.model ? ` generada con ${m.model}` : ''}${rep.prompt_version ? ` (prompt ${rep.prompt_version})` : ''}. ` +
  'Es una segunda mirada, no una calificación: comprueba cada cita en tus archivos.', ''];
 const groups = [['faltante', 'Corregir: no se encontró el requisito'], ['parcial', 'Completar: hay avance, falta una parte'],
  ['no_verificable', 'Verificar: la evidencia enviada no alcanza']];
 for (const [state, title] of groups) {
  const items = rows.filter(r => r.state === state);
  if (!items.length) continue;
  out.push(`## ${title} (${items.length})`, '');
  for (const r of items) {
   out.push(`- [${done.has(r.id) ? 'x' : ' '}] ${r.kind === 'restriccion' ? '**[Restricción]** ' : ''}${oneLine(r.text)}`);
   if (r.suggestion) out.push(`  - Siguiente paso: ${oneLine(r.suggestion)}`);
   if (r.needs_verification) out.push(`  - Por verificar: ${oneLine(r.needs_verification)}`);
   for (const e of r.evidence) out.push(`  - Evidencia: \`${citationLabel(e)}\``);
  }
  out.push('');
 }
 const ok = rows.filter(r => r.state === 'cumplido').length;
 out.push(rows.length === ok ? 'No hay pendientes.' : `${ok} criterio(s) cumplido(s) no se incluyen en esta lista.`);
 return out.join('\n') + '\n';
}

/* ---------- espera y errores ---------- */
function progressStart(info) {
 progressStop();
 $('notice').hidden = true;
 $('progress-title').textContent = info.title;
 $('progress-detail').textContent = info.detail || '';
 $('progress-steps').replaceChildren(...info.steps.map(s => el('li', s)));
 $('progress-long').hidden = true;
 $('progress').hidden = false;
 const started = Date.now();
 const tick = () => {
  const seconds = Math.floor((Date.now() - started) / 1000);
  $('progress-time').textContent = formatClock(seconds);
  const late = [...LONG_WAIT].reverse().find(([after]) => seconds >= after);
  if (late && $('progress-long').textContent !== late[1]) {$('progress-long').textContent = late[1]; $('progress-long').hidden = false;}
 };
 tick();
 clock = setInterval(tick, 1000);
 const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
 $('progress').scrollIntoView({behavior: calm ? 'auto' : 'smooth', block: 'center'});
}
function progressStop() {
 clearInterval(clock);
 clock = null;
 $('progress').hidden = true;
}
function reviewProgressInfo() {
 const criteria = $('criteria').value.split('\n').filter(l => l.trim()).length;
 const baseline = $('mode').value === 'baseline', tools = $('allow-execution').checked && !baseline;
 return {title: 'Revisando tu entrega',
  detail: `${session?.documents.length || 0} archivos · ${criteria} criterios · ${baseline ? 'Baseline' : 'Revisión con evidencia'}${tools ? ' · con pruebas en Docker' : ''}`,
  steps: ['Enviamos al modelo las instrucciones, los criterios y el texto seleccionado.',
   ...(tools ? ['Si el modelo lo pide, se ejecutan las cinco pruebas aisladas y se le entregan sus resultados.'] : []),
   'El modelo evalúa cada criterio y cita evidencia.',
   'Comprobamos cada cita contra tus archivos y descartamos las que no coinciden.']};
}
function criteriaProgressInfo() {
 return {title: 'Proponiendo criterios', detail: 'Revisarás y corregirás la propuesta antes de continuar.',
  steps: ['Enviamos al modelo las instrucciones y la rúbrica.', 'El modelo extrae los requisitos explícitos y distingue restricciones.']};
}
function runProgressInfo() {
 return {title: 'Ejecutando cinco pruebas', detail: 'En un contenedor sin red y con límites de tiempo y memoria.',
  steps: ['Se arranca el contenedor con el perfil fijo.', 'Se corren los cinco casos, cada uno con su propio límite.', 'Se recogen los resultados.']};
}
function showError(error, retry) {
 const message = error?.message || 'No se pudo completar la operación.';
 const box = $('notice');
 box.hidden = false;
 box.className = 'error';
 box.replaceChildren(el('strong', message));
 const hint = errorHint(message);
 if (hint) box.append(el('p', hint, 'error-hint'));
 if (retry) {
  const again = el('button', 'Reintentar', 'secondary');
  again.addEventListener('click', retry);
  box.append(again);
 }
 box.scrollIntoView({block: 'nearest'});
}

/* ---------- resultados ---------- */
function copyText(value, button, done = 'Copiado ✓') {
 const original = button.textContent;
 const flash = label => {button.textContent = label; setTimeout(() => {button.textContent = original;}, 1600);};
 (navigator.clipboard?.writeText(value) || Promise.reject()).then(() => flash(done), () => flash('No se pudo copiar'));
}
function downloadText(name, value, type) {
 const url = URL.createObjectURL(new Blob([value], {type}));
 const link = el('a');
 link.href = url;
 link.download = name;
 link.click();
 setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function supportMeter(r) {
 const s = supportOf(r), box = el('div', undefined, `support level-${s.level}`);
 const dots = el('span', undefined, 'dots');
 dots.setAttribute('aria-hidden', 'true');
 for (let i = 1; i <= 3; i++) dots.append(el('i', undefined, i <= s.level ? 'on' : ''));
 const label = el('span');
 label.append(el('strong', s.label), document.createTextNode(` · ${s.detail}`));
 box.append(dots, label);
 return box;
}
function citationView(e) {
 const details = el('details', undefined, 'source-view');
 const summary = el('summary', citationLabel(e));
 const copy = el('button', 'Copiar referencia', 'text-button copy-ref');
 copy.addEventListener('click', ev => {ev.preventDefault(); copyText(citationLabel(e), copy);});
 summary.append(copy);
 details.append(summary, el('pre', asText(e.quote)));
 return details;
}
function resultCard(r) {
 const card = el('article', undefined, `card result-card ${r.state}${reviewed.has(r.id) ? ' reviewed' : ''}`);
 card.dataset.id = r.id;
 card.append(el('p', `${r.id} · ${r.kind === 'restriccion' ? 'Restricción obligatoria' : 'Criterio de rúbrica'}`, 'criterion-kind'));
 const head = el('div', undefined, 'criterion-header');
 head.append(el('h3', r.text), el('span', STATE_NAME[r.state], `badge ${r.state}`));
 card.append(head, el('p', STATE_HELP[r.state], 'state-help'));
 if (r.explanation) card.append(el('p', r.explanation, 'muted'));
 card.append(supportMeter(r));
 if (r.evidence_type !== 'ninguna') card.append(el('p', `Evidencia: ${EVIDENCE_NAME[r.evidence_type]}`, 'evidence-label'));
 if (r.evidence_type === 'prueba_escrita') card.append(el('p', 'Una prueba escrita no demuestra que se haya ejecutado o aprobado.', 'status-description'));
 r.evidence.forEach(e => card.append(citationView(e)));
 if (r.test_ids.length) card.append(el('p', `Pruebas relacionadas: ${r.test_ids.map(i => caseNames[i] || i).join('; ')}`, 'muted'));
 if (r.state === 'no_verificable' || (r.state === 'parcial' && r.needs_verification)) {
  const gap = el('div', undefined, 'gap');
  gap.append(el('strong', 'Qué falta para estar seguros: '), document.createTextNode(r.needs_verification ||
   'No hay evidencia suficiente en lo que se envió. Añade o señala los archivos relevantes, o compruébalo tú.'));
  card.append(gap);
 } else if (r.needs_verification) card.append(el('p', `Por verificar: ${r.needs_verification}`, 'muted'));
 r.warnings.forEach(w => card.append(el('p', w, 'warning')));
 if (r.suggestion) {
  const suggestion = el('div', undefined, 'suggestion');
  suggestion.append(el('strong', 'Siguiente paso: '), document.createTextNode(r.suggestion));
  card.append(suggestion);
 }
 const actions = el('div', undefined, 'card-actions');
 const check = el('label', undefined, 'check done-check'), box = el('input');
 box.type = 'checkbox';
 box.checked = reviewed.has(r.id);
 box.addEventListener('change', () => {
  box.checked ? reviewed.add(r.id) : reviewed.delete(r.id);
  card.classList.toggle('reviewed', box.checked);
  updateReviewProgress();
 });
 check.append(box, el('span', 'Ya lo revisé'));
 actions.append(check);
 if (r.suggestion) {
  const copy = el('button', 'Copiar siguiente paso', 'text-button');
  copy.addEventListener('click', () => copyText(r.suggestion, copy));
  actions.append(copy);
 }
 card.append(actions);
 return card;
}
function pendingRows() {
 return report ? report.results.map(safeResult).filter(r => r.state !== 'cumplido') : [];
}
function updateReviewProgress() {
 const pending = pendingRows();
 $('review-progress').textContent = pending.length ? `Revisados ${pending.filter(r => reviewed.has(r.id)).length} de ${pending.length} pendientes` : 'Sin pendientes';
}
function renderSummary(rows) {
 const counts = countStates(rows), bar = $('state-bar');
 bar.setAttribute('aria-label', STATE_ORDER.filter(s => counts[s]).map(s => `${counts[s]} ${STATE_NAME[s].toLowerCase()}`).join(', '));
 bar.replaceChildren(...STATE_ORDER.filter(s => counts[s]).map(s => {
  const part = el('span', undefined, `part ${s}`);
  part.style.flexGrow = counts[s];
  return part;
 }));
 const chips = [['all', 'Todos', rows.length], ...STATE_ORDER.filter(s => counts[s]).map(s => [s, STATE_NAME[s], counts[s]])];
 $('state-chips').replaceChildren(...chips.map(([key, label, count]) => {
  const chip = el('button', `${label} · ${count}`, `chip ${key}`);
  chip.type = 'button';
  chip.setAttribute('aria-pressed', String(stateFilter === key));
  chip.addEventListener('click', () => {stateFilter = key; renderResults();});
  return chip;
 }));
}
function renderResults() {
 if (!report) return;
 const all = report.results.map(safeResult);
 if (stateFilter !== 'all' && !all.some(r => r.state === stateFilter)) stateFilter = 'all';
 renderSummary(all);
 const rows = sortByPriority(all.filter(r => (stateFilter === 'all' || r.state === stateFilter) && (!onlyRestrictions || r.kind === 'restriccion')));
 const target = $('results');
 target.replaceChildren(...rows.map(resultCard));
 if (!rows.length) target.append(el('div', 'No hay criterios con este filtro.', 'empty'));
 updateReviewProgress();
}
function renderBanners(value) {
 const coverage = $('coverage-banner'), warnings = value.coverage?.warnings || [];
 coverage.replaceChildren();
 coverage.hidden = !warnings.length;
 if (warnings.length) {
  coverage.append(el('strong', `La revisión cubre ${value.coverage.files} archivo(s) y no toda la entrega.`),
   ...warnings.map(w => el('p', w)),
   el('p', 'Por eso «Faltante» no se usa: lo que no aparece en estos archivos queda como «No verificable».'));
 }
 const v = value.validation, format = $('validation-banner');
 format.replaceChildren();
 const issues = v ? v.unanswered + v.invalid_states + v.citations_dropped : 0;
 format.hidden = !issues;
 if (issues) {
  format.append(el('strong', 'El modelo devolvió datos que hubo que corregir.'));
  if (v.unanswered) format.append(el('p', `${v.unanswered} criterio(s) sin evaluación: se marcaron como no verificables.`));
  if (v.invalid_states) format.append(el('p', `${v.invalid_states} estado(s) desconocido(s): se marcaron como no verificables.`));
  if (v.citations_dropped) format.append(el('p', `${v.citations_dropped} cita(s) se descartaron porque no coinciden con tus archivos; se conservaron ${v.citations_kept}.`));
 }
}
function renderExecution(execution) {
 const target = $('execution-results');
 target.replaceChildren();
 if (!execution) return;
 $('runner-status').textContent = execution.message || execution.status;
 const cases = execution.cases || [];
 if (execution.executed && cases.length) {
  const passed = cases.filter(c => c.passed).length;
  target.append(el('p', `${passed} de ${cases.length} casos aprobaron. Un caso aprobado solo respalda lo que ese caso comprueba, no todo el criterio.`, 'muted'));
 }
 for (const c of cases) {
  const row = el('div', undefined, 'execution-item');
  row.append(el('strong', caseNames[c.id] || c.id), el('span', c.passed ? 'Aprobó este caso' : 'Falló este caso', `badge ${c.passed ? 'cumplido' : 'faltante'}`));
  const details = el('details');
  details.append(el('summary', 'Entrada y resultado'), el('pre', JSON.stringify(c, null, 2)));
  row.append(details);
  target.append(row);
 }
 if (execution.log) {
  const details = el('details');
  details.append(el('summary', 'Detalle de ejecución'), el('pre', execution.log));
  target.append(details);
 }
}
function resetResultsView() {
 reviewed = new Set();
 stateFilter = 'all';
 for (const id of ['state-chips', 'state-bar', 'coverage-banner', 'validation-banner']) $(id).replaceChildren();
 $('coverage-banner').hidden = $('validation-banner').hidden = true;
 $('review-progress').textContent = '';
}
function renderReport(value) {
 report = value;
 reviewed = new Set();
 stateFilter = 'all';
 const m = value.metrics || {}, rows = value.results.map(safeResult), pending = rows.filter(r => r.state !== 'cumplido').length;
 const boxes = [[String(rows.length), 'Criterios revisados'], [String(pending), 'Para revisar o verificar'],
  [m.duration_seconds === undefined ? '—' : `${m.duration_seconds}s`, 'Tiempo total de revisión'],
  [m.estimated_cost_usd == null ? 'Sin precio configurado' : `$${m.estimated_cost_usd.toFixed(4)}`, 'Costo estimado · USD']];
 $('metrics').replaceChildren(...boxes.map(([v, label]) => {const d = el('div', undefined, 'metric'); d.append(el('strong', v), el('span', label)); return d;}));
 $('report-notice').textContent = `${value.notice} Modelo: ${m.model}. Tokens: ${m.total_tokens}. Prompt: ${value.prompt_version}.`;
 renderBanners(value);
 renderResults();
 renderExecution(value.execution);
 showStep(3);
 $('step-3-title').focus({preventScroll: true});
 notice(pending ? `Revisión lista: ${pending} de ${rows.length} criterios necesitan atención. Comprueba las evidencias antes de hacer cambios.` : 'Revisión lista: ningún criterio quedó pendiente. Aun así, comprueba las evidencias.');
 refreshButtons();
}

$('only-restrictions').addEventListener('change', event => {onlyRestrictions = event.target.checked; renderResults();});
$('copy-pending').addEventListener('click', event => {if (report) copyText(pendingMarkdown(report, reviewed), event.currentTarget, 'Lista copiada ✓');});
$('download-pending').addEventListener('click', () => {if (report) downloadText(`pendientes-${Date.now()}.md`, pendingMarkdown(report, reviewed), 'text/markdown');});
$('expand-all').addEventListener('click', event => {
 const open = event.currentTarget.dataset.open !== '1';
 document.querySelectorAll('#results .source-view').forEach(d => {d.open = open;});
 event.currentTarget.dataset.open = open ? '1' : '0';
 event.currentTarget.textContent = open ? 'Contraer evidencias' : 'Expandir evidencias';
});
