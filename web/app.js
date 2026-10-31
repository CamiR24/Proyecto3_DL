'use strict';
const $ = id => document.getElementById(id);
let config = null, session = null, report = null, busy = false;
const caseNames = {valid_tac:'Entrada válida: genera TAC', lexical_blocks_tac:'Error léxico: bloquea TAC', syntax_blocks_tac:'Error sintáctico: bloquea TAC', semantic_blocks_tac:'Error semántico: bloquea TAC', multiple_errors:'Varios errores en una misma ejecución'};
function el(tag, text, className){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;}
function notice(text, error=false){$('notice').hidden=!text;$('notice').textContent=text;$('notice').className=error?'error':'';}
function refreshButtons(){
 document.querySelectorAll('button').forEach(b=>b.disabled=busy);
 document.querySelectorAll('.step').forEach(b=>b.disabled=busy||(!['0','1'].includes(b.dataset.step)&&!session)||(b.dataset.step==='3'&&!report));
 $('export').disabled=busy||!report;
 $('copy-pending').disabled=$('download-pending').disabled=busy||!report;
 $('extract').disabled=busy||!session||!config?.model_configured;
 $('review').disabled=busy||!session||!config?.model_configured;
 $('run').disabled=busy||!session?.runner_compatible||!config?.runner?.available;
 $('clear').hidden=!session;
}
async function task(message, work, progress){
 // Con `progress` (ver resultados.js) se muestra el panel de espera; sin él, un aviso simple.
 if(busy)return;
 busy=true;refreshButtons();
 if(progress)progressStart(progress);else{notice(message);$('notice').className='busy';}
 try{await work();}catch(error){showError(error,progress&&(()=>task(message,work,progress)));}
 finally{busy=false;progressStop();refreshButtons();}
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
 document.querySelector('.execution').hidden=['0','1'].includes(String(step))||!session;
 const heading=$(String(step)==='0'?'home-title':`step-${step}-title`);
 if(heading)heading.focus({preventScroll:true});
 window.scrollTo({top:0,behavior:'smooth'});
}
function invalidateReport(){report=null;$('results').replaceChildren();$('metrics').replaceChildren();$('execution-results').replaceChildren();resetResultsView();refreshButtons();}
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
// renderReport, renderResults y renderExecution viven en resultados.js
$('start-review').addEventListener('click',()=>showStep(1));
$('home-link').addEventListener('click',event=>{event.preventDefault();if(!busy)showStep(0);});
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
$('extract').addEventListener('click',()=>{
 try{requireConsent();}catch(error){return showError(error);}
 task('La IA está proponiendo criterios. Revisa su interpretación al terminar…',async()=>{
  const value=await api('/api/criteria',{session_id:session.session_id});
  $('criteria').value=value.criteria.map(c=>(c.kind==='restriccion'?'[R] ':'')+c.text).join('\n');invalidateReport();
  notice(`Propuesta lista: confirma o corrige los criterios. Esta llamada consumió ${value.metrics.total_tokens} tokens.`);
 },criteriaProgressInfo());
});
$('criteria').addEventListener('input',invalidateReport);
$('review').addEventListener('click',()=>{
 try{requireConsent();if(!$('criteria').value.trim())throw new Error('Confirma al menos un criterio.');}catch(error){return showError(error);}
 task('Revisando criterios y localizando evidencia. Puede tomar uno o dos minutos…',async()=>{
  const value=await api('/api/review',{session_id:session.session_id,criteria_text:$('criteria').value,mode:$('mode').value,allow_execution:$('allow-execution').checked});renderReport(value);
 },reviewProgressInfo());
});
$('run').addEventListener('click',()=>task('Ejecutando cinco casos en el entorno aislado…',async()=>{
 const value=await api('/api/run',{session_id:session.session_id});renderExecution(value);
 notice(value.executed?'Pruebas terminadas. Vuelve a criterios y solicita otra revisión para incorporarlas.':value.message,!value.executed);
},runProgressInfo()));
$('edit').addEventListener('click',()=>showStep(2));
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
