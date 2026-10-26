'use strict';
const $ = id => document.getElementById(id);
let config = null, session = null, report = null, busy = false;
const states = {cumplido:'Cumplido', parcial:'Parcial', faltante:'Faltante', no_verificable:'No verificable'};
const kinds = {codigo:'Código', documentacion:'Documentación', prueba_escrita:'Prueba escrita', ejecucion:'Ejecución registrada', ninguna:'Sin evidencia suficiente'};
const caseNames = {valid_tac:'Entrada válida: genera TAC', lexical_blocks_tac:'Error léxico: bloquea TAC', syntax_blocks_tac:'Error sintáctico: bloquea TAC', semantic_blocks_tac:'Error semántico: bloquea TAC', multiple_errors:'Varios errores en una misma ejecución'};
function el(tag, text, className){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;}
function notice(text, error=false){$('notice').hidden=!text;$('notice').textContent=text;$('notice').className=error?'error':'';}
function refreshButtons(){
 document.querySelectorAll('button').forEach(b=>b.disabled=busy);
 document.querySelectorAll('.step').forEach(b=>b.disabled=busy||(b.dataset.step!=='1'&&!session)||(b.dataset.step==='3'&&!report));
 $('export').disabled=busy||!report;
 $('extract').disabled=busy||!session||!config?.model_configured;
 $('review').disabled=busy||!session||!config?.model_configured;
 $('run').disabled=busy||!session?.runner_compatible||!config?.runner?.available;
 $('clear').hidden=!session;
}
async function task(message, work){
 if(busy)return;
 busy=true;refreshButtons();notice(message);$('notice').className='busy';
 try{await work();}catch(error){notice(error.message||'No se pudo completar la operación.',true);}
 finally{busy=false;refreshButtons();}
}
async function api(path, data){
 const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),240000);
 try{
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Revisor-Token':config.token},body:JSON.stringify(data),signal:controller.signal});
  const value=await response.json();if(!response.ok)throw new Error(value.error||'La solicitud falló.');return value;
 }catch(error){if(error.name==='AbortError')throw new Error('Se agotó el tiempo de espera. La operación podría seguir en curso; espera antes de repetirla.');throw error;}
 finally{clearTimeout(timer);}
}
function showStep(step){
 document.querySelectorAll('.page').forEach(p=>p.hidden=p.id!==`step-${step}`);
 document.querySelectorAll('.step').forEach(b=>{b.classList.toggle('active',b.dataset.step===String(step));b.setAttribute('aria-current',b.dataset.step===String(step)?'step':'false');});
 document.querySelector('.execution').hidden=String(step)==='1'||!session;
 window.scrollTo({top:0,behavior:'smooth'});
}
function invalidateReport(){report=null;$('results').replaceChildren();$('metrics').replaceChildren();$('execution-results').replaceChildren();refreshButtons();}
function updateSession(value){
 session=value;invalidateReport();$('assignment-preview').textContent=value.assignment;
 $('coverage-count').textContent=`${value.documents.length} archivos seleccionados`;
 $('coverage-warnings').replaceChildren(...value.warnings.map(w=>el('p',w,'warning')));
 const list=$('file-list');list.replaceChildren();
 for(const d of value.documents){
  const wrapper=el('div');const row=el('div',undefined,'file-row');row.append(el('span',`${d.path} · ${d.lines} líneas${d.truncated?' · recortado':''}`));
  const button=el('button','Ver texto','text-button');button.addEventListener('click',()=>{pre.hidden=!pre.hidden;button.textContent=pre.hidden?'Ver texto':'Ocultar';});
  const pre=el('pre',d.text);pre.hidden=true;row.append(button);wrapper.append(row,pre);list.append(wrapper);
 }
 $('criteria').value=value.criteria_text||'';
 $('consent').checked=false;$('allow-execution').checked=false;
 $('allow-execution').disabled=!value.runner_compatible;
 $('runner-status').textContent=!value.runner_compatible?'Esta entrega no es compatible con el perfil de ejecución.':config.runner.reason;
 showStep(2);refreshButtons();
}
async function filePayload(file){
 if(!file)throw new Error('Selecciona tu entrega para continuar.');
 if(file.size>80*1024*1024)throw new Error('El archivo supera 80 MiB. Retira dependencias y vuelve a comprimirlo.');
 return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve({name:file.name,data:reader.result.split(',')[1]});reader.onerror=()=>reject(new Error('No se pudo leer el archivo.'));reader.readAsDataURL(file);});
}
function requireConsent(){if(!$('consent').checked)throw new Error('Confirma la autorización de envío al modelo antes de continuar.');}
function renderExecution(execution){
 const target=$('execution-results');target.replaceChildren();if(!execution)return;
 $('runner-status').textContent=execution.message||execution.status;
 for(const c of execution.cases||[]){const row=el('div',undefined,'execution-item');row.append(el('strong',caseNames[c.id]||c.id),el('span',c.passed?'Aprobó este caso':'Falló este caso',`badge ${c.passed?'cumplido':'faltante'}`));
 const details=el('details');details.append(el('summary','Entrada y resultado'),el('pre',JSON.stringify(c,null,2)));row.append(details);target.append(row);}
 if(execution.log){const details=el('details');details.append(el('summary','Detalle de ejecución'),el('pre',execution.log));target.append(details);}
}
function renderResults(){
 if(!report)return;
 const filter=$('filter').value,target=$('results');target.replaceChildren();
 let rows=report.results.filter(r=>filter==='all'||(filter==='pending'&&r.state!=='cumplido')||(filter==='restriccion'&&r.kind==='restriccion'));
 rows=[...rows].sort((a,b)=>(a.kind==='restriccion'?0:1)-(b.kind==='restriccion'?0:1));
 for(const r of rows){
  const card=el('article',undefined,`card result-card ${r.state}`);card.append(el('p',`${r.id} · ${r.kind==='restriccion'?'Restricción obligatoria':'Criterio de rúbrica'}`,'criterion-kind'));
  const heading=el('div',undefined,'criterion-header');heading.append(el('h3',r.text),el('span',states[r.state]||r.state,`badge ${r.state}`));card.append(heading,el('p',r.explanation,'muted'));
  card.append(el('p',`Evidencia: ${kinds[r.evidence_type]||r.evidence_type}`,'evidence-label'));
  if(r.evidence_type==='prueba_escrita')card.append(el('p','Una prueba escrita no demuestra que se haya ejecutado o aprobado.','status-description'));
  for(const evidence of r.evidence||[]){
   const details=el('details',undefined,'source-view');details.append(el('summary',`${evidence.path} · líneas ${evidence.line_start}–${evidence.line_end}`),el('pre',evidence.quote));card.append(details);
  }
  if(r.test_ids?.length)card.append(el('p',`Pruebas relacionadas: ${r.test_ids.map(i=>caseNames[i]||i).join('; ')}`,'muted'));
  const suggestion=el('div',undefined,'suggestion');suggestion.append(el('strong','Siguiente paso: '),document.createTextNode(r.suggestion));card.append(suggestion);
  if(r.needs_verification)card.append(el('p',`Por verificar: ${r.needs_verification}`,'muted'));
  for(const warning of r.warnings||[])card.append(el('p',warning,'warning'));
  target.append(card);
 }
 if(!rows.length)target.append(el('div','No hay criterios en este filtro.','empty'));
}
function renderReport(value){
 report=value;const m=value.metrics;const boxes=[
  [String(value.results.length),'Criterios revisados'],
  [String(value.results.filter(r=>r.state!=='cumplido').length),'Para revisar o verificar'],
  [`${m.duration_seconds}s`,'Tiempo total de revisión'],
  [m.estimated_cost_usd===null?'Sin precio configurado':`$${m.estimated_cost_usd.toFixed(4)}`,'Costo estimado · USD']];
 $('metrics').replaceChildren(...boxes.map(([v,label])=>{const d=el('div',undefined,'metric');d.append(el('strong',v),el('span',label));return d;}));
 $('report-notice').textContent=`${value.notice} Modelo: ${m.model}. Tokens: ${m.total_tokens}. Prompt: ${value.prompt_version}.`;
 renderResults();renderExecution(value.execution);showStep(3);notice('Revisión lista. Comprueba las evidencias antes de hacer cambios.');refreshButtons();
}
document.querySelectorAll('.step').forEach(b=>b.addEventListener('click',()=>showStep(b.dataset.step)));
for(const id of ['rubric','submission'])$(id).addEventListener('change',()=>{$(`${id}-name`).textContent=$(id).files[0]?.name||'Selecciona un archivo';});
$('prepare').addEventListener('click',()=>task('Preparando archivos y comprobando cobertura…',async()=>{
 const submission=await filePayload($('submission').files[0]);const rubric=$('rubric').files[0]?await filePayload($('rubric').files[0]):null;
 if(!$('instructions').value.trim()&&!rubric)throw new Error('Pega las instrucciones o adjunta una rúbrica.');
 const previous=session?.session_id;
 const value=await api('/api/ingest',{instructions:$('instructions').value,rubric,submission});
 if(previous)await api('/api/delete',{session_id:previous});
 updateSession(value);notice('Archivos preparados. Escribe los criterios o autoriza una propuesta de IA.');
}));
$('example').addEventListener('click',()=>task('Cargando el ejemplo real de Compiscript…',async()=>{
 const previous=session?.session_id,value=await api('/api/example',{});
 if(previous)await api('/api/delete',{session_id:previous});
 updateSession(value);notice('Ejemplo cargado con criterios preparados manualmente. Todavía no se ha llamado al LLM ni ejecutado código.');
}));
$('extract').addEventListener('click',()=>task('La IA está proponiendo criterios. Revisa su interpretación al terminar…',async()=>{
 requireConsent();const value=await api('/api/criteria',{session_id:session.session_id});
 $('criteria').value=value.criteria.map(c=>(c.kind==='restriccion'?'[R] ':'')+c.text).join('\n');invalidateReport();
 notice(`Propuesta lista: confirma o corrige los criterios. Esta llamada consumió ${value.metrics.total_tokens} tokens.`);
}));
$('criteria').addEventListener('input',invalidateReport);
$('review').addEventListener('click',()=>task('Revisando criterios y localizando evidencia. Puede tomar uno o dos minutos…',async()=>{
 requireConsent();if(!$('criteria').value.trim())throw new Error('Confirma al menos un criterio.');
 const value=await api('/api/review',{session_id:session.session_id,criteria_text:$('criteria').value,mode:$('mode').value,allow_execution:$('allow-execution').checked});renderReport(value);
}));
$('run').addEventListener('click',()=>task('Ejecutando cinco casos en el entorno aislado…',async()=>{
 const value=await api('/api/run',{session_id:session.session_id});renderExecution(value);
 notice(value.executed?'Pruebas terminadas. Vuelve a criterios y solicita otra revisión para incorporarlas.':value.message,!value.executed);
}));
$('edit').addEventListener('click',()=>showStep(2));$('filter').addEventListener('change',renderResults);
$('export').addEventListener('click',()=>{
 if(!report)return;const blob=new Blob([JSON.stringify({...report,exported_at:new Date().toISOString()},null,2)],{type:'application/json'});
 const url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download=`revision-${report.prompt_version.replace('.txt','')}-${Date.now()}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
$('clear').addEventListener('click',()=>task('Eliminando la revisión de esta sesión…',async()=>{
 await api('/api/delete',{session_id:session.session_id});session=null;invalidateReport();$('file-list').replaceChildren();$('assignment-preview').textContent='';$('criteria').value='';$('report-notice').textContent='';$('instructions').value='';
 for(const id of ['rubric','submission']){$(id).value='';$(`${id}-name`).textContent='Selecciona un archivo';}
 showStep(1);notice('Revisión eliminada de la aplicación. Esto no elimina archivos originales, descargas ni datos que ya se hayan enviado al proveedor.');
}));
fetch('/api/config').then(r=>{if(!r.ok)throw new Error();return r.json();}).then(value=>{
 config=value;$('connection-label').textContent=value.model_configured?`Modelo configurado: ${value.model}`:'Pendiente: configurar modelo';$('connection-dot').classList.toggle('ready',value.model_configured);refreshButtons();
}).catch(()=>notice('No se pudo conectar al servidor local. Abre la dirección indicada al ejecutar app.py.',true));
refreshButtons();
