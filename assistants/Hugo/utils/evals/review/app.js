let scenarios = [];
let current = null;
let currentVerdict = null;

async function loadList() {
  scenarios = await (await fetch('/api/scenarios')).json();
  document.getElementById('listHeading').textContent = 'Flagged for Review';
  document.getElementById('searchHint').textContent = '';
  renderList();
  renderProgress();
}

async function runSearch(query) {
  if (!query.trim()) { loadList(); return; }
  scenarios = await (await fetch('/api/search?q=' + encodeURIComponent(query))).json();
  document.getElementById('listHeading').textContent = 'Search Results';
  document.getElementById('searchHint').textContent =
    `${scenarios.length} match${scenarios.length === 1 ? '' : 'es'} across all conversations`;
  renderList();
  renderProgress();
}

function renderProgress() {
  const total = scenarios.length;
  const done = scenarios.filter(s => s.verdict).length;
  const ok = scenarios.filter(s => s.verdict === 'approve').length;
  const minor = scenarios.filter(s => s.verdict === 'minor').length;
  const needs = scenarios.filter(s => s.verdict === 'needs').length;
  document.getElementById('progress').textContent =
    `${done}/${total} reviewed · ${ok} approve · ${minor} minor · ${needs} needs`;
}

function itemMarkup(s) {
  const div = document.createElement('div');
  div.className = 'item' + (current === s.id ? ' active' : '');
  const dot = s.verdict || '';
  const kind = s.kind ? chip(s.kind, s.kind.toLowerCase()) : '';
  div.innerHTML = `<div class="id"><span class="dot ${dot}"></span>${s.id}${kind}</div>` +
                  `<div class="sub">${esc(s.title)}</div>`;
  div.onclick = () => loadScenario(s.id);
  return div;
}

function renderList() {
  const list = document.getElementById('list');
  list.innerHTML = '';
  for (const s of scenarios) list.appendChild(itemMarkup(s));
}

async function loadScenario(id) {
  current = id;
  renderList();
  const c = await (await fetch('/api/scenario/' + encodeURIComponent(id))).json();
  const fb = await (await fetch('/api/feedback/' + encodeURIComponent(id))).json();
  renderScenario(c, fb);
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));
}

function chip(text, cls = '') { return `<span class="chip ${cls}">${esc(text)}</span>`; }

// "P1: clear + conversational" -> {label:"Persona 1", rest:"clear + conversational"}
function spell(raw, word) {
  const m = String(raw || '').match(/^[A-Z](\d+):\s*(.*)$/);
  if (!m) return { label: word, rest: raw || '' };
  return { label: `${word} ${m[1]}`, rest: m[2] };
}

function metaTag(raw, word) {
  const { label, rest } = spell(raw, word);
  return `<span class="tag"><b>${esc(label)}</b> &nbsp;${esc(rest)}</span>`;
}

function fmtSlot(v) { return typeof v === 'object' ? JSON.stringify(v) : String(v); }

// Conversation-level no-flow intent: 'Plan' or 'Clarify' if any turn carries it, else null.
function scanKind(c) {
  for (const t of c.turns) {
    const intent = t.labels && t.labels.intent;
    const flow = t.labels && t.labels.flow;
    if (flow === 'Clarify') return 'Clarify';
    if (intent === 'Plan' || intent === 'Clarify') return intent;
  }
  return null;
}

// Expandable record of how this conversation was sampled/generated (observability).
function genPanel(c) {
  const g = c.generation;
  if (!g) return '';
  const spec = g.spec ? ' — ' + esc(g.spec) : '';
  return `<details class="gen"><summary>⚙ Generation trace${spec}</summary>` +
         `<pre class="gen-json">${esc(JSON.stringify(g, null, 2))}</pre></details>`;
}

function renderScenario(c, fb) {
  currentVerdict = fb.verdict || null;
  const main = document.getElementById('main');
  const kind = scanKind(c);
  const kindChip = kind ? chip(kind, kind.toLowerCase()) : '';
  let html = `<div class="meta">${metaTag(c.persona, 'Persona')}` +
             `${metaTag(c.use_case, 'Use case')}${metaTag(c.topic, 'Topic')}${kindChip}</div>`;
  html += `<h2>${esc(c.title)}</h2>`;
  html += `<div class="meta"><span class="tag">${esc(c.convo_id)}</span></div>`;
  html += genPanel(c);
  if (c.available_data && Object.keys(c.available_data).length) {
    html += `<div class="seed">seeded: ${esc(JSON.stringify(c.available_data))}</div>`;
  }
  for (const t of c.turns) {
    const who = t.role === 'user' ? 'user' : 'agent';
    let labels = '';
    if (t.labels || t.slots || t.expected_tools) {
      const intent = t.labels && t.labels.intent;
      const flow = t.labels && t.labels.flow;
      const dax = t.labels && t.labels.dax;
      const isClarify = intent === 'Clarify' || flow === 'Clarify';
      labels = '<div class="labels">';
      if (flow && flow !== 'Clarify') labels += chip(dax ? flow + ' ' + dax : flow, 'flow');
      else if (isClarify) labels += chip('Clarify', 'clarify');
      else if (intent === 'Plan') labels += chip('Plan', 'plan');
      if (intent && flow && flow !== 'Clarify') labels += chip(intent, 'intent');
      if (t.slots) for (const k in t.slots) labels += chip(k + ': ' + fmtSlot(t.slots[k]));
      if (t.expected_tools) for (const tool of t.expected_tools) labels += chip('🔧 ' + tool);
      labels += '</div>';
    }
    const note = t.note ? `<div class="note">⚠ ${esc(t.note)}</div>` : '';
    html += `<div class="turn ${who}"><div class="bubble"><div class="who">${who}</div>` +
            `${esc(t.utterance)}${labels}${note}</div></div>`;
  }
  html += `<div class="feedback">
    <button class="needs ${currentVerdict==='needs'?'sel':''}" data-v="needs">✗ Needs work</button>
    <button class="minor ${currentVerdict==='minor'?'sel':''}" data-v="minor">~ Minor edit</button>
    <button class="approve ${currentVerdict==='approve'?'sel':''}" data-v="approve">✓ Approve</button>
    <button class="save" id="saveBtn">Save</button>
    <textarea id="comment" placeholder="Feedback / what to fix…">${esc(fb.comment || '')}</textarea>
  </div>`;
  main.innerHTML = html;
  main.querySelectorAll('.feedback button[data-v]').forEach(b => {
    b.onclick = () => {
      currentVerdict = b.dataset.v;
      main.querySelectorAll('.feedback button[data-v]').forEach(x => x.classList.remove('sel'));
      b.classList.add('sel');
    };
  });
  document.getElementById('saveBtn').onclick = () => saveFeedback(c.convo_id);
}

async function saveFeedback(id) {
  const body = { id, verdict: currentVerdict, comment: document.getElementById('comment').value };
  await fetch('/api/feedback/' + encodeURIComponent(id),
    { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const item = scenarios.find(s => s.id === id);
  if (item) item.verdict = currentVerdict;
  renderList();
  renderProgress();
  const btn = document.getElementById('saveBtn');
  btn.textContent = 'Saved ✓';
  setTimeout(() => { btn.textContent = 'Save'; }, 1200);
}

let searchTimer = null;
document.getElementById('searchBox').addEventListener('input', event => {
  clearTimeout(searchTimer);
  const query = event.target.value;
  searchTimer = setTimeout(() => runSearch(query), 200);
});

loadList();
