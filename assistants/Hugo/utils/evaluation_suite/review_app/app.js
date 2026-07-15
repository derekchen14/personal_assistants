let scenarios = [];
let current = null;
let currentVerdict = null;
let curationState = null;
let currentReview = null;

async function loadList() {
  curationState = await (await fetch('/api/curation')).json();
  scenarios = await (await fetch('/api/scenarios')).json();
  document.getElementById('listHeading').textContent = curationState.active
    ? `Curation Round ${curationState.round.round}` : 'Flagged for Review';
  const generalized = document.getElementById('generalized');
  generalized.style.display = curationState.active ? 'block' : 'none';
  if (curationState.active) {
    document.getElementById('generalizedText').value = curationState.round.generalized_feedback || '';
  }
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
  if (curationState && curationState.active) {
    const events = curationState.ledger ? curationState.ledger.events.length : total;
    document.getElementById('progress').textContent =
      `${done}/${total} resolved · ${events}/32 review events used`;
  } else {
    const ok = scenarios.filter(s => s.verdict === 'approve').length;
    const minor = scenarios.filter(s => s.verdict === 'minor').length;
    const needs = scenarios.filter(s => s.verdict === 'needs').length;
    document.getElementById('progress').textContent =
      `${done}/${total} reviewed · ${ok} approve · ${minor} minor · ${needs} needs`;
  }
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
  const review = curationState && curationState.active
    ? await (await fetch('/api/curation/' + encodeURIComponent(id))).json() : null;
  const displayed = review && review.edited_case ? review.edited_case : c;
  renderScenario(displayed, fb, review);
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

// Conversation-level chip: 'Plan' if any turn is a plan (multi-flow stack / intent Plan), else null.
function scanKind(c) {
  for (const t of c.turns) {
    if (t.labels && t.labels.intent === 'Plan') return 'Plan';
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

function renderScenario(c, fb, review = null) {
  currentReview = review;
  currentVerdict = review ? review.decision : (fb.verdict || null);
  const main = document.getElementById('main');
  const kind = scanKind(c);
  const kindChip = kind ? chip(kind, kind.toLowerCase()) : '';
  let html = `<div class="meta">${metaTag(c.persona, 'Persona')}` +
             `${metaTag(c.use_case, 'Use case')}${metaTag(c.topic, 'Topic')}${kindChip}</div>`;
  html += `<h2>${esc(c.title)}</h2>`;
  html += `<div class="meta"><span class="tag">${esc(c.convo_id)}</span></div>`;
  if (review && review.edited_case) {
    html += `<div class="seed">Showing the proposed edited conversation</div>`;
  }
  html += genPanel(c);
  if (review) {
    html += `<details class="gen"><summary>Curation findings · score ${esc(review.score)}</summary>` +
      `<pre class="gen-json">${esc(JSON.stringify({audit: review.audit, judgment: review.judgment,
        existing_feedback: review.existing_feedback, proposed_case: review.edited_case}, null, 2))}</pre></details>`;
  }
  if (c.available_data && Object.keys(c.available_data).length) {
    html += `<div class="seed">seeded: ${esc(JSON.stringify(c.available_data))}</div>`;
  }
  for (const t of c.turns) {
    const who = t.role === 'user' ? 'user' : 'agent';
    let labels = '';
    if (t.labels || t.slots || t.actions || t.ambiguity) {
      const intent = t.labels && t.labels.intent;
      const stack = (t.labels && t.labels.stack) || [];
      labels = '<div class="labels">';
      for (const s of stack) labels += chip(s.dax ? s.flow + ' ' + s.dax : s.flow, 'flow');
      if (intent) labels += chip(intent, intent === 'Plan' ? 'plan' : 'intent');
      if (t.ambiguity) labels += chip('❓ ' + t.ambiguity, 'clarify');
      if (t.slots) for (const k in t.slots) labels += chip(k + ': ' + fmtSlot(t.slots[k]));
      if (t.actions) for (const tool of t.actions) labels += chip('🔧 ' + tool);
      labels += '</div>';
    }
    const note = t.note ? `<div class="note">⚠ ${esc(t.note)}</div>` : '';
    html += `<div class="turn ${who}"><div class="bubble"><div class="who">${who}</div>` +
            `${esc(t.utterance)}${labels}${note}</div></div>`;
  }
  const buttons = review
    ? `<button class="needs ${currentVerdict==='delete'?'sel':''}" data-v="delete">✗ Delete</button>
       <button class="minor ${currentVerdict==='fix'?'sel':''}" data-v="fix">~ Fix</button>
       <button class="approve ${currentVerdict==='keep'?'sel':''}" data-v="keep">✓ Keep</button>`
    : `<button class="needs ${currentVerdict==='needs'?'sel':''}" data-v="needs">✗ Needs work</button>
       <button class="minor ${currentVerdict==='minor'?'sel':''}" data-v="minor">~ Minor edit</button>
       <button class="approve ${currentVerdict==='approve'?'sel':''}" data-v="approve">✓ Approve</button>`;
  html += `<div class="feedback">${buttons}
    <button class="save" id="saveBtn">Save</button>
    <textarea id="comment" placeholder="Feedback / what to fix…">${esc(review ? review.correction || '' : fb.comment || '')}</textarea>
  </div>`;
  main.innerHTML = html;
  main.querySelectorAll('.feedback button[data-v]').forEach(b => {
    b.onclick = () => {
      currentVerdict = b.dataset.v;
      main.querySelectorAll('.feedback button[data-v]').forEach(x => x.classList.remove('sel'));
      b.classList.add('sel');
    };
  });
  document.getElementById('saveBtn').onclick = () => review ? saveCuration(c.convo_id) : saveFeedback(c.convo_id);
}

async function saveCuration(id) {
  const editedCase = currentReview && currentReview.edited_case ? currentReview.edited_case : null;
  const body = { decision: currentVerdict, correction: document.getElementById('comment').value,
                 edited_case: editedCase };
  await fetch('/api/curation/' + encodeURIComponent(id),
    { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const item = scenarios.find(s => s.id === id);
  if (item) item.verdict = currentVerdict;
  renderList();
  renderProgress();
  const btn = document.getElementById('saveBtn');
  btn.textContent = 'Saved ✓';
  setTimeout(() => { btn.textContent = 'Save'; }, 1200);
}

async function saveGeneralized() {
  const body = { generalized_feedback: document.getElementById('generalizedText').value };
  await fetch('/api/curation',
    { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const button = document.getElementById('saveGeneralized');
  button.textContent = 'Saved ✓';
  setTimeout(() => { button.textContent = 'Save generalized feedback'; }, 1200);
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
document.getElementById('saveGeneralized').onclick = saveGeneralized;

loadList();
