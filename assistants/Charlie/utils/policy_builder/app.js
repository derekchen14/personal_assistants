// Policy Builder app \u2014 Round 2.
// Flow dropdown (all 9 flows). Per flow, one scrollable page with sections
// in prompt-read order: intent prompt \u2192 skill body (intro \u2192 Process \u2192 Error
// Handling \u2192 Tools \u2192 Output \u2192 Few-shot) \u2192 starter (task \u2192 content block) \u2192
// policy \u2192 flow config. Each section renders as preformatted code with
// Accept / Override / Rationale controls, and an optional multi-choice
// clarify when a deeply unclear decision is flagged.

const state = {
  flows: [],
  activeFlow: null,
  drafts: {},     // flow -> draft json
  feedback: {},   // flow -> feedback json
  dirty: false,
};

async function fetchJSON(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`);
  return res.json();
}

async function loadFlows() {
  const meta = await fetchJSON('/api/flows');
  state.flows = meta.flows;
  state.activeFlow = meta.flows[0];
  document.getElementById('round-label').textContent = `Round ${meta.round}`;
  const sel = document.getElementById('flow-switcher');
  sel.innerHTML = '';
  for (const flow of state.flows) {
    const opt = document.createElement('option');
    opt.value = flow;
    opt.textContent = flow;
    sel.appendChild(opt);
  }
  sel.addEventListener('change', e => {
    if (state.dirty) {
      if (!confirm('Unsaved feedback. Discard and switch flow?')) {
        sel.value = state.activeFlow;
        return;
      }
    }
    state.activeFlow = e.target.value;
    renderAll();
  });
}

async function loadFlow(flow) {
  if (!state.drafts[flow]) {
    try {
      state.drafts[flow] = await fetchJSON(`/api/draft/${flow}`);
    } catch (ecp) {
      state.drafts[flow] = { flow, sections: [], error: ecp.message };
    }
  }
  if (!state.feedback[flow]) {
    const saved = await fetchJSON(`/api/feedback/${flow}`);
    state.feedback[flow] = saved.sections ? saved : { flow, sections: {} };
  }
}

function getSectionFeedback(flow, sectionId) {
  const f = state.feedback[flow].sections;
  if (f[sectionId]) return f[sectionId];
  const fresh = { accepted: null, override: null, rationale: '', clarify_answer: null };
  f[sectionId] = fresh;
  return fresh;
}

function markDirty() {
  state.dirty = true;
  const el = document.getElementById('save-status');
  el.textContent = 'unsaved';
  el.className = 'text-xs text-amber-600 w-24 text-right';
}

function markSaved() {
  state.dirty = false;
  const el = document.getElementById('save-status');
  el.textContent = 'saved';
  el.className = 'text-xs text-emerald-600 w-24 text-right';
}

function renderSectionCard(section) {
  const card = document.createElement('div');
  card.className = 'bg-white border border-slate-200 rounded-lg p-4 shadow-sm';

  const header = document.createElement('div');
  header.className = 'flex items-baseline justify-between mb-2 gap-3';
  const labelEl = document.createElement('h3');
  labelEl.className = 'text-base font-semibold';
  labelEl.textContent = section.label;
  header.appendChild(labelEl);
  const pathEl = document.createElement('code');
  pathEl.className = 'monospace text-xs text-slate-500 truncate';
  pathEl.textContent = section.path;
  header.appendChild(pathEl);
  card.appendChild(header);

  if (section.note) {
    const note = document.createElement('p');
    note.className = 'text-xs text-slate-500 italic mb-2';
    note.textContent = section.note;
    card.appendChild(note);
  }

  const pre = document.createElement('pre');
  pre.className = 'bg-slate-50 border border-slate-200 rounded p-3 text-sm monospace whitespace-pre-wrap overflow-x-auto mb-3';
  if (section.status === 'n/a') {
    pre.classList.add('text-slate-400', 'italic');
    pre.textContent = section.content || 'N/A for this flow.';
  } else {
    pre.textContent = section.content;
  }
  card.appendChild(pre);

  const fb = getSectionFeedback(state.activeFlow, section.id);

  if (section.clarify) {
    const box = document.createElement('div');
    box.className = 'bg-amber-50 border border-amber-200 rounded p-3 mb-3';
    const q = document.createElement('p');
    q.className = 'text-sm font-medium mb-2';
    q.textContent = 'Clarify: ' + section.clarify.question;
    box.appendChild(q);
    for (const opt of section.clarify.options) {
      const lbl = document.createElement('label');
      lbl.className = 'flex items-start gap-2 cursor-pointer text-sm py-1';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = `clarify-${section.id}`;
      input.className = 'mt-0.5';
      input.value = opt;
      input.checked = fb.clarify_answer === opt;
      input.addEventListener('change', () => {
        fb.clarify_answer = opt;
        markDirty();
      });
      lbl.appendChild(input);
      const text = document.createElement('span');
      text.textContent = opt;
      lbl.appendChild(text);
      box.appendChild(lbl);
    }
    card.appendChild(box);
  }

  if (section.status !== 'n/a') {
    const controls = document.createElement('div');
    controls.className = 'flex gap-4 mb-2 text-sm';
    const makeRadio = (value, labelText) => {
      const w = document.createElement('label');
      w.className = 'flex items-center gap-2 cursor-pointer';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = `decision-${section.id}`;
      input.value = value;
      input.checked = fb.accepted === (value === 'accept');
      input.addEventListener('change', () => {
        fb.accepted = (value === 'accept');
        if (value === 'accept') fb.override = null;
        markDirty();
        renderSections();
      });
      w.appendChild(input);
      const t = document.createElement('span');
      t.textContent = labelText;
      w.appendChild(t);
      return w;
    };
    controls.appendChild(makeRadio('accept', 'Accept'));
    controls.appendChild(makeRadio('override', 'Override'));
    card.appendChild(controls);

    if (fb.accepted === false) {
      const ow = document.createElement('div');
      ow.className = 'mb-3';
      if (fb.override === null || typeof fb.override !== 'string') fb.override = section.content;
      const ta = document.createElement('textarea');
      ta.className = 'w-full border border-slate-300 rounded p-2 text-sm monospace';
      ta.rows = Math.min(20, Math.max(6, (section.content || '').split('\n').length + 2));
      ta.value = fb.override;
      ta.addEventListener('input', e => {
        fb.override = e.target.value;
        markDirty();
      });
      ow.appendChild(ta);
      card.appendChild(ow);
    }
  }

  const rwrap = document.createElement('div');
  const rlabel = document.createElement('label');
  rlabel.className = 'text-xs uppercase tracking-wide text-slate-500 block mb-1';
  rlabel.textContent = 'Rationale (transferable)';
  rwrap.appendChild(rlabel);
  const rta = document.createElement('textarea');
  rta.className = 'w-full border border-slate-300 rounded p-2 text-sm';
  rta.rows = 2;
  rta.placeholder = 'Why did you accept or override? Cross-flow reasoning goes here.';
  rta.value = fb.rationale || '';
  rta.addEventListener('input', e => {
    fb.rationale = e.target.value;
    markDirty();
  });
  rwrap.appendChild(rta);
  card.appendChild(rwrap);

  return card;
}

function renderSections() {
  const container = document.getElementById('sections');
  container.innerHTML = '';
  const draft = state.drafts[state.activeFlow];
  const notesEl = document.getElementById('flow-notes');
  if (draft.notes) {
    notesEl.textContent = draft.notes;
    notesEl.classList.remove('hidden');
  } else {
    notesEl.classList.add('hidden');
  }
  if (draft.error) {
    const err = document.createElement('pre');
    err.className = 'text-sm text-red-700 bg-red-50 p-4 rounded';
    err.textContent = `No draft yet for ${state.activeFlow}: ${draft.error}`;
    container.appendChild(err);
    return;
  }
  for (const section of draft.sections || []) {
    container.appendChild(renderSectionCard(section));
  }
}

async function renderAll() {
  await loadFlow(state.activeFlow);
  document.getElementById('flow-switcher').value = state.activeFlow;
  renderSections();
  markSaved();
}

async function saveFeedback() {
  const flow = state.activeFlow;
  const payload = state.feedback[flow];
  payload.flow = flow;
  payload.round = 2;
  try {
    await fetchJSON(`/api/feedback/${flow}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    markSaved();
  } catch (ecp) {
    const el = document.getElementById('save-status');
    el.textContent = 'save failed';
    el.className = 'text-xs text-red-600 w-24 text-right';
    console.error(ecp);
  }
}

async function main() {
  await loadFlows();
  await renderAll();
  document.getElementById('save-btn').addEventListener('click', saveFeedback);
  window.addEventListener('beforeunload', e => {
    if (state.dirty) {
      e.preventDefault();
      e.returnValue = '';
    }
  });
}

main().catch(ecp => {
  document.getElementById('sections').innerHTML =
    `<pre class="text-sm text-red-700 bg-red-50 p-4 rounded">Load failed: ${ecp.message}</pre>`;
});
