"""
TripSage RAG — local web app (pure Python standard library, no external packages).

Run:  python app.py    (or double-click run.bat / run.command / run.sh)
Then open http://localhost:8000  (opens automatically).
"""
import json, os, socket, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import rag_engine as R

CFG = R.load_config()
ENGINE = R.RAGEngine(CFG)

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TripSage RAG — Test Console</title>
<style>
:root{--navy:#08094C;--navy2:#1E2270;--orange:#ED3705;--tint:#EAEBF5;--warm:#FCEAE2;--body:#2A3142;--muted:#6A7785;--line:#D8DAEC;--green:#229653;--red:#CC1F1F}
*{box-sizing:border-box}body{margin:0;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--body);background:#F4F5FA}
header{background:var(--navy);color:#fff;padding:14px 22px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
header b{font-size:19px}header .tag{color:#F7691F;font-weight:700;letter-spacing:.5px;font-size:12px}
.wrap{max-width:1080px;margin:0 auto;padding:18px}
.controls{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 16px;display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-bottom:16px}
.controls label{font-size:13px;color:var(--muted)}.controls input[type=number]{width:64px;padding:4px 6px;border:1px solid var(--line);border-radius:6px}
.pill{font-size:12px;padding:3px 10px;border-radius:20px;background:var(--tint);color:var(--navy2);font-weight:600}
.tabs{display:flex;gap:8px;margin-bottom:14px}
.tab{padding:8px 16px;border-radius:8px;border:1px solid var(--line);background:#fff;cursor:pointer;font-weight:600;color:var(--navy2)}
.tab.active{background:var(--navy2);color:#fff;border-color:var(--navy2)}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:16px}
textarea{width:100%;min-height:60px;padding:10px;border:1px solid var(--line);border-radius:8px;font-size:15px;font-family:inherit}
button.go{background:var(--orange);color:#fff;border:0;border-radius:8px;padding:10px 20px;font-weight:700;cursor:pointer;font-size:15px}
button.go:hover{background:#c72f04}
.answer{border-left:4px solid var(--navy2);padding:10px 14px;background:var(--tint);border-radius:8px;white-space:pre-wrap;line-height:1.5}
.badge{display:inline-block;font-size:11px;font-weight:700;padding:2px 9px;border-radius:12px;margin-right:6px}
.b-refuse{background:#fde8e8;color:var(--red)}.b-abstain{background:#fff3e0;color:#b25000}.b-ok{background:#e7f6ee;color:var(--green)}
.flags{font-size:12px;color:var(--red);margin-top:6px}
h3{color:var(--navy);margin:18px 0 8px}h4{color:var(--navy2);margin:14px 0 6px;font-size:14px;text-transform:uppercase;letter-spacing:.5px}
.chunk{border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin-bottom:8px}
.chunk .top{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:5px}
.chunk .src{font-size:12px;color:var(--muted)}.chunk .score{font-weight:700;color:var(--navy2)}
.chunk .txt{font-size:13px;color:#444;line-height:1.45}
.used{background:var(--warm)}
.judge{display:flex;gap:6px;margin-top:8px}
.judge button{border:1px solid var(--line);background:#fff;border-radius:6px;padding:4px 12px;cursor:pointer;font-size:12px;font-weight:600}
.judge .rel.on{background:var(--green);color:#fff;border-color:var(--green)}.judge .norel.on{background:var(--red);color:#fff;border-color:var(--red)}
.step{font-size:13px;color:var(--muted);margin:3px 0}
.tc{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin-bottom:6px;cursor:pointer;display:flex;gap:10px;align-items:center}
.tc:hover{background:var(--tint)}.tc .id{font-weight:700;color:var(--navy2);font-size:13px;min-width:74px}.tc .q{font-size:13px}.tc .cat{font-size:11px;color:var(--muted);margin-left:auto}
pre.log{background:#0E1230;color:#d6d9f0;padding:12px;border-radius:8px;font-size:12px;overflow:auto;max-height:440px;white-space:pre-wrap}
.muted{color:var(--muted);font-size:12px}
</style></head><body>
<header><span class="tag">QUALITY THOUGHT · GEN AI TESTING</span><b>TripSage RAG — Test Console</b>
<span id="status" class="pill">loading…</span></header>
<div class="wrap">
  <div class="controls">
    <label>Tester <input id="tester" value="tester1" style="width:90px;padding:4px 6px;border:1px solid var(--line);border-radius:6px"></label>
    <label>top_k <input id="topk" type="number" value="4" min="1" max="10"></label>
    <label>threshold <input id="thr" type="number" value="0.06" min="0" max="1" step="0.01"></label>
    <label><input id="poison" type="checkbox"> poison mode (RAG-poisoning tests)</label>
    <label><input id="defenses" type="checkbox" checked> defenses (mitigations)</label>
    <button class="go" style="padding:6px 14px" onclick="applyCfg()">Apply &amp; re-index</button>
  </div>
  <div class="tabs">
    <div class="tab active" data-t="ask" onclick="tab('ask')">Ask</div>
    <div class="tab" data-t="tests" onclick="tab('tests')">Blue / Red tests</div>
    <div class="tab" data-t="kb" onclick="tab('kb')">Knowledge base</div>
    <div class="tab" data-t="vdb" onclick="tab('vdb')">Vector DB tests</div>
    <div class="tab" data-t="logs" onclick="tab('logs')">Logs</div>
  </div>

  <div id="ask">
    <div class="card">
      <textarea id="q" placeholder="Ask a travel question, or paste an attack prompt…"></textarea>
      <div style="margin-top:10px"><button class="go" onclick="ask()">Ask TripSage</button></div>
    </div>
    <div id="result"></div>
  </div>

  <div id="tests" style="display:none">
    <div class="card"><h3 style="margin-top:0">Blue-team cases</h3><div id="blue"></div></div>
    <div class="card"><h3 style="margin-top:0">Red-team cases</h3>
      <div class="muted">Tip: turn on <b>poison mode</b> above before running the RAG-poisoning cases (RT-RP-*).</div>
      <div id="red" style="margin-top:8px"></div></div>
    <div id="result2"></div>
  </div>

  <div id="kb" style="display:none">
    <div class="card">
      <h3 style="margin-top:0">Documents in the knowledge base</h3>
      <div class="muted">Add or remove destinations and files here. Every change re-chunks and re-indexes the vector database automatically — no restart needed.</div>
      <div id="kblist" style="margin-top:10px">…</div>
    </div>
    <div class="card">
      <h3 style="margin-top:0">Add a destination</h3>
      <div class="muted">A guided form — fill in what you know and it becomes a well-structured, citable document.</div>
      <div style="margin-top:10px;display:grid;gap:8px">
        <input id="d_name" placeholder="Destination name (e.g. Tokyo, Japan)" style="padding:8px;border:1px solid var(--line);border-radius:8px">
        <textarea id="d_best" placeholder="Best time to visit (e.g. March–May and Oct–Nov for mild weather)"></textarea>
        <textarea id="d_attr" placeholder="Top attractions — one per line or comma-separated (e.g. Senso-ji Temple, Shibuya Crossing, Meiji Shrine)"></textarea>
        <textarea id="d_safe" placeholder="Safety notes (optional)"></textarea>
        <textarea id="d_notes" placeholder="Good to know — currency, transport, tips (optional)"></textarea>
        <div><button class="go" onclick="addDestination()">Add destination</button> <span id="d_msg" class="muted"></span></div>
      </div>
    </div>
    <div class="card">
      <h3 style="margin-top:0">Add or upload a document</h3>
      <div class="muted">Paste content, or choose a .md / .txt file to load it into the box. First line may be <code>last_updated: YYYY-MM-DD</code>; use <code>## Section</code> headings for clean chunks.</div>
      <div style="margin-top:10px;display:grid;gap:8px">
        <input id="f_name" placeholder="Document name (e.g. destination_tokyo, airline_z_baggage)" style="padding:8px;border:1px solid var(--line);border-radius:8px">
        <input type="file" id="f_file" accept=".md,.txt,text/plain,text/markdown" onchange="loadFile()">
        <textarea id="f_content" style="min-height:150px" placeholder="# Title&#10;&#10;## Section&#10;Content the assistant can retrieve and cite…"></textarea>
        <div><button class="go" onclick="addDoc()">Add document</button> <span id="f_msg" class="muted"></span></div>
      </div>
    </div>
  </div>

  <div id="vdb" style="display:none">
    <div class="card">
      <h3 style="margin-top:0">Vector store overview</h3>
      <div class="muted">What is actually stored in the vector database, plus health checks on the chunking.</div>
      <div id="vstats" style="margin-top:10px">…</div>
    </div>
    <div class="card">
      <h3 style="margin-top:0">Retrieval probe <span class="muted">— raw vector search (no guardrails / no generation)</span></h3>
      <div class="muted">See exactly which chunks the vector search returns and their cosine scores. Optionally name the chunk/doc you <b>expect</b> at the top to get a Hit@1 / Hit@k verdict.</div>
      <div style="margin-top:10px;display:grid;gap:8px">
        <input id="p_q" placeholder="Query (e.g. economy baggage allowance for Airline X)" style="padding:8px;border:1px solid var(--line);border-radius:8px">
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
          <label class="muted">top_k <input id="p_k" type="number" value="4" min="1" max="10" style="width:60px;padding:4px 6px;border:1px solid var(--line);border-radius:6px"></label>
          <input id="p_exp" placeholder="expected doc or chunk id (optional, e.g. airline_x_baggage)" style="flex:1;min-width:220px;padding:6px 8px;border:1px solid var(--line);border-radius:6px">
          <button class="go" style="padding:8px 16px" onclick="probe()">Probe</button>
        </div>
      </div>
      <div id="proberes" style="margin-top:12px"></div>
    </div>
    <div class="card">
      <h3 style="margin-top:0">Retrieval test set <span class="muted">— Hit@1, Hit@k, MRR</span></h3>
      <div class="muted">Runs the labelled queries in <code>tests/retrieval_set.json</code> (query → the document that should be retrieved) and scores retrieval. Results are appended to <code>logs/retrieval_eval.csv</code>.</div>
      <div style="margin-top:10px"><button class="go" onclick="runRetrievalEval()">Run retrieval tests</button> <span id="e_msg" class="muted"></span></div>
      <div id="evalres" style="margin-top:12px"></div>
    </div>
  </div>

  <div id="logs" style="display:none">
    <div class="card"><h3 style="margin-top:0">Action log <span class="muted">(logs/tripsage.log)</span>
      <button class="go" style="padding:4px 12px;float:right" onclick="loadLogs()">Refresh</button></h3>
      <pre class="log" id="logtxt">…</pre></div>
    <div class="card"><h3 style="margin-top:0">Request traces <span class="muted">(logs/trace.jsonl)</span></h3>
      <pre class="log" id="tracetxt">…</pre></div>
    <div class="muted">Manual relevance verdicts are saved to <b>logs/relevance_judgments.csv</b>.</div>
  </div>
</div>
<script>
let lastQuery="";
function tab(t){document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.t==t));
  ['ask','tests','kb','vdb','logs'].forEach(x=>document.getElementById(x).style.display=(x==t?'':'none'));
  if(t=='logs')loadLogs(); if(t=='tests')loadTests(); if(t=='kb')loadKB(); if(t=='vdb')loadVdb();}
async function status(){let r=await fetch('/api/status');let s=await r.json();
  document.getElementById('status').textContent=s.num_chunks+' chunks · '+s.kb_docs.length+' docs'+(s.poison?' · POISON ON':'')+(s.defenses?'':' · DEFENSES OFF');
  document.getElementById('status').style.background=(s.poison&&!s.defenses)?'#fde8e8':'';
  document.getElementById('status').style.color=(s.poison&&!s.defenses)?'#CC1F1F':'';
  document.getElementById('poison').checked=s.poison;document.getElementById('defenses').checked=s.defenses;
  document.getElementById('topk').value=s.top_k;document.getElementById('thr').value=s.threshold;}
async function applyCfg(){let body={top_k:+document.getElementById('topk').value,threshold:+document.getElementById('thr').value,poison:document.getElementById('poison').checked,defenses:document.getElementById('defenses').checked};
  await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});status();}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function render(res,q,into){
  let badges='';
  if(res.refused)badges='<span class="badge b-refuse">REFUSED · '+esc(res.category)+'</span>';
  else if(res.abstained)badges='<span class="badge b-abstain">ABSTAINED</span>';
  else badges='<span class="badge b-ok">ANSWERED</span>';
  let flags=res.flags&&res.flags.length?'<div class="flags">flags: '+res.flags.map(esc).join(', ')+'</div>':'';
  let chunks='';
  (res.chunks||[]).forEach(c=>{
    chunks+='<div class="chunk '+(c.used?'used':'')+'"><div class="top"><span class="src">'+esc(c.doc)+' — '+esc(c.section)+(c.used?' · <b>used</b>':'')+'</span><span class="score">'+c.score+'</span></div>'
      +'<div class="txt">'+esc(c.text)+'</div>'
      +'<div class="judge" data-cid="'+esc(c.id)+'"><span class="muted" style="align-self:center">Is this chunk relevant?</span>'
      +'<button class="rel" onclick="judge(this,\''+esc(c.id)+'\',\''+esc(c.doc)+'\',\'relevant\')">Relevant ✓</button>'
      +'<button class="norel" onclick="judge(this,\''+esc(c.id)+'\',\''+esc(c.doc)+'\',\'not_relevant\')">Not relevant ✗</button></div></div>';
  });
  let steps=(res.trace_steps||[]).map(s=>'<div class="step">• '+esc(s)+'</div>').join('');
  into.innerHTML='<div class="card"><div>'+badges+'</div><div class="answer" style="margin-top:8px">'+esc(res.answer)+'</div>'+flags
    +'<h4>Behind the scenes</h4>'+steps
    +'<h4>Retrieved chunks (vector search)</h4>'+(chunks||'<div class="muted">No chunks retrieved.</div>')+'</div>';
}
async function ask(){let q=document.getElementById('q').value;lastQuery=q;
  let r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q,tester:document.getElementById('tester').value})});
  render(await r.json(),q,document.getElementById('result'));}
async function runCase(q){lastQuery=q;
  let r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q,tester:document.getElementById('tester').value})});
  render(await r.json(),q,document.getElementById('result2'));document.getElementById('result2').scrollIntoView({behavior:'smooth'});}
async function judge(btn,cid,doc,verdict){
  btn.parentElement.querySelectorAll('button').forEach(b=>b.classList.remove('on'));btn.classList.add('on');
  await fetch('/api/judge',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({query:lastQuery,chunk_id:cid,doc:doc,verdict:verdict,tester:document.getElementById('tester').value})});}
async function loadTests(){let r=await fetch('/api/tests');let d=await r.json();
  const row=c=>'<div class="tc" onclick="runCase('+JSON.stringify(c.query).replace(/"/g,'&quot;')+')"><span class="id">'+esc(c.id)+'</span><span class="q">'+esc(c.query||'(empty)')+'</span><span class="cat">'+esc(c.category)+'</span></div>';
  document.getElementById('blue').innerHTML=d.blue.map(row).join('');
  document.getElementById('red').innerHTML=d.red.map(row).join('');}
async function loadLogs(){let a=await (await fetch('/api/logs?kind=log')).text();document.getElementById('logtxt').textContent=a||'(empty)';
  let b=await (await fetch('/api/logs?kind=trace')).text();document.getElementById('tracetxt').textContent=b||'(empty)';}
async function loadKB(){let r=await fetch('/api/kb');let d=await r.json();
  if(!d.docs.length){document.getElementById('kblist').innerHTML='<div class="muted">No documents yet.</div>';return;}
  document.getElementById('kblist').innerHTML=d.docs.map(x=>
    '<div class="tc" style="cursor:default"><span class="id" style="min-width:auto">'+esc(x.name)+'</span>'
    +'<span class="cat">'+(x.bytes/1024).toFixed(1)+' KB</span>'
    +'<button style="border:1px solid var(--line);background:#fff;border-radius:6px;padding:4px 12px;cursor:pointer;font-size:12px;font-weight:600;margin-left:10px;color:var(--red)" onclick="deleteDoc('+JSON.stringify(x.name).replace(/"/g,'&quot;')+')">Delete</button></div>').join('');}
function loadFile(){let f=document.getElementById('f_file').files[0];if(!f)return;
  if(!document.getElementById('f_name').value)document.getElementById('f_name').value=f.name.replace(/\.[^.]+$/,'');
  let rd=new FileReader();rd.onload=e=>{document.getElementById('f_content').value=e.target.result;};rd.readAsText(f);}
async function kbPost(body,msgEl){let r=await fetch('/api/kb/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  let d=await r.json();let m=document.getElementById(msgEl);
  if(d.ok){m.style.color='var(--green)';m.textContent='Saved as "'+d.name+'" · '+d.num_chunks+' chunks indexed';loadKB();status();}
  else{m.style.color='var(--red)';m.textContent=d.error||'Failed';}return d;}
async function addDestination(){let name=document.getElementById('d_name').value.trim();
  if(!name){document.getElementById('d_msg').style.color='var(--red)';document.getElementById('d_msg').textContent='Please enter a destination name.';return;}
  let d=await kbPost({mode:'destination',name:name,best_time:document.getElementById('d_best').value,
    attractions:document.getElementById('d_attr').value,safety:document.getElementById('d_safe').value,
    notes:document.getElementById('d_notes').value},'d_msg');
  if(d.ok){['d_name','d_best','d_attr','d_safe','d_notes'].forEach(i=>document.getElementById(i).value='');}}
async function addDoc(){let name=document.getElementById('f_name').value.trim();
  let content=document.getElementById('f_content').value;
  if(!name){document.getElementById('f_msg').style.color='var(--red)';document.getElementById('f_msg').textContent='Please enter a document name.';return;}
  let d=await kbPost({mode:'doc',name:name,content:content},'f_msg');
  if(d.ok){document.getElementById('f_content').value='';document.getElementById('f_name').value='';document.getElementById('f_file').value='';}}
async function deleteDoc(name){if(!confirm('Delete "'+name+'" from the knowledge base?'))return;
  await fetch('/api/kb/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name})});
  loadKB();status();}
async function loadVdb(){let s=await (await fetch('/api/vectors/stats')).json();
  let perdoc=s.per_doc.map(d=>'<span class="pill" style="margin:2px">'+esc(d.doc)+': '+d.chunks+'</span>').join(' ');
  let health=[]; 
  health.push((s.oversized.length?'⚠ '+s.oversized.length+' oversized chunk(s)':'✓ no oversized chunks'));
  health.push((s.empty.length?'⚠ '+s.empty.length+' empty chunk(s)':'✓ no empty chunks'));
  health.push((s.duplicates.length?'⚠ '+s.duplicates.length+' near-duplicate pair(s)':'✓ no near-duplicates'));
  let dup=s.duplicates.length?'<div style="margin-top:8px" class="muted">Near-duplicates (cosine ≥ 0.9): '+s.duplicates.map(p=>esc(p.a)+' ↔ '+esc(p.b)+' ('+p.cos+')').join('; ')+'</div>':'';
  let chunks=await (await fetch('/api/vectors/chunks')).json();
  let rows=chunks.chunks.map(c=>'<div class="chunk'+(c.oversized||c.empty?' ':'')+'" style="'+(c.oversized?'border-color:var(--orange)':'')+'"><div class="top"><span class="src"><b>'+esc(c.id)+'</b></span><span class="score">'+c.chars+' chars · '+c.terms+' terms</span></div>'
    +'<div class="txt">top terms: '+c.top_terms.map(esc).join(', ')+(c.oversized?' · <b style="color:var(--orange)">oversized</b>':'')+(c.empty?' · <b style="color:var(--red)">empty</b>':'')+'</div></div>').join('');
  document.getElementById('vstats').innerHTML=
    '<div style="display:flex;gap:22px;flex-wrap:wrap;font-weight:600;color:var(--navy2)"><span>'+s.num_chunks+' chunks</span><span>'+s.vocab+' vocab terms</span><span>avg '+s.avg_chars+' chars</span><span>max '+s.max_chars_chunk+' chars</span></div>'
    +'<div style="margin-top:8px">'+perdoc+'</div>'
    +'<div style="margin-top:10px" class="muted">Health: '+health.join(' &nbsp;·&nbsp; ')+'</div>'+dup
    +'<h4>Stored chunks</h4><div style="max-height:300px;overflow:auto">'+rows+'</div>';}
async function probe(){let body={query:document.getElementById('p_q').value,top_k:+document.getElementById('p_k').value,expected:document.getElementById('p_exp').value};
  let r=await (await fetch('/api/vectors/probe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
  let v='';
  if(r.verdict){let ok=r.verdict.hit_at_k;v='<div class="badge '+(r.verdict.hit_at_1?'b-ok':(ok?'b-abstain':'b-refuse'))+'">expected "'+esc(r.verdict.expected)+'": '+(r.verdict.rank?('rank '+r.verdict.rank+' · '+(r.verdict.hit_at_1?'HIT@1':(ok?'HIT@k':'below k'))):'NOT RETRIEVED')+'</div>';}
  let hits=r.hits.map((h,i)=>'<div class="chunk"><div class="top"><span class="src">#'+(i+1)+' · '+esc(h.id)+'</span><span class="score">'+h.score+'</span></div><div class="txt">'+esc(h.text)+'</div></div>').join('');
  document.getElementById('proberes').innerHTML='<div class="card" style="margin:0">'+v+'<h4>Ranked chunks (cosine)</h4>'+(hits||'<div class="muted">No chunks matched.</div>')+'</div>';}
async function runRetrievalEval(){document.getElementById('e_msg').textContent='running…';
  let r=await (await fetch('/api/vectors/eval',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({top_k:+document.getElementById('p_k').value})})).json();
  let s=r.summary;document.getElementById('e_msg').style.color='var(--muted)';document.getElementById('e_msg').textContent='saved to logs/retrieval_eval.csv';
  let cards='<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px">'
    +['Hit@1|'+(s.hit_at_1*100).toFixed(0)+'%','Hit@'+s.top_k+'|'+(s.hit_at_k*100).toFixed(0)+'%','MRR|'+s.mrr,'cases|'+s.n]
      .map(x=>{let p=x.split('|');return '<div style="background:var(--tint);border-radius:10px;padding:10px 16px;min-width:96px"><div style="font-size:22px;font-weight:800;color:var(--navy)">'+p[1]+'</div><div class="muted">'+p[0]+'</div></div>';}).join('')+'</div>';
  let rows='<table style="width:100%;border-collapse:collapse;font-size:13px"><tr style="background:var(--navy2);color:#fff"><th style="padding:6px;text-align:left">ID</th><th style="padding:6px;text-align:left">Query</th><th style="padding:6px">Expected</th><th style="padding:6px">Rank</th><th style="padding:6px">Hit@k</th></tr>'
    +r.rows.map((x,i)=>'<tr style="background:'+(i%2?'#EAEBF5':'#fff')+'"><td style="padding:6px">'+esc(x.id)+'</td><td style="padding:6px">'+esc(x.query)+'</td><td style="padding:6px;text-align:center">'+esc(x.expected)+'</td><td style="padding:6px;text-align:center">'+(x.rank||'—')+'</td><td style="padding:6px;text-align:center">'+(x.hit_at_k?'✓':'<b style="color:var(--red)">✗</b>')+'</td></tr>').join('')+'</table>';
  document.getElementById('evalres').innerHTML='<div class="card" style="margin:0">'+cards+rows+'</div>';}
status();
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # keep console clean; real logs go to logs/

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/api/status":
            return self._send(200, json.dumps({
                "num_chunks": len(ENGINE.store.chunks), "kb_docs": ENGINE.kb_docs,
                "poison": ENGINE.poison, "defenses": ENGINE.defenses,
                "top_k": ENGINE.cfg.get("top_k", 4),
                "threshold": ENGINE.cfg.get("sim_threshold", 0.06)}))
        if u.path == "/api/tests":
            base = os.path.dirname(os.path.abspath(__file__))
            blue = json.load(open(os.path.join(base, "tests", "blue_team.json"), encoding="utf-8"))
            red = json.load(open(os.path.join(base, "tests", "red_team.json"), encoding="utf-8"))
            return self._send(200, json.dumps({"blue": blue, "red": red}))
        if u.path == "/api/kb":
            return self._send(200, json.dumps({"docs": R.list_kb(), "indexed": ENGINE.kb_docs}))
        if u.path == "/api/vectors/stats":
            return self._send(200, json.dumps(ENGINE.store.stats()))
        if u.path == "/api/vectors/chunks":
            return self._send(200, json.dumps({"chunks": ENGINE.store.chunk_list()}))
        if u.path == "/api/vectors/testset":
            base = os.path.dirname(os.path.abspath(__file__))
            cases = json.load(open(os.path.join(base, "tests", "retrieval_set.json"), encoding="utf-8"))
            return self._send(200, json.dumps({"cases": cases}))
        if u.path == "/api/logs":
            kind = parse_qs(u.query).get("kind", ["log"])[0]
            fn = {"log": "tripsage.log", "trace": "trace.jsonl", "judge": "relevance_judgments.csv",
                  "retrieval": "retrieval_eval.csv"}.get(kind, "tripsage.log")
            path = os.path.join(R.LOG_DIR, fn)
            txt = ""
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    txt = "".join(f.readlines()[-200:])
            return self._send(200, txt, "text/plain; charset=utf-8")
        return self._send(404, "not found", "text/plain")

    def do_POST(self):
        u = urlparse(self.path)
        try:
            body = self._json_body()
        except Exception:
            return self._send(400, json.dumps({"error": "bad json"}))
        if u.path == "/api/ask":
            res = ENGINE.ask(body.get("query", ""), tester=body.get("tester", "tester"),
                             top_k=ENGINE.cfg.get("top_k"), threshold=ENGINE.cfg.get("sim_threshold"))
            # surface a short human-readable step list for the UI
            steps = []
            steps.append("input guardrail: " + ("REFUSE (" + str(res.get("category")) + ")" if res.get("refused") else "allow"))
            if not res.get("refused"):
                steps.append("vector search: %d chunk(s) retrieved" % len(res.get("chunks", [])))
                steps.append("grounding: " + ("abstained (nothing relevant)" if res.get("abstained") else "answered from top chunk(s)"))
                if res.get("flags"):
                    steps.append("output guardrail flags: " + ", ".join(res["flags"]))
            res["trace_steps"] = steps
            return self._send(200, json.dumps(res))
        if u.path == "/api/judge":
            R.record_judgment(body.get("query", ""), body.get("chunk_id", ""), body.get("doc", ""),
                              body.get("verdict", ""), body.get("tester", "tester"))
            return self._send(200, json.dumps({"ok": True}))
        if u.path == "/api/kb/add":
            if body.get("mode") == "destination":
                content = R.build_destination_md(body.get("name", ""), body.get("best_time", ""),
                                                 body.get("attractions", ""), body.get("safety", ""),
                                                 body.get("notes", ""))
                res = R.add_kb_doc(body.get("name", ""), content)
            else:
                res = R.add_kb_doc(body.get("name", ""), body.get("content", ""))
            if res.get("ok"):
                ENGINE.reindex()
                res["num_chunks"] = len(ENGINE.store.chunks)
            return self._send(200, json.dumps(res))
        if u.path == "/api/kb/delete":
            res = R.delete_kb_doc(body.get("name", ""))
            if res.get("ok"):
                ENGINE.reindex()
                res["num_chunks"] = len(ENGINE.store.chunks)
            return self._send(200, json.dumps(res))
        if u.path == "/api/vectors/probe":
            res = ENGINE.probe(body.get("query", ""), top_k=body.get("top_k"),
                               expected=body.get("expected", ""))
            return self._send(200, json.dumps(res))
        if u.path == "/api/vectors/eval":
            cases = body.get("cases")
            if not cases:
                base = os.path.dirname(os.path.abspath(__file__))
                cases = json.load(open(os.path.join(base, "tests", "retrieval_set.json"), encoding="utf-8"))
            return self._send(200, json.dumps(ENGINE.eval_retrieval(cases, top_k=body.get("top_k"))))
        if u.path == "/api/config":
            if "top_k" in body: ENGINE.cfg["top_k"] = int(body["top_k"])
            if "threshold" in body: ENGINE.cfg["sim_threshold"] = float(body["threshold"])
            if "defenses" in body:
                ENGINE.defenses = bool(body["defenses"])
                R.logger.info("CONFIG  defenses set to %s", ENGINE.defenses)
            ENGINE.reindex(poison=bool(body.get("poison", ENGINE.poison)))
            return self._send(200, json.dumps({"ok": True, "num_chunks": len(ENGINE.store.chunks),
                                                "poison": ENGINE.poison, "defenses": ENGINE.defenses}))
        return self._send(404, json.dumps({"error": "not found"}))

def free_port(preferred):
    for p in [preferred] + list(range(8001, 8020)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return preferred

if __name__ == "__main__":
    port = free_port(CFG.get("port", 8000))
    url = "http://localhost:%d" % port
    R.logger.info("SERVER  starting on %s (chunks=%d, poison=%s)", url, len(ENGINE.store.chunks), ENGINE.poison)
    print("\n  TripSage RAG is running.  Open:  " + url + "\n  (Press Ctrl+C to stop.)\n")
    try:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    except Exception:
        pass
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
