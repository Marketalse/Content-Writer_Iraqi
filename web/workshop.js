'use strict';
const $=s=>document.querySelector(s);
let current=null,active=null,polling=0,retryRequest=null;
const labels={comedy:'Comedy / Skit · موقف خفيف',why:'Explainer / Why · شرح فكرة',hot_take:'Hot take · رأي مباشر',howto:'How-to / Checklist · شلون تسويها',mistake:'Mistake / Correction · غلطة وتصحيح',problem:'Problem / Solution · مشكلة وحل',insight:'Single insight · فكرة واحدة',experiment:'Storytelling / Experiment · حكاية أو تجربة'};
function text(el,value){el.textContent=value||'';}
function showError(message){text($('#error'),message);$('#error').hidden=!message;}
function toast(message){text($('#toast'),message);$('#toast').hidden=false;setTimeout(()=>$('#toast').hidden=true,2500);}
async function api(path,options={}){
 let response;
 try{response=await fetch('/api/'+path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});}catch(e){throw new Error('Connection interrupted. Your request may still be running. Reopen My drafts before starting again.');}
 let body;
 try{body=await response.json();}catch(e){throw new Error('The writing service is starting or unavailable. Please wait a moment and try again.');}
 if(response.status===401){$('#login-cover').hidden=false;throw new Error(body.message||'Please sign in.');}
 if(!response.ok)throw new Error(body.message||'The request could not be completed.');
 return body;
}
function view(name){
 for(const section of document.querySelectorAll('.view'))section.hidden=section.id!=='view-'+name;
 for(const button of document.querySelectorAll('.nav'))button.classList.toggle('on',button.dataset.view===name);
 text($('#breadcrumb'),name.toUpperCase());showError('');
 if(name==='library')loadLibrary().catch(e=>showError(e.message));
 if(name==='progress')loadMilestones().catch(e=>showError(e.message));
}
function busy(value){
 $('#generate').disabled=value;$('#edit-submit').disabled=value;
 $('#working').hidden=!value;
 for(const button of $('#suggestion-list').querySelectorAll('button'))button.disabled=value;
}
function setJob(job){
 current=job;const r=job.result||{};const running=['queued','running'].includes(job.state);
 busy(running);$('#result').hidden=running; if(running)return;
 $('#topic').value=job.topic;$('#strategy').value=job.strategy_id;summary();
 const approved=job.state==='accepted'&&Boolean(r.copy);
 text($('#result-badge'),job.state==='accepted'&&window.workshopDemo?'Sample output':({accepted:'Reviewed script',blocked:'Not delivered',needs_review:'Quality target not reached',clarification:'One detail needed',error:'Request interrupted',interrupted:'Interrupted — no approved result'}[job.state]||job.state));
 text($('#result-message'),r.message);text($('#script'),approved?r.copy:'');$('#script').hidden=!approved;$('#copy').hidden=!approved;$('#edit-form').hidden=!approved;$('#clarify-form').hidden=job.state!=='clarification';
 text($('#request-ref'),'Request '+job.id);text($('#result-score'),r.score==null?'':`Quality ${r.score}/10`);
 $('#result-notices').replaceChildren();for(const value of r.notices||[]){const p=document.createElement('p');p.className='notice arabic';p.dir='auto';text(p,value);$('#result-notices').append(p);}
 $('#source-list').replaceChildren();$('#sources').hidden=!(r.sources||[]).length;
 for(const url of r.sources||[]){const item=document.createElement('li'),a=document.createElement('a');if(!/^https?:\/\//.test(url))continue;a.href=url;a.target='_blank';a.rel='noopener noreferrer';text(a,url);item.append(a);$('#source-list').append(item);}
 $('#suggestion-list').replaceChildren();$('#suggestions').hidden=!(r.suggestions||[]).length;
 (r.suggestions||[]).forEach((item,index)=>{const button=document.createElement('button');button.className='suggestion arabic';text(button,item.topic);button.onclick=()=>submit({parent_id:job.id,suggestion:index}).catch(e=>showError(e.message));$('#suggestion-list').append(button);});
}
async function watch(id){
 const sequence=++polling;
 while(sequence===polling){
  const job=await api('jobs/'+encodeURIComponent(id));if(sequence!==polling)return;
  active=['queued','running'].includes(job.state)?id:null;setJob(job);
  if(!active){retryRequest=null;return;}
  await new Promise(resolve=>setTimeout(resolve,1000));
 }
}
async function submit(payload){
 showError('');view('create');busy(true);
 try{
  const serialized=JSON.stringify(payload);
  if(!retryRequest||retryRequest.serialized!==serialized)retryRequest={serialized,id:crypto.randomUUID()};
  const job=await api('jobs',{method:'POST',body:JSON.stringify({...payload,request_id:retryRequest.id})});
  active=job.id;await watch(job.id);
 }catch(e){busy(false);showError(e.message);throw e;}
}
async function loadLibrary(){
 const jobs=await api('jobs');$('#library-list').replaceChildren();
 if(!jobs.length){const p=document.createElement('p');text(p,'Your first script starts with an idea. Create one to begin.');$('#library-list').append(p);}
 for(const job of jobs){const button=document.createElement('button');button.className='card library-item';const details=document.createElement('div'),title=document.createElement('h2'),meta=document.createElement('small'),state=document.createElement('span');title.className='arabic';title.dir='auto';text(title,job.topic);text(meta,new Date(job.created).toLocaleString()+' · Instagram Story');text(state,job.state);state.className='pill';details.append(title,meta);button.append(details,state);button.onclick=()=>{view('create');if(['queued','running'].includes(job.state)){watch(job.id).catch(e=>showError(e.message));}else{++polling;setJob(job);$('#result').scrollIntoView({behavior:'smooth'});}};$('#library-list').append(button);}
}
async function loadMilestones(){
 const response=await fetch('/assets/progress.json');if(!response.ok)throw new Error('Progress snapshot unavailable.');const data=await response.json();$('#milestones').replaceChildren();
 for(const milestone of data.milestones){const card=document.createElement('article');card.className='card milestone';const number=document.createElement('div');number.className='milestone-number';text(number,milestone.id);const content=document.createElement('div'),title=document.createElement('h2'),status=document.createElement('span'),goal=document.createElement('p'),tasks=document.createElement('ul');text(title,milestone.title);text(status,milestone.status);status.className='pill';text(goal,milestone.goal);for(const task of milestone.tasks){const li=document.createElement('li');text(li,task);tasks.append(li);}content.append(title,status,goal,tasks);card.append(number,content);$('#milestones').append(card);}
}
async function initialize(){
 const config=await api('config');window.workshopDemo=config.demo;$('#demo-notice').hidden=!config.demo;$('#logout').hidden=config.demo;$('#strategy').replaceChildren();
 for(const option of config.strategies){const el=document.createElement('option');el.value=option.id;text(el,labels[option.id]||option.label);$('#strategy').append(el);}$('#strategy').value='insight';summary();
 const jobs=await api('jobs');const pending=jobs.find(j=>['queued','running'].includes(j.state));if(pending){active=pending.id;await watch(active);}
}
function summary(){text($('#treatment-summary'),$('#strategy').selectedOptions[0]?.textContent);}
$('#strategy').onchange=summary;
for(const button of document.querySelectorAll('[data-view]'))button.onclick=()=>view(button.dataset.view);
$('#new-script').onclick=()=>{view('create');if(active){watch(active).catch(e=>showError(e.message));return;}++polling;current=null;$('#result').hidden=true;$('#topic').value='';$('#topic').focus();};
$('#create-form').onsubmit=e=>{e.preventDefault();submit({topic:$('#topic').value,strategy_id:$('#strategy').value}).catch(()=>{});};
$('#edit-form').onsubmit=e=>{e.preventDefault();if(current)submit({parent_id:current.id,instruction:$('#edit').value}).catch(()=>{});};
$('#clarify-form').onsubmit=e=>{e.preventDefault();if(current)submit({parent_id:current.id,answer:$('#answer').value}).catch(()=>{});};
$('#copy').onclick=async()=>{try{await navigator.clipboard.writeText(current.result.copy);toast('Script copied');}catch(e){toast('Select the script to copy it manually.');}};
$('#login-form').onsubmit=async e=>{e.preventDefault();try{await api('session',{method:'POST',body:JSON.stringify({password:$('#password').value})});$('#password').value='';$('#login-cover').hidden=true;showError('');await initialize();}catch(error){text($('#login-error'),error.message);}};
$('#logout').onclick=async()=>{try{await api('session',{method:'DELETE'});location.reload();}catch(e){showError(e.message);}};
initialize().catch(e=>{if($('#login-cover').hidden)showError(e.message);});
