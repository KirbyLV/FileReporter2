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
  let res, text, data;
  try {
    res = await fetch('/api/scan');
    text = await res.text();
    data = JSON.parse(text);
  } catch (e) {
    alert('Scan failed.'); 
    console.error(e, text);
    tableBody.innerHTML = '';
    return;
  }
  if (!res.ok) {
    alert((data && data.error) || 'Scan error.');
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
  const res = await fetch(url, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body)
  });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { error: text }; }
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

$('#refresh').addEventListener('click', scan);
$('#checkAll').addEventListener('click', ()=> $$('.sel').forEach(el=> el.checked = true));
$('#uncheckAll').addEventListener('click', ()=> $$('.sel').forEach(el=> el.checked = false));

function clearSelections(){ $$('.sel:checked').forEach(cb => cb.checked = false); }

$('#approve').addEventListener('click', async ()=>{
  const paths = selectedPaths();
  if (!paths.length) return alert('No files selected');
  const res = await postJSON('/api/move-async', {action:'approve', paths});
  addMoveJob(res.job_id, paths.length, 'Approving');
  clearSelections(); // optional
});

$('#quarantine').addEventListener('click', async ()=>{
  const paths = selectedPaths();
  if (!paths.length) return alert('No files selected');
  const res = await postJSON('/api/move-async', {action:'quarantine', paths});
  addMoveJob(res.job_id, paths.length, 'Quarantining');
  clearSelections(); // optional
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

function addMoveJob(jobId, total, label){
  const div = document.createElement('div');
  div.dataset.jobId = jobId;
  div.className = 'job';
  div.dataset.errCount = "0";
  div.innerHTML = `
    <div class="job-head"><strong>${label}</strong>: <span class="job-count">0/${total}</span></div>
    <div class="job-progress"><div class="bar" style="width:0%"></div></div>
    <details class="job-errors-wrap" hidden>
      <summary>Errors (<span class="job-error-count">0</span>)</summary>
      <ul class="job-errors"></ul>
    </details>
  `;
  $('#jobs').appendChild(div);
  pollMoveJob(div, jobId, total, label);
}

function pollMoveJob(el, id, total, label){
  const countEl = el.querySelector('.job-count');
  const barEl   = el.querySelector('.bar');
  const errsWrap= el.querySelector('.job-errors-wrap');
  const errsCountEl = el.querySelector('.job-error-count');
  const errsList= el.querySelector('.job-errors');

  const t = setInterval(async ()=>{
    const res = await fetch(`/api/jobs/${id}`);
    const data = await res.json();

    if (!data || !data.status) return;

    const moved = data.moved ?? 0;
    const errs  = Array.isArray(data.errors) ? data.errors : [];

    // progress + count
    countEl.textContent = `${moved}/${total}`;
    const pct = total > 0 ? Math.round((moved/total)*100) : 0;
    barEl.style.width = `${pct}%`;

    // errors
    const prevErrCount = parseInt(el.dataset.errCount || "0", 10);
    if (errs.length !== prevErrCount) {
      // update list only when changed
      errsList.innerHTML = '';
      errs.forEach(msg => {
        const li = document.createElement('li');
        li.textContent = msg;
        errsList.appendChild(li);
      });
      errsCountEl.textContent = String(errs.length);
      el.dataset.errCount = String(errs.length);
      errsWrap.hidden = errs.length === 0;
    }

    // terminal states
    if (data.status === 'done' || data.status === 'done_with_errors') {
      clearInterval(t);
      // final fill (in case the last step was fast)
      barEl.style.width = '100%';
      // refresh table after completion
      await scan();
    }
  }, 1200);
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


(function attachSortableHeaders(){
  function init() {
    const table = document.getElementById('assets');
    if (!table) return false;

    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');
    if (!thead || !tbody) return false;

    const headers = Array.from(thead.querySelectorAll('th'));
    headers.forEach((th, colIdx) => {
      // Skip the checkbox column (first col)
      if (colIdx === 0) return;

      // Avoid double-binding
      if (th.dataset.sortBound === "1") return;
      th.dataset.sortBound = "1";

      th.addEventListener('click', () => {
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const isAsc = th.classList.contains('asc');
        const dir = isAsc ? -1 : 1;

        // reset other headers' state
        headers.forEach(h => { h.classList.remove('asc','desc'); });

        // toggle this header’s state
        th.classList.add(isAsc ? 'desc' : 'asc');

        // pick extractors for numeric-ish columns
        const getCell = (tr) => tr.children[colIdx]?.textContent?.trim() ?? "";

        const sorted = rows.sort((a, b) => {
          const A = getCell(a), B = getCell(b);

          // numeric-aware compare
          const aNum = Number(A.replace(/[^0-9.\-]/g, ''));
          const bNum = Number(B.replace(/[^0-9.\-]/g, ''));
          const bothNums = !Number.isNaN(aNum) && !Number.isNaN(bNum);

          if (bothNums) return (aNum - bNum) * dir;

          // ISO date friendly compare (your created/modified look ISO-ish)
          const aDate = Date.parse(A), bDate = Date.parse(B);
          const bothDates = !Number.isNaN(aDate) && !Number.isNaN(bDate);
          if (bothDates) return (aDate - bDate) * dir;

          // fallback to localeCompare (numeric option helps with 2 vs 10)
          return A.localeCompare(B, undefined, { numeric: true, sensitivity: 'base' }) * dir;
        });

        // reattach in sorted order
        const frag = document.createDocumentFragment();
        sorted.forEach(tr => frag.appendChild(tr));
        tbody.innerHTML = '';
        tbody.appendChild(frag);
      });
    });

    return true;
  }

  // Run after initial load and also after your Scan re-renders rows
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // If your app re-renders headers dynamically in the future, call init() again.
})();

