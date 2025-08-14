const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const tableBody = document.querySelector('#assets tbody');

function fmtRes(r){
  if (!r.width || !r.height) return '';
  return `${r.width}×${r.height}`;
}

function fmtDur(r){
  if (!r.duration_sec) return '';
  const s = Math.round(r.duration_sec);
  const m = Math.floor(s/60), ss = s%60;
  return `${m}:${String(ss).padStart(2,'0')}`;
}

async function scan(){
  const res = await fetch('/api/scan');
  const data = await res.json();
  if (!res.ok && data.error) {
    alert(data.error);
    tableBody.innerHTML = '';
    return;
  }
  renderRows(data.records || []);
}

function renderRows(recs){
  tableBody.innerHTML = '';
  for (const r of recs){
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="checkbox" class="sel" data-path="${r.path}"></td>
      <td title="${r.name}">${r.name}</td>
      <td>${r.fps ? Number(r.fps).toFixed(3) : ''}</td>
      <td>${r.codec ?? ''}</td>
      <td>${fmtRes(r)}</td>
      <td>${fmtDur(r)}</td>
      <td>${r.has_audio ? 'Yes' : 'No'}</td>
      <td title="${r.path}">${r.path}</td>
      <td>${r.created_iso ?? ''}</td>
      <td>${r.modified_iso ?? ''}</td>
    `;
    tableBody.appendChild(tr);
  }
}

function selectedPaths(){
  return $$('.sel:checked').map(el => el.dataset.path);
}

async function postJSON(url, body){
  const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  return await res.json();
}

$('#refresh').addEventListener('click', scan);
$('#checkAll').addEventListener('click', ()=> $$('.sel').forEach(el=> el.checked = true));
$('#uncheckAll').addEventListener('click', ()=> $$('.sel').forEach(el=> el.checked = false));

$('#approve').addEventListener('click', async ()=>{
  const paths = selectedPaths();
  if (!paths.length) return alert('No files selected');
  const out = await postJSON('/api/move', {action:'approve', paths});
  alert(out.error || `Moved ${out.moved.length} files`);
  await scan();
});

$('#quarantine').addEventListener('click', async ()=>{
  const paths = selectedPaths();
  if (!paths.length) return alert('No files selected');
  const out = await postJSON('/api/move', {action:'quarantine', paths});
  alert(out.error || `Moved ${out.moved.length} files`);
  await scan();
});

$('#makeProxy').addEventListener('click', async ()=>{
  const paths = selectedPaths();
  if (!paths.length) return alert('No files selected');
  const resFactor = parseInt($('#resFactor').value, 10);
  const alphaEnable = $('#alphaEnable').checked;
  const out = await postJSON('/api/proxy', {paths, res_factor: resFactor, alpha: alphaEnable});
  addJob(out.job_id);
});

$('#extractAudio').addEventListener('click', async ()=>{
  const paths = selectedPaths();
  if (!paths.length) return alert('No files selected');
  const out = await postJSON('/api/extract-audio', {paths});
  addJob(out.job_id);
});

$('#sync').addEventListener('click', async ()=>{
  const res = await postJSON('/api/sync-sheets', {});
  alert(res.error || `Synced ${res.count} records to Google Sheet`);
});

function addJob(id){
  const div = document.createElement('div');
  div.dataset.jobId = id;
  div.textContent = `Job ${id}: queued`;
  $('#jobs').appendChild(div);
  pollJob(div, id);
}

async function pollJob(el, id){
  const t = setInterval(async ()=>{
    const res = await fetch(`/api/jobs/${id}`);
    const data = await res.json();
    el.textContent = `Job ${id}: ${data.status}` + (data.outputs ? ` -> ${data.outputs.length} outputs` : '');
    if (data.status === 'done') clearInterval(t);
  }, 1500);
}

scan();