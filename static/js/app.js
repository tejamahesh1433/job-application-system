const API='http://localhost:8000', UID=1;
window.API = API; window.UID = UID;
let allCache=[], appliedUrls=new Set(), jobsStore={}, docStore=[], docActive='all', docSelected=null;

/* ── Re-execute <script> blocks injected via innerHTML ─────────────────── */
function _execScripts(el){
  el.querySelectorAll('script').forEach(old=>{
    const s=document.createElement('script');
    s.textContent=old.textContent;
    old.parentNode.replaceChild(s,old);
  });
}

/* ── Credentials page init ─────────────────────────────────────────────── */
async function lcredentials(){
  // Auto-seed from profile on first load if no credentials exist yet
  try{
    const r=await fetch(API+'/api/credentials?user_id='+UID);
    const d=await r.json();
    if((d.credentials||[]).length===0){
      await fetch(API+'/api/credentials/seed-from-profile?user_id='+UID,{method:'POST'});
    }
  }catch(e){}
}

/* ─── routing ─── */
function sp(name,navEl){
  if(window.location.hash !== '#' + name) {
    window.history.pushState(null, '', '#' + name);
  }
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.ni').forEach(n=>n.classList.remove('active'));
  
  const pg=g('page-'+name);
  if(pg){
    if(pg.innerHTML.trim() === '') {
       fetch(`views/${name}.html`).then(r=>r.text()).then(html=>{
         pg.innerHTML = html;
         _execScripts(pg);   // re-run <script> tags (innerHTML blocks execution)
         if(name==='apps') lapps();
         if(name==='profile') lprof();
         if(name==='analytics') icharts();
         if(name==='documents') ldocs();
         if(name==='settings') lsettings();
         if(name==='discover') { g('j-loc').value='Anywhere in USA'; loadSavedJobs(); }
         if(name==='overview') { ldash(); aqnim(); }
         if(name==='vault') loadVaultBadge();
         if(name==='credentials') lcredentials();
       }).catch(e=>console.error('Failed to load view:', e));
    } else {
       if(name==='apps') lapps();
       if(name==='profile') lprof();
       if(name==='analytics') { chReady=false; icharts(); }
       if(name==='documents') ldocs();
       if(name==='settings') { if(llmData) renderSettings(llmData); else lsettings(); }
       if(name==='discover') { g('j-loc').value='Anywhere in USA'; loadSavedJobs(); }
       if(name==='overview') { ldash(); aqnim(); }
       if(name==='vault') { if(typeof window.vaultTab==='function') window.vaultTab(window.currentVaultStatus || 'all'); else loadVaultBadge(); }
       if(name==='credentials') { lcredentials(); if(typeof window.loadCredentialsTab==='function') window.loadCredentialsTab(); }
       if(name==='form-records') { if(typeof window.loadFormRecordsTab==='function') window.loadFormRecordsTab(); }
    }
    pg.classList.add('active');
  }
  
  if(navEl) navEl.classList.add('active');
}

/* ─── clock ─── */
function tick(){g('clk').textContent=new Date().toLocaleTimeString('en-US',{hour12:false});}
setInterval(tick,1000); tick();

/* ─── health ─── */
async function hcheck(){
  const chip=g('api-chip'),dot=g('hcdot'),txt=g('hctxt'),spn=g('hcspin');
  spn.style.display='block'; dot.style.display='none'; txt.textContent='Checking...';
  try{
    const r=await fetch(API+'/health',{signal:AbortSignal.timeout(4000)});
    if(!r.ok) throw 0;
    spn.style.display='none'; dot.style.display='block';
    dot.style.background='var(--ok)'; txt.textContent='API Online';
    chip.className='api-chip ok'; shbars(true);
  }catch{
    spn.style.display='none'; dot.style.display='block';
    dot.style.background='var(--err)'; txt.textContent='Offline';
    chip.className='api-chip err'; shbars(false);
  }
}
function shbars(on){
  [['sh1','sv1','88%'],['sh2','sv2','76%'],['sh3','sv3','55%']].forEach(([b,v,w])=>{
    g(b).style.width=on?w:'0%'; g(v).textContent=on?'OK':'—';
  });
}

/* ─── dashboard ─── */
async function ldash(){
  g('tdate').textContent=new Date().toLocaleDateString('en-US',{weekday:'long',year:'numeric',month:'long',day:'numeric'}).toUpperCase();
  try{
    const r=await fetch(API+'/api/dashboard/combined-stats');
    if(!r.ok) throw 0;
    const d=await r.json();
    anum('st',d.total_apps||0); prog('pp1',Math.min(((d.total_apps||0)/25)*100,100));
    g('sm2').textContent=`${d.jobs_queued||0} queued · ${d.ready_apply||0} ready`;
    const m=d.avg_match||0; g('sm').textContent=m.toFixed(1)+'%'; prog('pp2',m);
    anum('si',d.interviews||0); prog('pp3',Math.min(((d.interviews||0)/10)*100,100));
    g('sm3').textContent='Target: 10 per 50 apps';
    g('sr').textContent=(d.response_rate||0).toFixed(1)+'%'; prog('pp4',d.response_rate||0);
    g('acnt').textContent=d.total_apps||0;
    if(d.recent?.length) rrecent(d.recent); else rrecent([]);
  }catch{
    anum('st',0); prog('pp1',0); g('sm2').textContent='Could not load application stats';
    g('sm').textContent='0.0%'; prog('pp2',0);
    anum('si',0); prog('pp3',0); g('sm3').textContent='Target: 10 per 50 apps';
    g('sr').textContent='0.0%'; prog('pp4',0); g('acnt').textContent='0';
    rrecent([]);
    toast('Could not load dashboard stats','err');
  }
  lprof();
}

function rrecent(apps){
  const tb=g('rec-tb');
  if(!apps?.length){tb.innerHTML=`<tr><td colspan="5"><div class="empty"><div class="et">No applications yet — find &amp; apply to jobs above.</div></div></td></tr>`;return;}
  tb.innerHTML=apps.map(a=>arow(a,false)).join('');
}

/* ─── JOB DISCOVERY ─── */
async function searchJobs(force=false){
  const kw=g('j-kw').value.trim()||'DevOps Engineer';
  const loc=g('j-loc').value, wt=g('j-wt').value;
  const jt=g('j-jt').value, src=g('j-src').value;
  const btn=g('search-btn');

  btn.disabled=true;
  const refreshBtn=g('refresh-search-btn');
  if(refreshBtn) refreshBtn.disabled=true;
  btn.innerHTML=force?'<div class="spin"></div> Refreshing...':'<div class="spin"></div> Searching...';
  g('jobs-grid').style.display='none';
  g('jd-empty').style.display='none';
  g('jd-status').style.display='none';

  // show skeletons
  g('jobs-grid').innerHTML=Array(6).fill(`
    <div class="skel">
      <div class="skel-line w70"></div>
      <div class="skel-line w50"></div>
      <div style="height:14px"></div>
      <div class="skel-line w30"></div>
      <div style="height:8px"></div>
      <div class="skel-line"></div>
    </div>`).join('');
  g('jobs-grid').style.display='grid';

  const t0=Date.now();
  try{
    const params=new URLSearchParams({keyword:kw,location:loc,work_type:wt,job_type:jt,source:src,user_id:UID});
    if(force) params.set('force','true');
    const r=await fetch(`${API}/api/jobs/search?${params}`);
    if(!r.ok) throw new Error('API returned '+r.status);
    const data=await r.json();
    const elapsed=((Date.now()-t0)/1000).toFixed(1);
    renderJobs(data.jobs||[], data.sources||[], elapsed, data.message, data.from_cache, data.new_count||0);
  }catch(e){
    g('jobs-grid').style.display='none';
    g('jd-empty').innerHTML=`
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" opacity=".3"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
      <div class="et">Could not reach API — make sure the backend is running.</div>
      <div style="font-family:var(--mono);font-size:9px;color:var(--err);margin-top:6px">python src/main.py → http://localhost:8000</div>`;
    g('jd-empty').style.display='block';
    toast('Backend offline — start with: python src/main.py','err');
  }

  btn.disabled=false;
  if(refreshBtn) refreshBtn.disabled=false;
  btn.innerHTML='<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="7" cy="7" r="5"/><path d="M12 12l2.5 2.5"/></svg> Search Jobs';
}

async function loadSavedJobs(silent=false){
  try{
    const r=await fetch(`${API}/api/jobs/saved?user_id=${UID}`);
    if(!r.ok) throw new Error('API returned '+r.status);
    const data=await r.json();
    renderJobs(data.jobs||[], ['Saved inbox'], 'saved', data.message, true);
  }catch(e){
    if(!silent) toast('Could not load saved discovery jobs','err');
  }
}

function renderJobs(jobs, sources, elapsed, message, fromCache=false, newCount=0){
  const grid=g('jobs-grid'), status=g('jd-status');

  if(!jobs.length){
    grid.style.display='none';
    status.style.display='none';
    g('jd-empty').innerHTML=`
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" opacity=".3"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
      <div class="et">${message||'No saved jobs yet. Search once and they will stay here until you prepare or remove them.'}</div>`;
    g('jd-empty').style.display='block';
    return;
  }

  g('jd-empty').style.display='none';
  const newLabel = newCount > 0 ? ` · <span style="color:#22c55e;font-weight:600">${newCount} new</span>` : '';
  g('jd-count').innerHTML=`${jobs.length} jobs${newLabel}`;
  g('jd-sources').textContent=fromCache ? 'saved inbox — no API credits used' : `via ${(sources||[]).join(', ')||'live sources'}`;
  g('jd-time').textContent=elapsed==='saved' ? 'saved' : `${elapsed}s`;
  status.style.display='flex';

  jobsStore={};
  grid.innerHTML=jobs.map((job,i)=>{jobsStore[i]=job;return jobCard(job,i);}).join('');
  grid.style.display='grid';
  g('live-cnt').textContent=jobs.length;
}

function jobCard(job, idx){
  const scoreNum=parseInt((job.match||'0').replace('%',''))||0;
  const atsNum=parseInt((job.ats||'0').replace('%',''))||0;
  const ivNum=parseInt((job.interview_prob||'0').replace('%',''))||0;
  const co=(job.company||'X').substring(0,2).toUpperCase();
  const src=(job.source||'other').toLowerCase();
  const srcCls=src.includes('remotive')?'remotive':src.includes('arbeit')?'arbeitnow':'other';
  const srcLabel=src.includes('remotive')?'Remotive':src.includes('arbeit')?'Arbeitnow':(job.source||'Live');
  const delay=(idx%6*0.05).toFixed(2);
  const alreadyApplied=appliedUrls.has(job.url);
  const warns=(job.warnings||[]).filter(w=>w&&!w.includes('not listed')||w.length>10).slice(0,2);

  const matchColor=scoreNum>=85?'var(--ok)':scoreNum>=70?'var(--lime)':scoreNum>=50?'var(--warn)':'var(--err)';

  const isNew = job.is_new === true;
  return `<div class="jcard${alreadyApplied?' applied-ok':''}${isNew?' jcard-new':''}" style="animation-delay:${delay}s" id="jc-${idx}">
  <div class="jcard-hd">
    <div class="jcard-logo">${esc(co)}</div>
    <div class="jcard-info">
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
        <div class="jcard-title">${esc(job.title||'Untitled Role')}</div>
        ${isNew?'<span style="background:rgba(34,197,94,.18);color:#22c55e;font-size:10px;font-weight:700;padding:1px 7px;border-radius:8px;letter-spacing:.05em">NEW</span>':''}
      </div>
      <div class="jcard-company">${esc(job.company||'Unknown Company')}</div>
      <div class="jcard-meta">${esc(job.location||'Remote')} · ${esc(job.work_type||'Remote')} · ${esc(job.job_type||'Full Time')}</div>
    </div>
    <div class="jcard-right">
      ${job.id?`<button title="Remove from Job Discovery" onclick="removeSavedJob('${esc(job.id)}',${idx},event)" style="align-self:flex-end;width:24px;height:24px;border:1px solid var(--bord);border-radius:6px;background:var(--surf);color:var(--err);cursor:pointer;font-size:14px;line-height:1">×</button>`:''}
      <span class="jcard-posted">${esc(job.posted||'Recently')}</span>
      ${job.posted_exact?`<span class="jcard-exact">${esc(job.posted_exact)}</span>`:''}
      <span class="src-badge ${srcCls}">${esc(srcLabel)}</span>
    </div>
  </div>
  <div class="jcard-scores">
    <div class="jscore match"><div class="jscore-n" style="color:${matchColor}">${job.match||'—'}</div><div class="jscore-l">Match</div></div>
    <div class="jscore ats"><div class="jscore-n">${job.ats||'—'}</div><div class="jscore-l">ATS</div></div>
    <div class="jscore iv"><div class="jscore-n">${job.interview_prob||'—'}</div><div class="jscore-l">Interview</div></div>
    <div class="jscore sal"><div class="jscore-n">${esc(job.salary&&job.salary!=='Not listed'?job.salary:'—')}</div><div class="jscore-l">Salary</div></div>
  </div>
  <div class="jcard-skills">
    ${(job.skills_matched||[]).length?`<div class="jsk-lbl">Matched skills</div><div class="jsk-row">${(job.skills_matched||[]).map(s=>`<span class="jsk match">✓ ${esc(s)}</span>`).join('')}</div>`:''}
    ${(job.skills_missing||[]).length?`<div class="jsk-row" style="margin-top:4px">${(job.skills_missing||[]).map(s=>`<span class="jsk miss">✗ ${esc(s)}</span>`).join('')}</div>`:''}
  </div>
  ${warns.length?`<div class="jcard-warn">${warns.map(w=>`<div class="jwarn-txt">${esc(w)}</div>`).join('')}</div>`:''}
  <div class="jcard-act">
    ${job.url?`<a href="${esc(job.url)}" target="_blank" class="btn bsec bsm" style="text-decoration:none">
      <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 3H3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1V9M9 1h5m0 0v5m0-5L7 9"/></svg>
      View Job
    </a>`:'<span></span>'}
    <button class="btn ${alreadyApplied?'bok':'bpri'} bsm" id="ab-${idx}"
      onclick="analyzeApply(${idx})"
      ${alreadyApplied?'disabled':''}>
      ${alreadyApplied?'✓ Prepared':'<svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><polygon points="4,2 14,8 4,14"/></svg> Analyze &amp; Prepare'}
    </button>
  </div>
  <div class="jcard-result" id="jr-${idx}"></div>
</div>`;
}

async function removeSavedJob(jobId, idx, ev){
  if(ev) ev.stopPropagation();
  try{
    const r=await fetch(`${API}/api/jobs/saved/${encodeURIComponent(jobId)}?user_id=${UID}`,{method:'DELETE'});
    if(!r.ok) throw new Error('remove');
    const card=g('jc-'+idx);
    if(card) card.remove();
    delete jobsStore[idx];
    const left=document.querySelectorAll('#jobs-grid .jcard').length;
    g('live-cnt').textContent=left;
    g('jd-count').textContent=`${left} saved jobs`;
    if(!left) renderJobs([], ['Saved inbox'], 'saved');
    toast('Removed from Job Discovery','ok');
  }catch(e){ toast('Could not remove job','err'); }
}

async function markDiscoveryApplied(job){
  try{
    if(job?.id) await fetch(`${API}/api/jobs/saved/${encodeURIComponent(job.id)}/applied?user_id=${UID}`,{method:'POST'});
  }catch(e){}
}

async function analyzeApply(idx){
  const job=jobsStore[idx];
  if(!job){ toast('Job data not found','err'); return; }

  const btn=g('ab-'+idx), card=g('jc-'+idx), result=g('jr-'+idx);
  if(!btn||!card) return;

  btn.disabled=true;
  btn.innerHTML='<div class="spin"></div> Analyzing...';
  card.classList.add('analyzing');

  try{
    // Step 1: Analyze job
    const r1=await fetch(`${API}/api/jobs/analyze`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        job_url:job.url||'',
        job_content:job.description||job.title||'',
        source:(job.source||'other').toLowerCase()
      })
    });
    if(!r1.ok) throw new Error('Analysis failed: '+r1.status);
    const d1=await r1.json();

    btn.innerHTML='<div class="spin"></div> Preparing...';

    // Step 2: Workflow
    const r2=await fetch(`${API}/api/workflow/process-single-application?user_id=${UID}&job_id=${d1.job_db_id}`,{method:'POST'});
    if(!r2.ok) throw new Error('Workflow failed: '+r2.status);
    const d2=await r2.json();

    const score=d2.match_score||0;
    const scoreColor=score>=85?'var(--ok)':score>=70?'var(--lime)':score>=50?'var(--warn)':'var(--err)';

    card.classList.remove('analyzing'); card.classList.add('applied-ok');
    btn.className='btn bok bsm'; btn.disabled=true;
    btn.innerHTML='✓ Prepared';
    appliedUrls.add(job.url);
    await markDiscoveryApplied(job);

    result.innerHTML=`<div class="jr-row">
      <div>
        <span style="font-family:var(--mono);font-size:9px;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:3px">Application Prepared</span>
        <div class="jr-info">ID: #${d2.application_id||'—'} · ATS: ${d2.resume_ats_score||'—'}<br>Visit job site to submit manually</div>
      </div>
      <div class="jr-score" style="color:${scoreColor}">${score}%</div>
    </div>`;
    result.classList.add('show');

    toast(`Prepared ${job.company} — submit manually on the job site`,'ok');
    setTimeout(()=>loadSavedJobs(true), 700);
    lapps();
    // refresh badge
    const cnt=parseInt(g('acnt').textContent)||0;
    g('acnt').textContent=cnt+1;

  }catch(e){
    card.classList.remove('analyzing'); card.classList.add('applied-err');
    btn.disabled=false;
    btn.innerHTML='⚠ Retry';
    btn.className='btn bsec bsm';

    const msg=e.message||'';
    let hint='Check that your Anthropic API key is set in .env';
    if(msg.includes('400')) hint='Backend returned error — check your API keys in .env';
    if(msg.includes('500')) hint='Server error — check backend logs';

    result.innerHTML=`<div style="font-family:var(--mono);font-size:9px;color:var(--err)">⚠ ${esc(hint)}</div>`;
    result.classList.add('show');
    toast(hint,'err');
  }
}

/* ─── documents ─── */
function docCat(cat, el){
  docActive=cat;
  document.querySelectorAll('.docf').forEach(x=>x.classList.remove('active'));
  if(el) el.classList.add('active');
  ldocs();
}

async function ldocs(){
  const q=(g('doc-q')?.value||'').trim();
  const params=new URLSearchParams();
  if(q) params.set('q',q);
  if(docActive && docActive!=='all') params.set('category',docActive);
  const list=g('docs-list');
  if(list) list.innerHTML='<div class="empty"><div class="et">Loading files...</div></div>';
  try{
    const r=await fetch(`${API}/api/documents${params.toString()?`?${params}`:''}`);
    if(!r.ok) throw new Error('API returned '+r.status);
    const d=await r.json();
    docStore=d.documents||[];
    const counts=d.counts||{};
    ['all','uploaded_resumes','tailored_resumes','cover_letters'].forEach(k=>{
      const el=g('dc-'+k); if(el) el.textContent=counts[k]??0;
    });
    rdocs();
  }catch(e){
    if(list) list.innerHTML=`<div class="empty"><div class="et">Could not load documents: ${esc(e.message)}</div></div>`;
  }
}

function rdocs(){
  const list=g('docs-list');
  if(!list) return;
  if(!docStore.length){
    list.innerHTML='<div class="empty" style="padding-top:70px"><div class="et">No files found. Upload a resume or generate a tailored resume/cover letter.</div></div>';
    return;
  }
  list.innerHTML=docStore.map((d,i)=>{
    const icon=d.category==='cover_letters'?'✉':'📄';
    const cat=docLabel(d.category);
    const title=d.company&&d.job_title?`${d.company} — ${d.doc_type} — ${d.job_title}`:d.name;
    return `<div class="doc-card ${docSelected?.id===d.id?'active':''}" onclick="selectDoc(${i})">
      <div style="min-width:0;display:flex;align-items:center;gap:12px">
        <div class="avatar" style="width:34px;height:34px;font-size:13px">${icon}</div>
        <div style="min-width:0">
          <div class="doc-card-title" title="${esc(d.name)}">${esc(title)}</div>
          <div class="doc-card-meta">${esc(d.company||'Unassigned')} · ${esc(d.job_title||cat)} · ${fmtSize(d.size_bytes)} · ${fmtDate(d.modified_at)}</div>
        </div>
      </div>
      <div style="display:flex;gap:6px;align-items:center">
        <a class="btn bsec bsm" href="${d.download_url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Download</a>
        <button class="btn bghost bsm" style="padding:0 6px" onclick="event.stopPropagation();renameDocByIdx(${i})" title="Rename">✎</button>
        <button class="btn bghost bsm" style="color:var(--err);padding:0 6px" onclick="event.stopPropagation();deleteDocByIdx(${i})" title="Delete">✕</button>
      </div>
    </div>`;
  }).join('');
}

async function selectDoc(i){
  const d=docStore[i]; if(!d) return;
  docSelected=d; rdocs();
  g('doc-empty').style.display='none';
  g('doc-prev').style.display='block';
  const title=d.company&&d.job_title?`${d.company} — ${d.doc_type}`:d.name;
  g('dp-title').textContent=title;
  g('dp-meta').textContent=`${d.company||'Unassigned'} · ${d.job_title||docLabel(d.category)} · ${fmtDate(d.modified_at)}`;
  g('dp-type').textContent=docLabel(d.category).toUpperCase();
  g('dp-down').href=(d.download_url.startsWith('http')?'':API)+d.download_url;
  const body=g('dp-body');
  const iframe=g('dp-iframe');
  const ext=(d.extension||'').toLowerCase();
  const editable=['txt','json','md','csv'].includes(ext);
  
  if(iframe){ iframe.style.display='none'; iframe.src=''; }
  body.style.display='block';
  body.value='';
  g('dp-save').disabled=!editable;
  
  if(ext==='pdf'){
    body.style.display='none';
    if(iframe){
      iframe.style.display='block';
      iframe.src=(d.view_url.startsWith('http')?'':API)+d.view_url;
    }
    return;
  }
  
  if(!editable){
    body.value='Preview is not available for this file type. Use Download to open it.';
    return;
  }
  try{
    const r=await fetch((d.view_url.startsWith('http')?'':API)+d.view_url);
    if(!r.ok) throw new Error('Preview unavailable');
    body.value=await r.text();
  }catch(e){ body.value=e.message; }
}

async function copyDocPreview(){
  const text=g('dp-body')?.value||g('dp-body')?.textContent||'';
  if(!text.trim()) return;
  await navigator.clipboard.writeText(text);
  toast('Document text copied','ok');
}

async function uploadDocResume(file){
  if(!file) return;
  const fd=new FormData();
  fd.append('file',file);
  try{
    const r=await fetch(`${API}/api/user/upload-resume-file?user_id=${UID}`,{method:'POST',body:fd});
    if(!r.ok) throw new Error('Upload failed');
    toast('Resume uploaded','ok');
    docActive='uploaded_resumes';
    document.querySelectorAll('.docf').forEach(x=>x.classList.toggle('active',x.dataset.cat==='uploaded_resumes'));
    ldocs();
  }catch(e){ toast(e.message||'Upload failed','err'); }
}

async function renameDoc(){
  if(!docSelected) return;
  const current=docSelected.name.replace(/\.[^.]+$/,'');
  const name=await agPrompt('New file name',current);
  if(!name || name===current) return;
  try{
    const r=await fetch(`${API}/api/documents/${encodeURIComponent(docSelected.category)}/${encodeURIComponent(docSelected.name)}`,{
      method:'PATCH',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({new_name:name})
    });
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Rename failed'}));throw new Error(e.detail||'Rename failed');}
    toast('File renamed','ok');
    docSelected=null; ldocs();
  }catch(e){ toast(e.message||'Rename failed','err'); }
}

async function saveDocText(){
  if(!docSelected) return;
  const text=g('dp-body')?.value||'';
  try{
    const r=await fetch(`${API}/api/documents/${encodeURIComponent(docSelected.category)}/${encodeURIComponent(docSelected.name)}`,{
      method:'PATCH',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({content:text})
    });
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Save failed'}));throw new Error(e.detail||'Save failed');}
    toast('File saved','ok');
    ldocs();
  }catch(e){ toast(e.message||'Save failed','err'); }
}

async function deleteDoc(){
  if(!docSelected) return;
  if(!(await agConfirm(`Delete "${docSelected.name}"?`))) return;
  try{
    const r=await fetch(`${API}/api/documents/${encodeURIComponent(docSelected.category)}/${encodeURIComponent(docSelected.name)}`,{method:'DELETE'});
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Delete failed'}));throw new Error(e.detail||'Delete failed');}
    toast('File deleted','ok');
    docSelected=null;
    g('doc-prev').style.display='none';
    g('doc-empty').style.display='block';
    ldocs();
  }catch(e){ toast(e.message||'Delete failed','err'); }
}

async function deleteDocByIdx(i){
  const d=docStore[i]; if(!d) return;
  if(!(await agConfirm(`Delete "${d.name}"?`))) return;
  try{
    const r=await fetch(`${API}/api/documents/${encodeURIComponent(d.category)}/${encodeURIComponent(d.name)}`,{method:'DELETE'});
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Delete failed'}));throw new Error(e.detail||'Delete failed');}
    toast('File deleted','ok');
    if(docSelected && docSelected.id === d.id){
      docSelected=null;
      g('doc-prev').style.display='none';
      g('doc-empty').style.display='block';
    }
    ldocs();
  }catch(e){ toast(e.message||'Delete failed','err'); }
}

async function renameDocByIdx(i){
  const d=docStore[i]; if(!d) return;
  const current=d.name.replace(/\.[^.]+$/,'');
  const name=await agPrompt('New file name',current);
  if(!name || name===current) return;
  try{
    const r=await fetch(`${API}/api/documents/${encodeURIComponent(d.category)}/${encodeURIComponent(d.name)}`,{
      method:'PATCH',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({new_name:name})
    });
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Rename failed'}));throw new Error(e.detail||'Rename failed');}
    toast('File renamed','ok');
    if(docSelected && docSelected.id === d.id) docSelected=null;
    ldocs();
  }catch(e){ toast(e.message||'Rename failed','err'); }
}

function docLabel(cat){
  return ({uploaded_resumes:'Uploaded Resume',tailored_resumes:'Tailored Resume',cover_letters:'Cover Letter'})[cat]||'File';
}
function fmtSize(bytes){
  const n=Number(bytes||0);
  if(n<1024) return `${n} B`;
  if(n<1024*1024) return `${Math.round(n/1024)} KB`;
  return `${(n/1024/1024).toFixed(1)} MB`;
}
function fmtDate(value){
  const d=new Date(value);
  return isNaN(d)?'Unknown date':d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
}
function money(v){
  const n=Number(v||0);
  if(n>0 && n<0.01) return '<$0.01';
  return '$'+n.toFixed(2);
}
function pct(used,cap){
  return cap>0?Math.max(0,Math.min(100,Math.round((Number(used||0)/Number(cap))*100))):0;
}
function usageTile(label,value,detail,percent){
  return `<div style="padding:12px;border:1px solid var(--bord);border-radius:8px;background:var(--surf)">
    <div style="font-family:var(--mono);font-size:8.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--t3);margin-bottom:7px">${esc(label)}</div>
    <div style="font-family:var(--serif);font-size:24px;font-weight:700;color:var(--t1);line-height:1">${esc(value)}</div>
    <div class="bt" style="height:4px;margin:10px 0 7px"><div class="bf" style="width:${percent}%;background:var(--acc)"></div></div>
    <div style="font-family:var(--mono);font-size:9px;color:var(--t3)">${esc(detail)}</div>
  </div>`;
}

/* ─── applications ─── */
async function lapps(){
  g('atb').innerHTML=`<tr><td colspan="6"><div class="empty"><div class="spin" style="margin:0 auto 8px"></div><div class="et">Loading...</div></div></td></tr>`;
  try{
    const r=await fetch(`${API}/api/applications/${UID}`);
    if(!r.ok) throw 0;
    const d=await r.json();
    allCache=d.applications||[]; rall(allCache);
  }catch{
    allCache=[];
    g('atb').innerHTML=`<tr><td colspan="6"><div class="empty"><div class="et">Could not load applications. Check the API status and try Refresh.</div></div></td></tr>`;
    toast('Could not load applications','err');
  }
}

function rall(apps){
  const tb=g('atb');
  if(!apps?.length){tb.innerHTML=`<tr><td colspan="6"><div class="empty"><div class="et">No applications found.</div></div></td></tr>`;return;}
  tb.innerHTML=apps.map(a=>arow(a,true)).join('');
}

function arow(a,withAct){
  const sc=a.match_score||0;
  const cl=sc>=85?'sex':sc>=70?'sgd':sc>=50?'smd':'swk';
  const pv=sc?sc+'%':'—';
  const st=mst(a.status);
  const co=(a.company||'X').substring(0,2).toUpperCase();
  const dt=(a.submitted_at||a.date||'—').toString().substring(0,10);
  return `<tr>
    <td><div class="coc"><div class="colo">${esc(co)}</div><div class="conm">${esc(a.company||'Unknown')}</div></div></td>
    <td><div class="ronm">${esc(a.title||a.job_title||'—')}</div></td>
    <td><div class="ms ${cl}"><div class="msb"><div class="msf" style="width:${sc}%"></div></div><span class="msv">${pv}</span></div></td>
    <td>${bdg(st)}</td>
    <td style="font-family:var(--mono);font-size:10px;color:var(--t3)">${dt}</td>
    ${withAct?`<td><button class="btn bghost bsm" onclick="sint(${a.id})">Set Interview</button></td>`:''}
  </tr>`;
}

function fapps(){
  const q=g('fq').value.toLowerCase(), s=g('fst').value;
  rall(allCache.filter(a=>{
    const mq=!q||(a.company||'').toLowerCase().includes(q)||(a.title||a.job_title||'').toLowerCase().includes(q);
    const ms=!s||mst(a.status)===s;
    return mq&&ms;
  }));
}

async function sint(id){
  try{
    const r=await fetch(`${API}/api/applications/${id}/status?status=INTERVIEW_SCHEDULED`,{method:'PATCH'});
    if(r.ok){toast('Status updated','ok');lapps();}else throw 0;
  }catch{toast('Could not update status','err');}
}

/* ─── profile ─── */
async function lprof(){
  try{
    const r=await fetch(`${API}/api/user/${UID}/profile`);
    if(!r.ok) throw 0;
    rprof(await r.json());
  }catch{
    rprof({name:'Unknown User',current_title:'—',current_company:'—',location:'—',years_experience:0,skills:{},certifications:{}});
  }
}

function rprof(p){
  const ini=(p.name||'U').split(' ').map(w=>w[0]).join('').substring(0,1).toUpperCase();
  const nm=p.name||'Unknown', tl=p.current_title||'—';
  if(g('mav')) g('mav').textContent=ini; 
  if(g('mnm')) g('mnm').textContent=nm; 
  if(g('mtl')) g('mtl').textContent=tl;
    if(g('plav')){
      g('plav').textContent=ini; g('pnm').textContent=nm; g('ptl').textContent=tl;
      g('plc').textContent=p.location||'—'; g('pexp').textContent=p.years_experience!==null?p.years_experience:0;
      g('pskc').textContent=Object.keys(p.skills||{}).length;
      g('pcrt').textContent=Object.keys(p.certifications||{}).length;
      g('enm').value=p.name||''; g('eem').value=p.email||'';
      g('etl').value=p.current_title||''; g('eloc').value=p.location||'';
      g('eco').value=p.current_company||''; g('eexp').value=p.years_experience!==null?p.years_experience:'';
      g('egh').value=p.github_profile||''; g('eli').value=p.linkedin_profile||'';
      g('eprt').value=p.portfolio_url||'';
    }
  const fs=[p.name,p.email,p.current_title,p.phone,p.location,Object.keys(p.certifications||{}).length?1:null,p.github_profile,p.linkedin_profile];
  const cp=Math.round((fs.filter(Boolean).length/fs.length)*100);
  if(g('mcp')) g('mcp').textContent=cp+'%'; 
  if(g('mcpb')) setTimeout(()=>{g('mcpb').style.width=cp+'%';},80);
  if(g('pcpp')){g('pcpp').textContent=cp+'%';setTimeout(()=>{g('pcpb').style.width=cp+'%';},80);}
  const sk=p.skills||{};
  const t8=Object.entries(sk).sort((a,b)=>b[1]-a[1]).slice(0,8);
  if(g('msk')) g('msk').innerHTML=t8.length?t8.map(([k,v])=>`<span class="skt${v>=7?' top':''}">${esc(k)}</span>`).join(''):`<span class="skt" style="color:var(--t3)">No skills</span>`;
  if(g('pskd')) g('pskd').innerHTML=Object.entries(sk).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<span class="skt${v>=7?' top':''}">${esc(k)} <span style="opacity:.45">${v}/10</span></span>`).join('')||`<span class="skt" style="color:var(--t3)">No skills</span>`;
}

async function sprof(){
  const pl={
    name:g('enm').value,
    current_title:g('etl').value,
    location:g('eloc').value,
    current_company:g('eco').value,
    years_experience:g('eexp').value !== '' ? Number(g('eexp').value) : null,
    github_profile:g('egh').value,
    linkedin_profile:g('eli').value,
    portfolio_url:g('eprt').value
  };
  try{
    const r=await fetch(`${API}/api/user/${UID}/profile`,{
      method:'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(pl)
    });
    if(r.ok){
      toast('Profile saved!','ok');
      lprof();
      // Auto-sync credentials with updated profile data (email, name, phone, etc.)
      fetch(API+'/api/credentials/seed-from-profile?user_id='+UID,{method:'POST'}).catch(()=>{});
    }else throw 0;
  }catch{toast('Profile save failed — endpoint may not be wired yet','err');}
}

async function upres(){
  const file=g('rfile').files[0]; if(!file) return;
  const fd=new FormData(); fd.append('file',file);
  toast(`Uploading ${file.name}...`,'info');
  try{
    const r=await fetch(`${API}/api/user/upload-resume-file?user_id=${UID}`,{method:'POST',body:fd});
    if(r.ok){ toast('Resume uploaded and profile extracted!','ok'); lprof(); } else throw 0;
  }catch{toast('Upload failed — ensure backend is running','err');}
}

/* ─── new application page ─── */
async function papp(){
  const url=g('jurl').value.trim(), cont=g('jcont').value.trim();
  const src=g('jsrc').value, mod=g('rmode').value;
  if(!url&&!cont){toast('Provide a job URL or paste content','err');return;}
  const btn=g('pbtn'), sta=g('pstat');
  btn.disabled=true; btn.innerHTML='<div class="spin"></div> Processing...';
  try{
    sta.textContent='Step 1/3 — Analyzing job...';
    const r1=await fetch(`${API}/api/jobs/analyze`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({job_url:url,job_content:cont,source:src})
    });
    if(!r1.ok) throw new Error('analysis');
    const d1=await r1.json();
    sta.textContent='Step 2/3 — Running workflow...';
    const r2=await fetch(`${API}/api/workflow/process-single-application?user_id=${UID}&job_id=${d1.job_db_id}`,{method:'POST'});
    if(!r2.ok) throw new Error('workflow');
    const d2=await r2.json();
    sta.textContent=''; sres(d1,d2,mod); toast('Application prepared — submit manually on the job site','ok');
  }catch(e){
    sta.textContent='';
    g('rp').classList.remove('show');
    const msg=e.message==='analysis'
      ? 'Job analysis failed. Check the URL/content and API logs.'
      : e.message==='workflow'
        ? 'Workflow failed. The application was not submitted.'
        : 'Could not process this application.';
    g('pstat').textContent=msg;
    toast(msg,'err');
  }
  btn.disabled=false;
  btn.innerHTML='<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="8" cy="8" r="6"/><path d="M6 8h4M8 6v4"/></svg> Analyze &amp; Process';
}

function sres(d1,d2,mod){
  const sc=d2.match_score||87;
  g('rsco').textContent=sc; g('rco').textContent=d1.company_name||'Company';
  g('rrol').textContent=d1.job_title||'Role'; g('rmod').textContent=mod;
  g('rats').textContent=d2.resume_ats_score?Math.round(d2.resume_ats_score)+'%':'—';
  g('rid').textContent='#'+(d2.application_id||'—');
  sring(sc); g('rp').classList.add('show');
}

function sring(sc){
  const c=sc>=85?'var(--ok)':sc>=70?'var(--lime)':sc>=50?'var(--warn)':'var(--err)';
  const el=g('sring'); el.style.borderColor=c; el.style.boxShadow=`0 0 22px ${sc>=85?'rgba(34,197,94,.25)':'rgba(245,158,11,.2)'}`;
  g('rsco').style.color=c;
  const q=sc>=85?'STRONG MATCH':sc>=70?'GOOD MATCH':sc>=50?'MODERATE':'WEAK MATCH';
  const qc=sc>=85?'interview':sc>=70?'submitted':sc>=50?'pending':'rejected';
  g('rqual').className=`badge ${qc}`; g('rqual').innerHTML=`<span class="bd"></span>${q}`;
}

function cform(){g('jurl').value='';g('jcont').value='';g('rp').classList.remove('show');g('pstat').textContent='';}

/* ─── charts ─── */
let chReady=false;
async function icharts(){
  if(chReady) return; chReady=true;
  
  // Fetch real data
  let apps=[];
  try{
    const r=await fetch(`${API}/api/applications/${UID}`);
    if(r.ok){ const d=await r.json(); apps=d.applications||[]; }
  }catch(e){}

  // Compute 7-day trend
  const dts=[...Array(7)].map((_,i)=>{const d=new Date();d.setDate(d.getDate()-6+i);return d.toISOString().substring(0,10);});
  const trend=dts.map(d=>apps.filter(a=>(a.submitted_at||a.created_at||'').startsWith(d)).length);
  const dtl=dts.map(d=>new Date(d).toLocaleDateString('en-US',{weekday:'short'}));

  // Compute status breakdown
  const stCount={applied:0,reviewing:0,interview:0,offered:0,rejected:0};
  apps.forEach(a=>{
    const s=mst(a.status);
    if(s==='submitted'||s==='pending') stCount.applied++;
    else if(s==='interview') stCount.interview++;
    else if(s==='offered') stCount.offered++;
    else if(s==='rejected') stCount.rejected++;
  });

  // Compute match score distribution
  const msc=[0,0,0,0]; // <50, 50-70, 70-85, 85-100
  apps.forEach(a=>{
    const s=a.match_score||0;
    if(s<50) msc[0]++; else if(s<70) msc[1]++; else if(s<85) msc[2]++; else msc[3]++;
  });

  Chart.defaults.color='#4A5568'; Chart.defaults.borderColor='rgba(28,35,55,.8)';
  Chart.defaults.font.family="'IBM Plex Mono',monospace"; Chart.defaults.font.size=10;
  
  new Chart(g('cht').getContext('2d'),{type:'line',data:{labels:dtl,datasets:[{label:'Applications',data:trend,borderColor:'#E8913A',backgroundColor:'rgba(232,145,58,.06)',borderWidth:2,tension:.4,fill:true,pointBackgroundColor:'#E8913A',pointRadius:3,pointHoverRadius:5}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{color:'rgba(28,35,55,.6)'},ticks:{color:'#3D4D60'}},y:{grid:{color:'rgba(28,35,55,.6)'},ticks:{color:'#3D4D60'},suggestedMax:5}}}});
  new Chart(g('chs').getContext('2d'),{type:'doughnut',data:{labels:['Applied','Interview','Offered','Rejected'],datasets:[{data:[stCount.applied,stCount.interview,stCount.offered,stCount.rejected],backgroundColor:['#60A5FA','#22C55E','#4ADE80','#EF4444'],borderWidth:0,hoverOffset:4}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'right',labels:{boxWidth:10,padding:12,color:'#7E8FA8',font:{size:9}}}},cutout:'65%'}});
  new Chart(g('chm').getContext('2d'),{type:'bar',data:{labels:['< 50%','50–70%','70–85%','85–100%'],datasets:[{label:'Apps',data:msc,backgroundColor:['#EF4444','#F59E0B','#84CC16','#22C55E'],borderRadius:3,borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{display:false},ticks:{color:'#3D4D60'}},y:{grid:{color:'rgba(28,35,55,.6)'},ticks:{color:'#3D4D60'},suggestedMax:5}}}});
  
  const avgMatch=apps.length?Math.round(apps.reduce((a,b)=>a+(b.match_score||0),0)/apps.length):0;
  
  g('kpm').innerHTML=[
    {l:'Total Applications',v:apps.length,n:'All time'},
    {l:'Avg Match Score',v:avgMatch+'%',n:'Across all apps'},
    {l:'Interviews Scheduled',v:stCount.interview,n:'Upcoming'},
    {l:'Offers Received',v:stCount.offered,n:'Congratulations!'},
    {l:'Response Rate',v:(apps.length?Math.round((stCount.interview+stCount.offered+stCount.rejected)/apps.length*100):0)+'%',n:'Heard back'},
  ].map(m=>`<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(28,35,55,.4)"><div><div style="font-size:12px;color:var(--t1)">${m.l}</div><div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-top:2px">${m.n}</div></div><div style="font-family:var(--serif);font-size:20px;font-weight:700;color:var(--acc)">${m.v}</div></div>`).join('');
}

/* ─── queue anim ─── */
const qstg=[['Scanning job requirements...','Cross-referencing keywords...','Finalizing ATS score...'],['Extracting required skills...','Customizing resume (balanced)...','Scoring keyword density...'],['Analyzing responsibilities...','Generating cover letter...','Writing form answers...']];
function aqnim(){
  document.querySelectorAll('#qlist .qi').forEach((item,i)=>{
    const fill=item.querySelector('.qfill'), pct=item.querySelector('.qpct'), stg=item.querySelector('.qstg');
    let p=parseFloat(fill?.style.width)||0;
    setInterval(()=>{
      if(p>=99) return;
      p=Math.min(p+Math.random()*3+.5,99);
      if(fill) fill.style.width=p.toFixed(1)+'%';
      if(pct) pct.textContent=Math.round(p)+'%';
      const si=p<40?0:p<75?1:2;
      if(stg) stg.textContent=qstg[i%3][si];
    },2000+i*300);
  });
}

/* ─── helpers ─── */
function agConfirm(msg){
  return new Promise(r=>{
    const o=document.createElement('div');
    o.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.6);backdrop-filter:blur(3px);z-index:9999;display:flex;align-items:center;justify-content:center;';
    const b=document.createElement('div');
    b.style.cssText='background:var(--card);border:1px solid var(--bord);border-radius:var(--r);padding:24px;width:340px;box-shadow:0 10px 30px rgba(0,0,0,.5);text-align:center;animation:fup .2s ease;';
    const t=document.createElement('div');
    t.style.cssText='font-size:14px;color:var(--t1);margin-bottom:20px;word-break:break-word;';
    t.textContent=msg;
    const bt=document.createElement('div');
    bt.style.cssText='display:flex;gap:10px;justify-content:center;';
    const c=document.createElement('button');
    c.className='btn bsec';c.textContent='Cancel';
    const k=document.createElement('button');
    k.className='btn bpri';k.textContent='Delete';k.style.background='var(--err)';k.style.borderColor='var(--err)';
    c.onclick=()=>{o.remove();r(false);};
    k.onclick=()=>{o.remove();r(true);};
    bt.append(c,k);b.append(t,bt);o.append(b);document.body.append(o);
  });
}
function agPrompt(msg,def=''){
  return new Promise(r=>{
    const o=document.createElement('div');
    o.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.6);backdrop-filter:blur(3px);z-index:9999;display:flex;align-items:center;justify-content:center;';
    const b=document.createElement('div');
    b.style.cssText='background:var(--card);border:1px solid var(--bord);border-radius:var(--r);padding:24px;width:340px;box-shadow:0 10px 30px rgba(0,0,0,.5);text-align:center;animation:fup .2s ease;';
    const t=document.createElement('div');
    t.style.cssText='font-size:14px;color:var(--t1);margin-bottom:12px;';
    t.textContent=msg;
    const i=document.createElement('input');
    i.type='text';i.value=def;
    i.style.cssText='width:100%;background:var(--surf);border:1px solid var(--bord);border-radius:var(--rs);padding:8px 12px;color:var(--t1);margin-bottom:20px;font-family:var(--sans);';
    const bt=document.createElement('div');
    bt.style.cssText='display:flex;gap:10px;justify-content:center;';
    const c=document.createElement('button');
    c.className='btn bsec';c.textContent='Cancel';
    const k=document.createElement('button');
    k.className='btn bpri';k.textContent='Rename';
    const sub=(v)=>{o.remove();r(v);};
    c.onclick=()=>sub(null);
    k.onclick=()=>sub(i.value);
    i.onkeydown=(e)=>{if(e.key==='Enter')sub(i.value);else if(e.key==='Escape')sub(null);};
    bt.append(c,k);b.append(t,i,bt);o.append(b);document.body.append(o);
    requestAnimationFrame(()=>i.select());
  });
}

function mst(s){
  const m={
    // uppercase (from query param values)
    PENDING:'pending',SUBMITTED:'submitted',APPLIED:'submitted',
    DRAFT:'pending',WITHDRAWN:'rejected',
    INTERVIEW_SCHEDULED:'interview',INTERVIEWED:'interview',
    OFFER_RECEIVED:'offered',OFFERED:'offered',REJECTED:'rejected',
    // lowercase (from DB)
    pending:'pending',submitted:'submitted',applied:'submitted',
    draft:'pending',withdrawn:'rejected',
    interview_scheduled:'interview',interviewed:'interview',
    offer_received:'offered',offered:'offered',rejected:'rejected',
    // misc
    interview:'interview',reviewing:'pending',
  };
  return m[s]||'pending';
}
function bdg(st){const lbl={pending:'Pending',submitted:'Applied',interview:'Interviewing',offered:'Offered',rejected:'Rejected',processing:'Processing'};return `<span class="badge ${st}"><span class="bd"></span>${lbl[st]||st}</span>`;}
function anum(id,target){const el=g(id);if(!el) return;const d=900,t0=performance.now();(function step(now){const p=Math.min((now-t0)/d,1),e=1-Math.pow(1-p,3);el.textContent=Math.round(target*e);if(p<1) requestAnimationFrame(step);})(t0);}
function prog(id,pct){setTimeout(()=>{const e=g(id);if(e) e.style.width=Math.min(pct,100)+'%';},60);}
function g(id){return document.getElementById(id);}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function toast(msg,type='info'){
  const c=g('toasts'),t=document.createElement('div');
  t.className=`toast ${type}`;t.textContent=msg;c.appendChild(t);
  setTimeout(()=>{t.style.cssText+=';opacity:0;transform:translateX(20px);transition:all .3s';setTimeout(()=>t.remove(),320);},3500);
}

/* ─── LLM STATUS ─── */
let llmData = null;

async function lsettings() {
  try {
    const r = await fetch(`${API}/api/llm/status`);
    if (!r.ok) throw new Error('status ' + r.status);
    llmData = await r.json();
    renderSettings(llmData);
    updateLlmPill(llmData);
  } catch(e) {
    // Ollama/API unreachable — show offline state
    const offline = {
      ollama:{ available:false, url:'http://localhost:11434', active_model:'none', installed:[], model_count:0 },
      cloud:{ anthropic_configured:false, openai_configured:false },
      active_provider:'none',
      cost_estimate:'No provider configured',
      recommended:[],
    };
    renderSettings(offline);
    updateLlmPill(offline);
  }
}

function updateLlmPill(data) {
  const dot = g('llm-dot'), lbl = g('llm-label'), cost = g('llm-cost'), pill = g('llm-pill');
  if (!dot) return;
  if (data.ollama.available) {
    dot.className = 'ag-d on';
    lbl.textContent = `Ollama · ${data.ollama.active_model}`;
    lbl.style.color = 'var(--ok)';
    cost.textContent = '$0/mo';
    cost.style.color = 'var(--ok)';
    pill.style.borderColor = 'rgba(34,197,94,.3)';
  } else if (data.cloud.anthropic_configured) {
    dot.className = 'ag-d idle';
    lbl.textContent = 'Claude API';
    lbl.style.color = 'var(--warn)';
    cost.textContent = '~$10/mo';
    cost.style.color = 'var(--warn)';
    pill.style.borderColor = 'rgba(245,158,11,.3)';
  } else {
    dot.style.background = 'var(--err)';
    lbl.textContent = 'No LLM';
    lbl.style.color = 'var(--err)';
    cost.textContent = '';
    pill.style.borderColor = 'rgba(239,68,68,.3)';
  }
}

function renderSettings(data) {
  const cards = g('llm-cards');
  if (!cards) return;

  const ollamaOk = data.ollama.available;
  const anthropicOk = data.cloud.anthropic_configured;
  const openaiOk = data.cloud.openai_configured;
  const usage = data.usage || {};
  const j = usage.jsearch || {};
  const day = usage.daily || {};
  const cloud = usage.cloud || {};
  const haikuCost = Number(cloud.claude_haiku_cost_usd || 0);
  const sonnetCost = Number(cloud.claude_sonnet_cost_usd || 0);
  const claudeCost = haikuCost + sonnetCost;
  const claudeBudget = Number(cloud.claude_haiku_budget_usd || 0) + Number(cloud.claude_sonnet_budget_usd || 0);
  const openaiCost = Number(cloud.openai_cost_usd || 0);
  const openaiBudget = Number(cloud.openai_budget_usd || 0);
  const jReq = Number(j.requests || 0);
  const jCap = Number(j.monthly_cap || 0);
  const minReq = Number(j.per_minute_requests || 0);
  const minCap = Number(j.per_minute_cap || 0);
  const dayReq = Number(day.jsearch_requests || 0);
  const dayCap = Number(day.jsearch_daily_cap || 0);

  cards.innerHTML = `
    <!-- Ollama card -->
    <div class="llm-card ${ollamaOk?'online':'offline'}">
      <div class="llm-card-head">
        <div>
          <div class="llm-card-title">🦙 Ollama — Local AI</div>
          <div style="font-size:11px;color:var(--t3);margin-top:3px">${data.ollama.url}</div>
        </div>
        <span class="llm-status-badge ${ollamaOk?'on':'off'}">${ollamaOk?'● ONLINE':'● OFFLINE'}</span>
      </div>

      ${ollamaOk ? `
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
          <div>
            <div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:3px">ACTIVE MODEL</div>
            <div style="font-family:var(--mono);font-size:13px;font-weight:600;color:var(--ok)">${esc(data.ollama.active_model)}</div>
          </div>
          <div style="margin-left:auto;text-align:right">
            <div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:3px">COST / MONTH</div>
            <div class="cost-badge free">$0.00</div>
          </div>
        </div>
        <div style="font-family:var(--mono);font-size:9px;color:var(--t3)">${data.ollama.model_count} model(s) installed · All agents use Ollama by default</div>
      ` : `
        <div style="font-family:var(--mono);font-size:10px;color:var(--err);margin-bottom:10px">Ollama not running — start it to use local AI at zero cost</div>
        <div style="display:flex;flex-direction:column;gap:6px">
          <div class="setup-cmd" onclick="copyCmd(this)">ollama serve</div>
          <div class="setup-cmd" onclick="copyCmd(this)">ollama pull mistral</div>
        </div>
      `}
    </div>

    <!-- Cloud fallback card -->
    <div class="llm-card ${anthropicOk||openaiOk?'online':'offline'}">
      <div class="llm-card-head">
        <div>
          <div class="llm-card-title">☁ Cloud APIs — Controlled Use</div>
          <div style="font-size:11px;color:var(--t3);margin-top:3px">Claude for resume/interview tasks · OpenAI fallback only</div>
        </div>
        <span class="llm-status-badge ${anthropicOk||openaiOk?'warn':'off'}">${anthropicOk||openaiOk?'● STANDBY':'● NOT SET'}</span>
      </div>
      <div style="display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 10px;background:var(--surf);border:1px solid var(--bord);border-radius:var(--rs)">
          <span style="font-family:var(--mono);font-size:10px;color:var(--t2)">Anthropic Claude</span>
          <span class="llm-status-badge ${anthropicOk?'warn':'off'}" style="font-size:8px">${anthropicOk?'CONFIGURED':'NOT SET'}</span>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 10px;background:var(--surf);border:1px solid var(--bord);border-radius:var(--rs)">
          <span style="font-family:var(--mono);font-size:10px;color:var(--t2)">OpenAI GPT-4</span>
          <span class="llm-status-badge ${openaiOk?'warn':'off'}" style="font-size:8px">${openaiOk?'CONFIGURED':'NOT SET'}</span>
        </div>
      </div>
      <div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-top:10px">Claude is reserved for high-value writing and interview prep. OpenAI is fallback only.</div>
    </div>

    <div class="llm-card online" style="grid-column:1 / -1">
      <div class="llm-card-head">
        <div>
          <div class="llm-card-title">API Usage — ${esc(usage.month || 'Current Month')}</div>
          <div style="font-size:11px;color:var(--t3);margin-top:3px">Local ledger from logs/usage_ledger.jsonl</div>
        </div>
        <span class="llm-status-badge on">TRACKING</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
        ${usageTile('JSearch Month', `${jReq}`, `${jReq} / ${jCap} paid searches`, pct(jReq,jCap))}
        ${usageTile('JSearch Today', `${dayReq}`, `${dayReq} / ${dayCap} today · ${minReq} / ${minCap} per minute`, pct(dayReq,dayCap))}
        ${usageTile('Claude Spend', money(claudeCost), `${money(haikuCost)} Haiku + ${money(sonnetCost)} Sonnet / ${money(claudeBudget)}`, pct(claudeCost,claudeBudget))}
        ${usageTile('OpenAI Fallback', money(openaiCost), `${money(openaiCost)} / ${money(openaiBudget)}`, pct(openaiCost,openaiBudget))}
      </div>
      <div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-top:12px">Opening Job Discovery does not search anymore. JSearch is used only when you choose “JSearch Paid” and click Search.</div>
    </div>
  `;

  // Installed models list
  const instList = g('installed-models-list');
  const badge = g('active-model-badge');
  if (instList) {
    if (!ollamaOk) {
      instList.innerHTML = `<div class="empty"><div class="et">Ollama offline — run 'ollama serve' first</div></div>`;
      if (badge) badge.textContent = 'Ollama offline';
    } else if (!data.ollama.installed.length) {
      instList.innerHTML = `<div class="empty"><div class="et">No models installed — pull one below</div></div>`;
      if (badge) badge.textContent = '0 models';
    } else {
      if (badge) badge.textContent = `${data.ollama.installed.length} installed · active: ${data.ollama.active_model}`;
      instList.innerHTML = data.ollama.installed.map(m => `
        <div class="model-row">
          <div style="width:8px;height:8px;border-radius:50%;background:${m.is_active?'var(--ok)':'var(--bord-b)'};flex-shrink:0"></div>
          <div class="model-name">${esc(m.name)}</div>
          <div class="model-size">${m.size_gb} GB</div>
          ${m.is_active ? '<span class="model-active-tag">ACTIVE</span>' : `<button class="btn bsec bsm" onclick="useModel('${esc(m.name)}')">Use</button>`}
          <button class="btn bghost bsm" onclick="deleteModel('${esc(m.name)}')" style="color:var(--err);font-size:10px">✕</button>
        </div>
      `).join('');
    }
  }

  // Recommended models
  const recList = g('rec-models-list');
  if (recList && data.recommended?.length) {
    const installedNames = (data.ollama.installed || []).map(m => m.name);
    recList.innerHTML = data.recommended.map(m => {
      const inst = installedNames.some(n => n.startsWith(m.name.split(':')[0]));
      return `<div class="rec-model-row">
        <div class="rec-model-info">
          <div class="rec-model-name">${esc(m.display)}</div>
          <div class="rec-model-meta">
            <span class="rec-tag spd">${esc(m.speed)}</span>
            <span class="rec-tag qual">${esc(m.quality)}</span>
            <span class="rec-tag">${esc(m.size)}</span>
            <span class="rec-tag">${m.vram_gb}GB VRAM</span>
          </div>
          <div class="rec-model-use">${esc(m.best_for)}</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-shrink:0">
          ${inst
            ? `<span class="model-active-tag">✓ INSTALLED</span>`
            : `<button class="btn bpri bsm" id="pull-${m.name.replace(':','-')}" onclick="pullModel('${esc(m.name)}')">
                <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M8 2v9M4 8l4 4 4-4"/><path d="M2 14h12"/>
                </svg>
                Pull
              </button>`
          }
          <div class="setup-cmd" onclick="copyCmd(this)" style="font-size:10px;padding:4px 10px">${esc(m.pull_cmd)}</div>
        </div>
      </div>`;
    }).join('');
  }
}

async function useModel(name) {
  try {
    const r = await fetch(`${API}/api/llm/set-model?model_name=${encodeURIComponent(name)}`, {method:'POST'});
    const d = await r.json();
    if (d.success) { toast(`Active model: ${name}`, 'ok'); lsettings(); }
    else toast(d.message || 'Failed', 'err');
  } catch { toast('Could not switch model', 'err'); }
}

async function pullModel(name) {
  const btnId = 'pull-' + name.replace(':','-');
  const btn = g(btnId);
  if (btn) { btn.disabled=true; btn.innerHTML='<div class="spin"></div> Pulling...'; }
  toast(`Downloading ${name}... this may take a few minutes`, 'info');
  try {
    const r = await fetch(`${API}/api/llm/pull?model_name=${encodeURIComponent(name)}`, {method:'POST'});
    const d = await r.json();
    if (d.success) { toast(d.message, 'ok'); setTimeout(lsettings, 1000); }
    else toast(d.message || 'Pull failed', 'err');
  } catch { toast('Pull failed — ensure Ollama is running', 'err'); }
  if (btn) { btn.disabled=false; btn.innerHTML='Pull'; }
}

async function deleteModel(name) {
  if (!confirm(`Remove model "${name}"? This frees disk space but you'll need to re-pull it.`)) return;
  try {
    const r = await fetch(`${API}/api/llm/model?model_name=${encodeURIComponent(name)}`, {method:'DELETE'});
    const d = await r.json();
    if (d.success) { toast(d.message, 'ok'); lsettings(); }
    else toast(d.message || 'Delete failed', 'err');
  } catch { toast('Could not delete model', 'err'); }
}

function copyCmd(el) {
  const cmd = el.textContent.replace(/^\$ /, '').trim();
  navigator.clipboard.writeText(cmd).then(() => toast(`Copied: ${cmd}`, 'ok')).catch(() => {});
}

/* ─── init ─── */
document.addEventListener('DOMContentLoaded',()=>{
  hcheck();
  
  const hashPage = window.location.hash.substring(1);
  const validPages = [
    'overview', 'discover', 'apps', 'new', 'profile',
    'analytics', 'documents', 'settings',
    'vault', 'credentials', 'form-records',  // new pages
  ];
  const startPage = validPages.includes(hashPage) ? hashPage : 'overview';

  const navEl = document.querySelector(`.ni[onclick*="sp('${startPage}'"]`) || document.querySelector('.ni[onclick*="sp(\'overview\'"]');
  sp(startPage, navEl);

  window.addEventListener('hashchange', () => {
    const page = window.location.hash.substring(1);
    if(validPages.includes(page)) {
      const el = document.querySelector(`.ni[onclick*="sp('${page}'"]`);
      sp(page, el);
    }
  });

  document.addEventListener('keydown', e => {
    if(e.target && e.target.id === 'j-kw' && e.key === 'Enter') searchJobs();
  });
  
  setInterval(hcheck,30000);
  setInterval(lsettings, 60000);
});
/* ─── vault badge ─── */
async function loadVaultBadge(){
  try{
    const r = await fetch(API+'/api/vault/counts?user_id='+UID);
    const d = await r.json();
    const badge = document.getElementById('vault-cnt');
    if(!badge) return;
    const total = (d.counts||{}).all || 0;
    if(total > 0){ badge.textContent=total; badge.style.display=''; }
    else { badge.style.display='none'; }
  }catch(e){}
}
// refresh vault badge on page load and every 60s
loadVaultBadge();
setInterval(loadVaultBadge, 60000);
