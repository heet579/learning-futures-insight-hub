// Insight Hub in the browser. Plain ES module; talks to the same API as the desktop app.

const app = document.getElementById('app');
const S = { token: '', user: null, config: null, work: null, checkIndex: 0, improve: { sections: [], method: 'gemini' }, reopened: new Set() };

// ---- small helpers ------------------------------------------------------------------------
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const store = {
  get(k) { try { return localStorage.getItem(k) || ''; } catch { return ''; } },
  set(k, v) { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch { /* private mode */ } },
};
const firstName = (u) => (u?.display_name || u?.username || '').split(' ')[0];
const greeting = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'; };
const ago = (iso) => {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (!isFinite(s)) return '';
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
};
const STATUS = {
  'DRAFT': ['Draft', 'draft'], 'CHANGES REQUESTED': ['Changes requested', 'changes'],
  'AWAITING HUMAN REVIEW': ['Waiting for review', 'waiting'], 'HUMAN REVIEWED': ['Approved', 'approved'],
};
const pill = (status) => { const [text, cls] = STATUS[status] || [status, 'draft']; return `<span class="pill ${cls}">${esc(text)}</span>`; };

function toast(message, bad = false) {
  const el = document.createElement('div');
  el.className = 'toast' + (bad ? ' bad' : '');
  el.textContent = message;
  $('#toasts').append(el);
  setTimeout(() => el.remove(), bad ? 6000 : 3200);
}

function md(text) {
  // The report format is simple Markdown: headings, bullets, sub-bullets and bold.
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  const out = []; let list = null;
  const close = () => { if (list) { out.push('</ul>'); list = null; } };
  for (const line of String(text || '').split('\n')) {
    if (/^# /.test(line)) { close(); out.push(`<h1>${inline(line.slice(2))}</h1>`); }
    else if (/^## /.test(line)) { close(); out.push(`<h2>${inline(line.slice(3))}</h2>`); }
    else if (/^\s*- /.test(line)) {
      if (!list) { out.push('<ul>'); list = true; }
      const sub = /^\s{2,}- /.test(line);
      out.push(`<li${sub ? ' style="margin-left:18px;list-style:circle"' : ''}>${inline(line.replace(/^\s*- /, ''))}</li>`);
    } else if (line.trim()) { close(); out.push(`<p>${inline(line)}</p>`); }
    else close();
  }
  close();
  return `<div class="doc-md">${out.join('')}</div>`;
}

const icon = {
  expand: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/></svg>',
  shrink: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3v3a2 2 0 0 1-2 2H3M21 8h-3a2 2 0 0 1-2-2V3M3 16h3a2 2 0 0 1 2 2v3M16 21v-3a2 2 0 0 1 2-2h3"/></svg>',
  check: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  mark: '<svg width="16" height="16" viewBox="0 0 32 32" aria-hidden="true"><path d="M7 25V9h4v16zm7 0V14h4v11zm7 0v-7h4v7z" fill="#fff"/></svg>',
  markPlum: '<svg width="16" height="16" viewBox="0 0 32 32" aria-hidden="true"><path d="M7 25V9h4v16zm7 0V14h4v11zm7 0v-7h4v7z" fill="#5B2EA6"/></svg>',
};

// ---- API ----------------------------------------------------------------------------------
class ApiError extends Error { constructor(message, status) { super(message); this.status = status; } }

async function api(path, { method = 'GET', body, form, raw } = {}) {
  const headers = {};
  if (S.token) headers.Authorization = `Bearer ${S.token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  let response;
  try {
    response = await fetch(path, { method, headers, body: payload });
  } catch {
    throw new ApiError('Cannot reach the Insight Hub server. Check your connection and try again.', 0);
  }
  if (raw && response.ok) return response;
  let data = null;
  try { data = await response.json(); } catch { /* empty body */ }
  if (!response.ok) {
    let message = data?.detail;
    if (Array.isArray(message)) message = message.map((d) => d.msg).join('; ');
    if (response.status === 401 && S.token) { signOut(false); toast(message || 'Please sign in again.', true); }
    throw new ApiError(message || `Something went wrong (${response.status}).`, response.status);
  }
  return data ?? {};
}

async function busy(button, work) {
  const label = button?.innerHTML;
  if (button) { button.disabled = true; button.innerHTML = '<span class="spinner"></span>' + label; }
  try { return await work(); }
  catch (error) { toast(error.message, true); return null; }
  finally { if (button && document.body.contains(button)) { button.disabled = false; button.innerHTML = label; } }
}

function dialog({ title, body = '', confirm = 'Confirm', danger = false, fields = '' }) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'overlay';
    overlay.innerHTML = `<div class="dialog" role="dialog" aria-modal="true" aria-labelledby="dlg-title">
      <h2 id="dlg-title">${esc(title)}</h2>${body ? `<p class="muted">${body}</p>` : ''}
      <form>${fields}<div class="buttons"><button type="button" class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn ${danger ? 'btn-bad' : 'btn-primary'}">${esc(confirm)}</button></div></form></div>`;
    document.body.append(overlay);
    const done = (value) => { overlay.remove(); document.removeEventListener('keydown', onKey); resolve(value); };
    const onKey = (e) => { if (e.key === 'Escape') done(null); };
    document.addEventListener('keydown', onKey);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) done(null); });
    $('[data-cancel]', overlay).onclick = () => done(null);
    $('form', overlay).onsubmit = (e) => { e.preventDefault(); done(Object.fromEntries(new FormData(e.target))); };
    ($('input, textarea, select', overlay) || $('.btn-primary, .btn-bad', overlay)).focus();
  });
}

async function download(path, fallbackName) {
  try {
    const response = await api(path, { raw: true });
    const name = /filename="(.+?)"/.exec(response.headers.get('content-disposition') || '')?.[1] || fallbackName;
    const url = URL.createObjectURL(await response.blob());
    const a = Object.assign(document.createElement('a'), { href: url, download: name });
    document.body.append(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    toast(`Downloaded ${name}`);
  } catch (error) { toast(error.message, true); }
}

// ---- session ---------------------------------------------------------------------------------
function startSession(result) {
  S.token = result.token;
  S.user = { username: result.username, role: result.role, display_name: result.display_name || '' };
  store.set('hub.token', S.token);
  go('#/');
}

function go(hash) {
  if (location.hash === hash) route(); else location.hash = hash;
}

function signOut(navigate = true) {
  S.token = ''; S.user = null; S.work = null;
  store.set('hub.token', '');
  if (navigate) go('#/sign-in');
}

async function restore() {
  S.config = await api('/api/config').catch(() => ({ approver_roles: [], sections: [] }));
  S.token = store.get('hub.token');
  if (S.token) {
    try { S.user = await api('/auth/me'); } catch { S.token = ''; S.user = null; store.set('hub.token', ''); }
  }
}

// ---- router ------------------------------------------------------------------------------------
async function route() {
  const hash = location.hash.replace(/^#/, '') || '/';
  if (!S.user) return signInView(hash === '/create-account' ? 'register' : 'signin');
  const parts = hash.split('/').filter(Boolean);
  if (parts[0] === 'r' && parts[1]) return workView(parts[1], parts[2] || '');
  if (parts[0] === 'accounts' && S.user.role === 'admin') return accountsView();
  if (parts[0] === 'oversight' && S.user.role === 'admin') return oversightView();
  if (parts[0] === 'profile') return profileView();
  return homeView();
}
window.addEventListener('hashchange', route);

function shell(active, content) {
  const pending = S.pendingCount ? `<span class="count">${S.pendingCount}</span>` : '';
  app.innerHTML = `
  <header class="topbar">
    <a class="brand" href="#/"><span class="brand-mark">${icon.mark}</span><span class="brand-name">Insight Hub</span> <small>Learning Futures</small></a>
    <nav class="nav" aria-label="Main">
      <a href="#/" ${active === 'home' ? 'aria-current="page"' : ''}>Reports${pending}</a>
      ${S.user.role === 'admin' ? `<a href="#/oversight" ${active === 'oversight' ? 'aria-current="page"' : ''}>Oversight</a><a href="#/accounts" ${active === 'accounts' ? 'aria-current="page"' : ''}>Accounts</a>` : ''}
    </nav>
    <span class="spacer"></span>
    <button class="icon-btn" id="fullscreen" title="Full screen" aria-label="Full screen">${document.fullscreenElement ? icon.shrink : icon.expand}</button>
    <button class="avatar" id="me" aria-haspopup="true" aria-expanded="false" title="${esc(S.user.display_name || S.user.username)}">${esc((S.user.display_name || S.user.username)[0].toUpperCase())}</button>
  </header>
  <main id="main">${content}</main>`;
  $('#fullscreen').onclick = toggleFullscreen;
  $('#me').onclick = (e) => { e.stopPropagation(); toggleMenu(); };
}

function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen?.();
  else document.documentElement.requestFullscreen?.().catch(() => toast('Your browser blocked full screen. Press F11 instead.', true));
}
document.addEventListener('fullscreenchange', () => { const b = $('#fullscreen'); if (b) b.innerHTML = document.fullscreenElement ? icon.shrink : icon.expand; });

function toggleMenu() {
  const open = $('.menu');
  if (open) { open.remove(); $('#me')?.setAttribute('aria-expanded', 'false'); return; }
  const menu = document.createElement('div');
  menu.className = 'menu';
  menu.innerHTML = `<div class="who"><b>${esc(S.user.display_name || S.user.username)}</b><div class="faint">${esc(S.user.username)} · ${S.user.role === 'admin' ? 'Administrator' : 'Member'}</div></div>
    <a href="#/profile">Profile and password</a>
    ${S.user.role === 'admin' ? '<a href="#/accounts">Manage accounts</a>' : ''}
    <button id="signout">Sign out</button>`;
  document.body.append(menu);
  $('#me').setAttribute('aria-expanded', 'true');
  $('#signout', menu).onclick = () => { menu.remove(); signOut(); };
  setTimeout(() => document.addEventListener('click', function close(e) {
    if (!menu.contains(e.target)) { menu.remove(); $('#me')?.setAttribute('aria-expanded', 'false'); document.removeEventListener('click', close); }
  }), 0);
}

// ---- sign in / create account ------------------------------------------------------------------
function signInView(mode) {
  const register = mode === 'register';
  app.innerHTML = `
  <div class="auth">
    <section class="auth-story">
      <a class="brand" href="#/"><span class="brand-mark">${icon.markPlum}</span>Insight Hub <small>Learning Futures</small></a>
      <div>
        <h1>Learner feedback, turned into reports people trust.</h1>
        <p>Import a survey, check what it says, and send a report that a second person has reviewed before anyone reads it.</p>
      </div>
      <ol class="steps">
        <li><b>1</b>Upload the survey export</li>
        <li><b>2</b>Keep the themes that are real</li>
        <li><b>3</b>Check every statement against the data</li>
        <li><b>4</b>Send it for a second review</li>
      </ol>
      <div class="bars" aria-hidden="true"><span style="height:120px"></span><span style="height:200px"></span><span style="height:160px"></span><span style="height:260px"></span></div>
    </section>
    <section class="auth-panel" id="main">
      ${register ? `
        <h2>Create your account</h2>
        <p class="sub">An administrator approves new accounts before they can sign in.</p>
        <form id="form">
          <label class="field"><span>Full name</span><input class="input" name="display_name" autocomplete="name" required></label>
          <label class="field"><span>Username</span><input class="input" name="username" autocomplete="username" required><small>Letters, numbers, dots or hyphens. You'll use it to sign in.</small></label>
          <label class="field"><span>Email</span><input class="input" name="email" type="email" autocomplete="email" required></label>
          <label class="field"><span>Password</span><div class="reveal"><input class="input" name="password" type="password" autocomplete="new-password" minlength="8" required><button type="button" class="reveal-btn" aria-pressed="false">Show</button></div><small>At least 8 characters.</small></label>
          <button class="btn btn-primary btn-lg" style="width:100%">Request account</button>
          <div id="msg"></div>
        </form>
        <p class="switch">Already have an account? <button id="switch">Sign in</button></p>` : `
        <h2>Welcome back</h2>
        <p class="sub">Sign in to your evaluation workspace.</p>
        <form id="form">
          <label class="field"><span>Username</span><input class="input" name="username" autocomplete="username" required autofocus></label>
          <label class="field"><span>Password</span><div class="reveal"><input class="input" name="password" type="password" autocomplete="current-password" required><button type="button" class="reveal-btn" aria-pressed="false" aria-label="Show password">Show</button></div></label>
          <button class="btn btn-primary btn-lg" style="width:100%">Sign in</button>
          <div id="msg"></div>
        </form>
        <div id="google-area" class="hidden"><div class="or">or</div><div class="google" id="google"></div></div>
        <p class="switch">New to Insight Hub? <button id="switch">Create an account</button></p>`}
    </section>
  </div>`;
  $('#switch').onclick = () => { location.hash = register ? '#/sign-in' : '#/create-account'; };
  bindReveal(app);
  const msg = (text, kind = 'bad') => { $('#msg').innerHTML = text ? `<div class="notice ${kind}" style="margin-top:16px">${esc(text)}</div>` : ''; };
  $('#form').onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    const button = $('button.btn-primary', e.target);
    msg('');
    if (register) {
      await busy(button, async () => {
        try {
          const r = await api('/auth/register', { method: 'POST', body: data });
          e.target.reset();
          msg(`Request sent for “${r.username}”. You can sign in once an administrator approves it.`, 'good');
        } catch (error) { msg(error.message); }
      });
    } else {
      await busy(button, async () => {
        try { startSession(await api('/auth/login', { method: 'POST', body: data })); }
        catch (error) { msg(error.status === 0 ? error.message : error.message || 'Username or password is incorrect.'); }
      });
    }
  };
  if (!register && S.config?.google_web_client_id) googleButton($('#google'), async (credential) => {
    msg('');
    try {
      const r = await api('/auth/google', { method: 'POST', body: { id_token: credential } });
      if (r.pending) msg(r.detail, 'warn'); else startSession(r);
    } catch (error) { msg(error.message); }
  }).then((shown) => shown && $('#google-area').classList.remove('hidden'));
}

function bindReveal(root) {
  $$('.reveal-btn', root).forEach((b) => b.onclick = () => {
    const input = b.previousElementSibling;
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    b.textContent = show ? 'Hide' : 'Show';
    b.setAttribute('aria-pressed', String(show));
    b.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    input.focus();
  });
}

function googleButton(target, onCredential) {
  return new Promise((resolve) => {
    const render = () => {
      try {
        window.google.accounts.id.initialize({ client_id: S.config.google_web_client_id, callback: (r) => onCredential(r.credential) });
        window.google.accounts.id.renderButton(target, { theme: 'outline', size: 'large', shape: 'pill', text: 'continue_with', width: 320 });
        resolve(true);
      } catch { resolve(false); }
    };
    if (window.google?.accounts?.id) return render();
    const script = Object.assign(document.createElement('script'), { src: 'https://accounts.google.com/gsi/client', async: true });
    script.onload = render; script.onerror = () => resolve(false);
    document.head.append(script);
  });
}

// ---- home: reports ------------------------------------------------------------------------------
async function homeView() {
  S.work = null;
  shell('home', '<div class="loading"><div class="spinner"></div>Loading your reports…</div>');
  let mine = [], pending = [], approved = [];
  try {
    [mine, pending, approved] = await Promise.all([
      api('/reports?view=mine'), api('/reports?view=pending'), api('/reports?view=approved')]);
  } catch (error) { $('#main').innerHTML = `<div class="page"><div class="notice bad">${esc(error.message)}</div></div>`; return; }
  S.pendingCount = pending.length;
  const working = mine.filter((r) => r.status !== 'HUMAN REVIEWED');
  const returned = mine.filter((r) => r.status === 'CHANGES REQUESTED').length;
  let line = 'Upload a survey export to start a report.';
  if (pending.length) line = `${pending.length === 1 ? 'One report is' : `${pending.length} reports are`} waiting for your review.`;
  else if (returned) line = `${returned === 1 ? 'One report came' : `${returned} reports came`} back with changes to make.`;
  else if (working.length) line = `You have ${working.length} report${working.length === 1 ? '' : 's'} in progress.`;
  const row = (r, opts = {}) => `
    <div class="item" data-open="${esc(r.id)}" tabindex="0" role="link">
      <div><div class="title">${esc(r.title)}</div>
        <div class="meta">${rowMeta(r, opts)}</div>
        ${r.return_notes ? `<div class="note"><b>${esc(r.returned_by)} asked for changes:</b> ${esc(r.return_notes)}</div>` : ''}
      </div>
      ${pill(r.status)}
      ${opts.delete && ['DRAFT', 'CHANGES REQUESTED'].includes(r.status)
        ? `<button class="btn btn-quiet btn-sm" data-delete="${esc(r.id)}" data-version="${r.version}" data-title="${esc(r.title)}">Delete</button>` : '<span></span>'}
    </div>`;
  shell('home', `<div class="page">
    <div class="hello"><h1>${greeting()}, ${esc(firstName(S.user))}.</h1><p>${esc(line)}</p></div>
    <form class="drop" id="drop">
      <div>
        <h2>Start a new report</h2>
        <p class="muted">Drop one or more survey exports here (CSV or Excel), or choose them from your computer.</p>
        <div class="row">
          <input class="input" name="title" placeholder="Report name (optional)" aria-label="Report name">
          <label class="btn btn-ghost">Choose files<input type="file" id="file" accept=".csv,.xlsx,.xls" multiple hidden></label>
        </div>
        <div class="files" id="files"></div>
      </div>
      <button class="btn btn-primary btn-lg" id="start" disabled>Analyse survey</button>
    </form>
    ${S.user.role === 'admin' || pending.length ? `<div class="section-head"><h2>Waiting for your review</h2><span class="faint">${pending.length}</span></div>
      <div class="list">${pending.map((r) => row(r, { owner: true })).join('') || '<div class="empty">Nothing to review right now. Reports teammates submit appear here.</div>'}</div>` : ''}
    <div class="section-head"><h2>Your reports</h2><span class="faint">${working.length}</span></div>
    <div class="list">${working.map((r) => row(r, { delete: true })).join('') || '<div class="empty">No reports yet. Your drafts appear here, and only you can see them until you send them for review.</div>'}</div>
    <div class="section-head"><h2>Approved</h2><span class="faint">${approved.length}</span></div>
    <div class="list">${approved.map((r) => row(r, { owner: r.owner !== S.user.username })).join('') || '<div class="empty">Approved reports you wrote or reviewed appear here, ready to download.</div>'}</div>
  </div>`);
  $$('[data-open]').forEach((el) => {
    const open = () => { location.hash = `#/r/${el.dataset.open}`; };
    el.onclick = (e) => { if (!e.target.closest('[data-delete]')) open(); };
    el.onkeydown = (e) => { if (e.key === 'Enter') open(); };
  });
  $$('[data-delete]').forEach((b) => b.onclick = async (e) => {
    e.stopPropagation();
    if (!await dialog({ title: 'Delete this draft?', body: `“${esc(b.dataset.title)}” and its review progress will be removed. This can't be undone.`, confirm: 'Delete draft', danger: true })) return;
    await busy(b, async () => { await api(`/reports/${b.dataset.open || b.dataset.delete}?version=${b.dataset.version}`, { method: 'DELETE' }); toast('Draft deleted'); homeView(); });
  });
  bindUpload();
}

function person(name, username) {
  return name && name !== username ? `${esc(name)} (${esc(username)})` : esc(username);
}

function rowMeta(r, opts) {
  const parts = [];
  if (opts.owner) parts.push(`From ${person(r.owner_name, r.owner)}`);
  if (r.status === 'AWAITING HUMAN REVIEW' && !opts.owner) parts.push(r.reviewer ? `With ${esc(r.reviewer_name || r.reviewer)} for review` : 'With the administrators for review');
  if (r.status === 'HUMAN REVIEWED' && r.reviewer) parts.push(`Approved by ${esc(r.reviewer_name || r.reviewer)}`);
  parts.push(`updated ${esc(ago(r.updated))}`);
  const text = parts.join(', ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function bindUpload() {
  const form = $('#drop'), input = $('#file'), start = $('#start');
  let files = [];
  const show = () => {
    $('#files').textContent = files.length ? files.map((f) => f.name).join(', ') : '';
    start.disabled = !files.length;
  };
  input.onchange = () => { files = [...input.files]; show(); };
  ['dragenter', 'dragover'].forEach((t) => form.addEventListener(t, (e) => { e.preventDefault(); form.classList.add('over'); }));
  ['dragleave', 'drop'].forEach((t) => form.addEventListener(t, (e) => { e.preventDefault(); form.classList.remove('over'); }));
  form.addEventListener('drop', (e) => { files = [...e.dataTransfer.files].filter((f) => /\.(csv|xlsx|xls)$/i.test(f.name)); show(); });
  form.onsubmit = async (e) => {
    e.preventDefault();
    const data = new FormData();
    files.forEach((f) => data.append('files', f));
    data.append('title', form.title.value);
    start.innerHTML = 'Reading and analysing…';
    await busy(start, async () => {
      const result = await api('/api/reports', { method: 'POST', form: data });
      S.work = result; S.checkIndex = 0;
      toast('Survey analysed');
      location.hash = `#/r/${result.report.id}/data`;
    });
  };
}

// ---- report workspace ---------------------------------------------------------------------------
const STEPS = [
  ['data', 'Data', 'What the survey says'],
  ['themes', 'Themes', 'Keep what is real'],
  ['draft', 'Draft', 'Write and refine'],
  ['check', 'Check', 'Facts checked for you'],
  ['send', 'Send', 'Second review'],
];

function stepState(ws) {
  const themesDone = ws.themes_progress.reviewed === ws.themes_progress.total;
  const claimsDone = !!ws.clear && ws.clear.check.passed && ws.claims.every((c) => c.decision !== 'pending');
  return {
    data: true, themes: themesDone, draft: !!ws.report && !ws.themes_changed_since_draft,
    check: claimsDone, send: ws.workflow.status !== 'DRAFT' && ws.workflow.status !== 'CHANGES REQUESTED',
  };
}

function suggestedStep(ws) {
  if (ws.can_review || ['AWAITING HUMAN REVIEW', 'HUMAN REVIEWED'].includes(ws.workflow.status)) return 'review';
  const done = stepState(ws);
  if (!done.themes) return 'themes';
  if (!done.draft) return 'draft';
  if (!done.check) return 'check';
  return 'send';
}

async function workView(id, step) {
  if (!S.work || S.work.report.id !== id) {
    shell('home', '<div class="loading"><div class="spinner"></div>Opening the report…</div>');
    try { S.work = await api(`/api/reports/${id}`); S.checkIndex = 0; S.improve = { sections: [], method: 'gemini' }; }
    catch (error) { $('#main').innerHTML = `<div class="page"><div class="notice bad">${esc(error.message)}</div><p style="margin-top:16px"><a href="#/">Back to reports</a></p></div>`; return; }
  }
  const ws = S.work.workspace;
  if (!step) { location.replace(`#/r/${id}/${suggestedStep(ws)}`); return; }
  renderWork(step);
}

function renderWork(step) {
  const { report, workspace: ws } = S.work;
  const done = stepState(ws);
  const locked = !ws.can_edit;
  const reviewing = step === 'review';
  const rail = `<aside class="rail">
      <a class="back" href="#/">Back to reports</a>
      <h2 id="title" ${ws.can_edit ? 'title="Rename" style="cursor:pointer"' : ''}>${esc(report.title)}</h2>
      <div style="margin-top:8px">${pill(ws.workflow.status)}</div>
      <ol>${STEPS.map(([key, label, hint], i) => {
        const available = key === 'data' || key === 'themes' || (key === 'draft' && done.themes) || (key === 'check' && ws.report) || (key === 'send' && ws.report);
        return `<li class="${done[key] ? 'done' : ''} ${available || locked ? '' : 'locked'}">
          <a href="#/r/${report.id}/${key}" ${step === key ? 'aria-current="step"' : ''}>
            <span class="dot">${done[key] ? icon.check : i + 1}</span><span class="label"><b>${label}</b><small>${hint}</small></span></a></li>`;
      }).join('')}
      ${ws.can_review || ['AWAITING HUMAN REVIEW', 'HUMAN REVIEWED'].includes(ws.workflow.status) ? `<li><a href="#/r/${report.id}/review" ${reviewing ? 'aria-current="step"' : ''}>
        <span class="dot">${ws.workflow.status === 'HUMAN REVIEWED' ? icon.check : '6'}</span><span class="label"><b>${ws.workflow.status === 'HUMAN REVIEWED' ? 'Approved' : 'Review'}</b><small>${ws.can_review ? 'Your decision' : report.reviewer_name ? esc(report.reviewer_name) : 'Reviewer’s decision'}</small></span></a></li>` : ''}
      </ol>
    </aside>`;
  const views = { data: dataStep, themes: themesStep, draft: draftStep, check: checkStep, send: sendStep, review: reviewStep };
  shell('home', `<div class="work">${rail}<section class="stage" id="stage"></section></div>`);
  if (ws.can_edit) $('#title').onclick = renameReport;
  (views[step] || dataStep)($('#stage'), ws, report);
}

function returnedBanner(ws) {
  if (ws.workflow.status !== 'CHANGES REQUESTED') return '';
  const event = [...ws.workflow.events].reverse().find((e) => e.action === 'Returned for changes');
  return event ? `<div class="notice warn banner"><b>${esc(event.actor)} asked for changes:</b> ${esc(event.notes)}<br><span class="muted">Make the changes, check the affected statements again, then send it back.</span></div>` : '';
}

function lockedBanner(ws) {
  if (ws.can_edit) return '';
  const text = ws.workflow.status === 'HUMAN REVIEWED' ? 'This report is approved and locked.'
    : ws.workflow.status === 'AWAITING HUMAN REVIEW' ? 'This report is with the reviewer, so it is locked for editing.' : 'You can view this report but not change it.';
  return `<div class="notice banner">${text}</div>`;
}

async function change(path, body, method = 'POST', button = null) {
  return busy(button, async () => {
    const result = await api(`/api/reports/${S.work.report.id}${path}`, { method, body });
    S.work = result;
    return result;
  });
}

async function renameReport() {
  const r = await dialog({ title: 'Rename report', confirm: 'Save name',
    fields: `<label class="field"><span>Report name</span><input class="input" name="title" value="${esc(S.work.report.title)}" required maxlength="300"></label>` });
  if (!r) return;
  try {
    const result = await api(`/reports/${S.work.report.id}/rename`, { method: 'POST', body: { version: S.work.report.version, title: r.title } });
    S.work.report.title = r.title.trim(); S.work.report.version = result.version;
    renderWork(location.hash.split('/')[3] || 'data');
  } catch (error) { toast(error.message, true); }
}

// step 1: data
function dataStep(el, ws) {
  const m = ws.metrics;
  const fmt = (v, d = 0) => (v === null || v === undefined ? 'n/a' : Number(v).toFixed(d));
  el.innerHTML = `${returnedBanner(ws)}
    <div class="stage-head"><div><h1>What the survey says</h1>
      <p>${esc(ws.file_label)}: ${m.responses.toLocaleString()} responses analysed. ${ws.masked_count
        ? `${ws.masked_count} contact detail${ws.masked_count === 1 ? ' was' : 's were'} found in comments and masked before anything else.`
        : 'No email addresses, phone numbers or links were found in the comments.'}</p></div>
      <a class="btn btn-primary" href="#/r/${S.work.report.id}/themes">Review themes</a></div>
    <div class="stats">
      <div class="stat lead"><b>${fmt(m.satisfaction_mean, 2)}</b><span>average satisfaction out of 5</span></div>
      <div class="stat"><b>${m.responses.toLocaleString()}</b><span>responses</span></div>
      <div class="stat"><b>${fmt(m.recommend_percent)}%</b><span>would recommend</span></div>
      <div class="stat"><b>${fmt(m.completeness)}%</b><span>answers complete</span></div>
    </div>
    <div class="two">
      <div class="panel"><h3>Ratings</h3>${m.ratings.map((r) => `
        <div class="bar"><span>${esc(r.label)}</span><div class="track"><div class="fill" style="width:${r.mean ? (r.mean / 5) * 100 : 0}%"></div></div><b>${fmt(r.mean, 2)}</b></div>`).join('')}
        ${ws.warnings.length ? `<div class="notice warn" style="margin-top:14px">${ws.warnings.map(esc).join('<br>')}</div>` : ''}
      </div>
      <div class="panel"><h3>Ask about this survey</h3>
        <p class="muted">Gemini answers from the calculated results only; comments never leave the server.</p>
        <form class="ask" id="ask"><input class="input" name="q" placeholder="Which area has the most room to improve?" maxlength="2000" aria-label="Question"><button class="btn btn-ghost">Ask</button></form>
        <div class="answer" id="answer"></div>
      </div>
    </div>
    <div class="panel" style="margin-top:28px">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px"><h3 style="margin:0">Overview and suggested next steps</h3>
      <button class="btn btn-ghost btn-sm" id="insights">Get Gemini insights</button></div>
      <div id="insights-body" style="margin-top:12px">${insightsHtml(ws.insights)}</div>
    </div>
    <div style="margin-top:34px;display:flex;justify-content:space-between;align-items:end;gap:12px">
      <div><h2>Responses</h2><p class="faint">Shown with contact details masked.</p></div>
      <input class="input" id="search" placeholder="Search responses" style="max-width:280px" aria-label="Search responses">
    </div>
    <div class="table-wrap" id="rows"><div class="loading">Loading…</div></div>
    <div style="display:flex;gap:10px;align-items:center;margin-top:10px" id="pager"></div>`;
  let offset = 0, timer;
  const load = async () => {
    try {
      const data = await api(`/api/reports/${S.work.report.id}/rows?search=${encodeURIComponent($('#search').value)}&offset=${offset}`);
      $('#rows').innerHTML = `<table><thead><tr>${data.columns.map((c) => `<th>${esc(c.replace(/([a-z])([A-Z])/g, '$1 $2'))}</th>`).join('')}</tr></thead>
        <tbody>${data.rows.map((r) => `<tr>${r.map((v) => `<td>${esc(cell(v))}</td>`).join('')}</tr>`).join('') || `<tr><td colspan="${data.columns.length}">No responses match.</td></tr>`}</tbody></table>`;
      $('#pager').innerHTML = `<span class="faint">${data.total ? `${offset + 1}–${Math.min(offset + 50, data.total)} of ${data.total}` : ''}</span>
        <button class="btn btn-quiet btn-sm" id="prev" ${offset ? '' : 'disabled'}>Previous</button>
        <button class="btn btn-quiet btn-sm" id="next" ${offset + 50 < data.total ? '' : 'disabled'}>Next</button>`;
      $('#prev').onclick = () => { offset = Math.max(0, offset - 50); load(); };
      $('#next').onclick = () => { offset += 50; load(); };
    } catch (error) { $('#rows').innerHTML = `<div class="notice bad">${esc(error.message)}</div>`; }
  };
  $('#search').oninput = () => { clearTimeout(timer); timer = setTimeout(() => { offset = 0; load(); }, 250); };
  load();
  $('#ask').onsubmit = async (e) => {
    e.preventDefault();
    const q = e.target.q.value.trim();
    if (!q) return;
    $('#answer').innerHTML = '<div class="faint">Thinking about the calculated results…</div>';
    try {
      const r = await api(`/api/reports/${S.work.report.id}/ask`, { method: 'POST', body: { question: q } });
      $('#answer').innerHTML = `<p>${esc(r.answer)}</p>${r.evidence.length ? `<div class="evidence" style="margin-top:12px"><h4>Based on</h4><ul>${r.evidence.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}`;
    } catch (error) { $('#answer').innerHTML = `<div class="notice bad">${esc(error.message)}</div>`; }
  };
  $('#insights').onclick = (e) => busy(e.currentTarget, async () => {
    const r = await api(`/api/reports/${S.work.report.id}/insights`, { method: 'POST' });
    $('#insights-body').innerHTML = insightsHtml(r.markdown);
  });
}

function insightsHtml(markdown) {
  // Lead with the suggestions; keep the long evidence list one click away.
  const at = markdown.search(/^## (Evidence|Limitations)/m);
  if (at < 0) return md(markdown);
  return `${md(markdown.slice(0, at))}<details style="margin-top:6px"><summary style="cursor:pointer;color:var(--plum);font-weight:700">Show the evidence and limitations</summary>
    <div style="margin-top:10px">${md(markdown.slice(at))}</div></details>`;
}

const cell = (v) => /^\d{4}-\d{2}-\d{2}T00:00:00$/.test(v ?? '') ? v.slice(0, 10) : (v ?? '');

// step 2: themes
function highlight(text, words) {
  let html = esc(text);
  for (const w of words) html = html.replace(new RegExp(`\\b(${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})\\b`, 'gi'), '<mark>$1</mark>');
  return html;
}

function themesStep(el, ws) {
  const p = ws.themes_progress;
  const pct = p.total ? (p.reviewed / p.total) * 100 : 100;
  el.innerHTML = `${returnedBanner(ws)}${lockedBanner(ws)}
    <div class="stage-head"><div><h1>Keep the themes that are real</h1>
      <p>Themes come from keyword rules, so they can be wrong. Read the comments behind each one, then keep it (and fix its category) or leave it out. Only kept themes go into the report.</p></div></div>
    ${ws.themes_changed_since_draft ? '<div class="notice warn banner">You changed themes after creating the draft. Create the draft again so the report matches.</div>' : ''}
    <div class="progress-line"><b>${p.reviewed} of ${p.total} reviewed</b><div class="track"><div class="fill" style="width:${pct}%"></div></div></div>
    <div id="themes">${ws.themes.map((t, i) => themeCard(t, i, ws)).join('') || '<div class="notice">No recurring themes met the evidence threshold. You can go straight to the draft.</div>'}</div>
    <div style="display:flex;justify-content:flex-end;margin-top:20px">
      <a class="btn btn-primary ${p.reviewed === p.total ? '' : 'hidden'}" href="#/r/${S.work.report.id}/draft">Continue to draft</a></div>`;
  $$('[data-theme]').forEach((card) => {
    const theme = ws.themes[card.dataset.theme];
    $$('[data-cat]', card).forEach((b) => b.onclick = () => { $$('[data-cat]', card).forEach((x) => x.setAttribute('aria-pressed', String(x === b))); });
    const decide = (status, button) => change('/themes', { name: theme.name, status, category: $('[data-cat][aria-pressed="true"]', card)?.dataset.cat || theme.category }, 'POST', button)
      .then((r) => { if (r) { S.reopened.delete(theme.name); renderWork('themes'); } });
    $('[data-keep]', card)?.addEventListener('click', (e) => decide('confirmed', e.currentTarget));
    $('[data-drop]', card)?.addEventListener('click', (e) => decide('rejected', e.currentTarget));
    $('[data-reopen]', card)?.addEventListener('click', () => { S.reopened.add(theme.name); themesStep(el, ws); });
  });
}

function themeCard(t, i, ws, forceOpen = false) {
  const decided = t.decision && !forceOpen && !S.reopened.has(t.name);
  if (decided) {
    const kept = t.decision === 'confirmed';
    return `<article class="theme decided" data-theme="${i}"><header><div><h3>${esc(t.name)}</h3></div>
      <div class="result"><span class="pill ${kept ? 'approved' : 'changes'}">${kept ? `Kept as ${esc(t.decided_category)}` : 'Left out'}</span>
      ${ws.can_edit ? '<button class="btn btn-quiet btn-sm" data-reopen>Change</button>' : ''}</div></header></article>`;
  }
  const current = t.decided_category || t.category;
  return `<article class="theme" data-theme="${i}">
    <header><div><h3>${esc(t.name)}</h3><div class="count">${t.frequency} comment${t.frequency === 1 ? '' : 's'} mention this · suggested as ${esc(t.category)}</div></div></header>
    <div class="quotes">${t.evidence.map((q) => `<div class="quote">${highlight(q.text, q.matched)}</div>`).join('')}</div>
    ${ws.can_edit ? `<div class="actions"><div class="left"><span class="faint">Category</span>
      <div class="segmented" role="group" aria-label="Category">${ws.categories.map((c) => `<button type="button" data-cat="${c}" aria-pressed="${c === current}">${c}</button>`).join('')}</div></div>
      <div class="left"><button class="btn btn-bad" data-drop>Leave out</button><button class="btn btn-primary" data-keep>Keep theme</button></div></div>` : ''}
  </article>`;
}

// step 3: draft
function draftStep(el, ws) {
  const id = S.work.report.id;
  if (!ws.report) {
    const audience = ws.audience || 'facilitator';
    el.innerHTML = `${returnedBanner(ws)}${lockedBanner(ws)}
      <div class="stage-head"><div><h1>Create the draft</h1><p>Choose who the report is for. Gemini writes the summary and recommendations from the calculated results and the themes you kept; everything else comes straight from the data.</p></div></div>
      <div class="choices" role="group" aria-label="Report type">
        <button class="choice" data-aud="facilitator" aria-pressed="${audience === 'facilitator'}"><b>Facilitator report</b><span>Internal coaching: teaching practice, engagement and what to change next time.</span></button>
        <button class="choice" data-aud="client" aria-pressed="${audience === 'client'}"><b>Client report</b><span>For the client: outcomes, relevance and value. Needs approval by a Learning Futures lead.</span></button>
      </div>
      <div class="ask-charts"><b>Include charts in the report?</b>
        <div class="segmented" role="group" aria-label="Charts">
          <button type="button" data-want="on" aria-pressed="true">Yes, the AI picks them</button>
          <button type="button" data-want="off" aria-pressed="false">No, text only</button></div></div>
      <button class="btn btn-primary btn-lg" id="create" ${ws.can_edit && ws.themes_progress.reviewed === ws.themes_progress.total ? '' : 'disabled'}>Create draft</button>
      ${ws.themes_progress.reviewed < ws.themes_progress.total ? `<p class="faint" style="margin-top:10px">Review every theme first (${ws.themes_progress.reviewed} of ${ws.themes_progress.total} done).</p>` : ''}`;
    let chosen = audience, wantCharts = true;
    $$('[data-aud]').forEach((b) => b.onclick = () => { chosen = b.dataset.aud; $$('[data-aud]').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); });
    $$('[data-want]').forEach((b) => b.onclick = () => { wantCharts = b.dataset.want === 'on'; $$('[data-want]').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); });
    $('#create').onclick = async (e) => {
      e.currentTarget.innerHTML = 'Writing the draft…';
      const r = await change('/draft', { audience: chosen, charts: wantCharts }, 'POST', e.currentTarget);
      if (r) { if (r.result) toast(r.result); else toast('Draft ready'); renderWork('draft'); }
    };
    return;
  }
  const revision = ws.revision;
  el.innerHTML = `${returnedBanner(ws)}${lockedBanner(ws)}
    <div class="stage-head"><div><h1>Your draft</h1><p>${ws.report.audience === 'client' ? 'Client' : 'Facilitator'} report, first written by ${esc(ws.report.written_by)}. Read it through and refine any section. The app then checks every fact for you.</p></div>
      <a class="btn btn-primary" href="#/r/${id}/check">Run the check</a></div>
    ${ws.themes_changed_since_draft ? '<div class="notice warn banner">Themes changed since this draft was written. Create it again so they match.</div>' : ''}
    ${ws.can_edit ? `<div class="toolbar">
      <button class="btn btn-ghost btn-sm" id="edit">Edit text</button>
      ${ws.can_undo_revision ? '<button class="btn btn-ghost btn-sm" id="undo">Undo last change</button>' : ''}
      <button class="btn btn-quiet btn-sm" id="regenerate">Create draft again</button>
      <span class="spacer" style="flex:1"></span>
      <button class="btn btn-quiet btn-sm" data-export="md">Markdown</button><button class="btn btn-quiet btn-sm" data-export="docx">Word</button><button class="btn btn-ghost btn-sm" data-export="pdf">PDF</button></div>` : ''}
    <div id="doc-area"><article class="doc">${md(ws.content)}</article></div>
    ${chartsPanel(ws)}
    ${ws.can_edit ? `<section class="panel improve" id="improve">
      <h3>Improve a section</h3>
      ${revision ? revisionPreview(revision) : `
      <p class="muted">Pick the sections to change and say what you want. You'll see the new wording before anything changes.</p>
      <div class="chips" role="group" aria-label="Sections">${(S.config.sections || []).map((s) => `<button type="button" class="chip" data-sec="${esc(s)}" aria-pressed="${S.improve.sections.includes(s)}">${esc(s)}</button>`).join('')}</div>
      <div class="segmented" role="group" aria-label="How" style="margin-bottom:14px">
        <button type="button" data-method="gemini" aria-pressed="${S.improve.method === 'gemini'}">Ask Gemini</button>
        <button type="button" data-method="offline" aria-pressed="${S.improve.method === 'offline'}">Quick edit</button>
        <button type="button" data-method="manual" aria-pressed="${S.improve.method === 'manual'}">My own wording</button></div>
      ${S.improve.method === 'manual'
        ? '<label class="field"><span>New wording for the selected section</span><textarea class="input" id="replacement" placeholder="Paste or write the replacement text"></textarea></label>'
        : `<label class="field"><span>${S.improve.method === 'gemini' ? 'What should change?' : 'Quick edit'}</span><textarea class="input" id="instruction" placeholder="${S.improve.method === 'gemini' ? 'For example: make the summary three sentences for a busy manager' : 'For example: shorten, bullet points, plain language'}"></textarea></label>`}
      <button class="btn btn-primary" id="suggest">Show suggested change</button>`}
    </section>` : ''}`;
  $$('[data-export]').forEach((b) => b.onclick = () => download(`/api/reports/${id}/export?format=${b.dataset.export}`, `report.${b.dataset.export}`));
  bindCharts(ws, id);
  if (!ws.can_edit) return;
  $('#regenerate').onclick = async (e) => {
    if (!await dialog({ title: 'Create the draft again?', body: 'This replaces the current text and clears every statement you checked.', confirm: 'Create again', danger: true })) return;
    const r = await change('/draft', { audience: ws.report.audience, charts: ws.charts_enabled }, 'POST', e.target);
    if (r) { toast(r.result || 'New draft ready'); S.checkIndex = 0; renderWork('draft'); }
  };
  $('#undo')?.addEventListener('click', async (e) => { if (await change('/revisions/undo', undefined, 'POST', e.currentTarget)) { toast('Previous wording restored'); renderWork('draft'); } });
  $('#edit').onclick = () => {
    $('#doc-area').innerHTML = `<textarea class="input" id="editor" style="min-height:520px;font-family:var(--body)">${esc(ws.content)}</textarea>
      <div style="display:flex;gap:10px;margin-top:12px"><button class="btn btn-primary" id="save-text">Save changes</button><button class="btn btn-ghost" id="cancel-text">Cancel</button></div>
      <p class="faint" style="margin-top:8px">Edited sentences become new statements to check.</p>`;
    $('#cancel-text').onclick = () => renderWork('draft');
    $('#save-text').onclick = async (e) => { if (await change('/content', { content: $('#editor').value }, 'PUT', e.currentTarget)) { toast('Changes saved'); renderWork('draft'); } };
  };
  if (revision) {
    $('#apply').onclick = async (e) => { if (await change('/revisions/apply', undefined, 'POST', e.currentTarget)) { toast('Change applied'); S.improve.sections = []; renderWork('draft'); } };
    $('#discard').onclick = async (e) => { if (await change('/revisions/discard', undefined, 'POST', e.currentTarget)) renderWork('draft'); };
    return;
  }
  $$('[data-sec]').forEach((b) => b.onclick = () => {
    const s = b.dataset.sec;
    if (S.improve.method === 'manual') S.improve.sections = [s];
    else S.improve.sections = S.improve.sections.includes(s) ? S.improve.sections.filter((x) => x !== s) : [...S.improve.sections, s];
    $$('[data-sec]').forEach((x) => x.setAttribute('aria-pressed', String(S.improve.sections.includes(x.dataset.sec))));
  });
  $$('[data-method]').forEach((b) => b.onclick = () => { S.improve.method = b.dataset.method; if (b.dataset.method === 'manual') S.improve.sections = S.improve.sections.slice(0, 1); renderWork('draft'); $('#improve').scrollIntoView(); });
  $('#suggest').onclick = async (e) => {
    if (!S.improve.sections.length) return toast('Choose at least one section.', true);
    const body = { sections: S.improve.sections, method: S.improve.method, instruction: $('#instruction')?.value || '', replacement: $('#replacement')?.value || '' };
    if (S.improve.method !== 'manual' && !body.instruction.trim()) return toast('Say what should change.', true);
    e.currentTarget.innerHTML = S.improve.method === 'gemini' ? 'Asking Gemini…' : 'Preparing…';
    if (await change('/revisions', body, 'POST', e.currentTarget)) { renderWork('draft'); $('#improve').scrollIntoView({ block: 'start' }); }
  };
}

// charts that go into the two-page Word / PDF report
function chartsPanel(ws) {
  const editable = ws.can_edit, on = ws.charts_enabled;
  const card = (c, i) => `<figure class="chart-card" data-chart="${i}">
      <div class="chart-img"><img alt="${esc(c.title)}" data-src="/api/reports/${S.work.report.id}/charts/${i}.png?v=${S.work.report.version}"></div>
      <figcaption><b>Figure ${i + 1}.</b> ${esc(c.title)}${c.reason ? `<span class="why">${esc(c.reason)}</span>` : ''}</figcaption>
      ${editable && ws.charts.length > 1 ? '<button class="btn btn-quiet btn-sm chart-remove" data-remove>Remove</button>' : ''}
    </figure>`;
  return `<section class="panel charts-panel" id="charts">
    <div class="charts-head"><div><h3>Charts in the report</h3>
      <p class="muted">${on ? `The AI picked ${ws.charts.length === 1 ? 'this chart' : `these ${ws.charts.length} charts`} to suit the data. The Word and PDF downloads place two on each page and fill both pages.`
        : 'This report is text only. The two pages are filled with plain-English summaries and tables instead of charts.'}</p></div>
      ${editable ? `<div class="segmented" role="group" aria-label="Charts in the report">
        <button type="button" data-charts="on" aria-pressed="${on}">With charts</button>
        <button type="button" data-charts="off" aria-pressed="${!on}">Text only</button></div>` : ''}</div>
    ${on ? `<div class="chart-grid">${ws.charts.map(card).join('')}</div>` : ''}
    ${editable ? `<div class="chart-ask">
      <label class="field" style="flex:1;margin:0"><span>Ask for any chart</span>
        <input class="input" id="chart-text" maxlength="300" placeholder="e.g. heat map of ratings by course · pie chart of delivery mode · how satisfaction changed month by month"></label>
      <button class="btn btn-primary" id="chart-add">Make chart</button>
      ${on ? '<button class="btn btn-ghost" id="chart-auto">Let the AI choose again</button>' : ''}</div>
      <p class="faint" style="margin-top:8px">${on && ws.charts.length >= ws.chart_kinds.max ? `The report holds ${ws.chart_kinds.max} charts, so a new one replaces figure ${ws.chart_kinds.max}.` : 'Bar, stacked, box, violin, histogram, pie, heat map, scatter and trend charts are all available.'}</p>` : ''}
  </section>`;
}

function bindCharts(ws, id) {
  $$('#charts img[data-src]').forEach(async (img) => {
    try {
      const response = await api(img.dataset.src, { raw: true });
      img.src = URL.createObjectURL(await response.blob());
      img.onload = () => URL.revokeObjectURL(img.src);
    } catch { img.closest('.chart-img').classList.add('failed'); }
  });
  if (!ws.can_edit) return;
  const after = (r, fallback) => { if (r) { toast(r.result || fallback); renderWork('draft'); $('#charts')?.scrollIntoView({ block: 'start' }); } };
  $$('#charts [data-charts]').forEach((b) => b.onclick = async (e) => {
    const enabled = b.dataset.charts === 'on';
    if (enabled === ws.charts_enabled) return;
    after(await change('/charts/enabled', { enabled }, 'PUT', e.currentTarget), enabled ? 'Charts on' : 'Text only');
  });
  $$('#charts [data-remove]').forEach((b) => b.onclick = async (e) => {
    const i = Number(b.closest('[data-chart]').dataset.chart);
    after(await change(`/charts/${i}`, undefined, 'DELETE', e.currentTarget), 'Chart removed');
  });
  $('#chart-auto')?.addEventListener('click', async (e) => after(await change('/charts/auto', undefined, 'POST', e.currentTarget), 'Charts chosen'));
  const ask = async (e) => {
    const text = $('#chart-text').value.trim();
    if (!text) return toast('Describe the chart you want.', true);
    after(await change('/charts/describe', { text }, 'POST', e?.currentTarget || $('#chart-add')), 'Chart added');
  };
  $('#chart-add').onclick = ask;
  $('#chart-text').onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); ask(); } };
}

function revisionPreview(r) {
  return `<p class="muted">${esc(r.provider === 'Gemini' ? 'Gemini suggests' : 'Suggested')} new wording for ${r.sections.map(esc).join(', ')}. Nothing has changed yet.</p>
    ${r.changes.map((c) => `<h4 style="margin:14px 0 0;font-family:var(--display)">${esc(c.section)}</h4>
      <div class="compare"><div class="before"><h4>Now</h4>${esc(c.before.trim())}</div><div class="after"><h4>Suggested</h4>${esc(c.after.trim())}</div></div>
      ${c.note ? `<p class="faint">${esc(c.note)}</p>` : ''}`).join('')}
    <div style="display:flex;gap:10px"><button class="btn btn-primary" id="apply">Use this wording</button><button class="btn btn-ghost" id="discard">Keep current wording</button></div>`;
}

// step 4: CLEAR check (automatic) and level
function checkStep(el, ws) {
  const id = S.work.report.id;
  if (!ws.report) { el.innerHTML = `<h1>Check</h1><p class="muted" style="margin-top:8px">Create the draft first.</p><p style="margin-top:16px"><a class="btn btn-primary" href="#/r/${id}/draft">Go to draft</a></p>`; return; }
  const { check, level } = ws.clear;
  const pending = ws.claims.filter((c) => c.decision === 'pending');
  if (S.checkIndex >= pending.length) S.checkIndex = 0;
  const c = pending[S.checkIndex];
  el.innerHTML = `${returnedBanner(ws)}${lockedBanner(ws)}
    <div class="stage-head"><div><h1>The app checked the facts</h1>
      <p>Every number, quote and name in the draft is checked against the survey automatically. You only see what failed or needs a person to confirm.</p></div></div>
    <div class="clear-summary">
      <div class="big"><b>${check.auto_verified}</b><span>checked automatically</span></div>
      <div class="big ${check.needs_person ? 'warn' : 'ok'}"><b>${check.needs_person}</b><span>${check.needs_person === 1 ? 'needs you' : 'need you'}</span></div>
      <div class="big"><b>${level.questions.length}</b><span>questions for the reviewer</span></div>
    </div>
    <ul class="rules">${check.rules.map((r) => `<li class="${r.ok ? 'ok' : r.blocking ? 'bad' : 'warn'}"><span class="mark">${r.ok ? '✓' : r.blocking ? '!' : '?'}</span>
      <div><b>${esc(r.rule)}</b><small>${esc(r.detail)}</small></div></li>`).join('')}</ul>
    ${c ? `<h2 class="sub-head">Needs you (${pending.length})</h2>${claimCard(c, ws)}` : ''}
    <section class="panel level ${level.level}"><div class="level-head"><span class="pill ${level.level === 'high' ? 'changes' : 'approved'}">${esc(level.label)}</span>
      <h3>How closely the reviewer looks</h3></div>
      <ul>${level.reasons.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
      <p class="muted">The reviewer answers ${level.questions.length} questions only a person can answer. ${esc(level.approver)}</p></section>
    ${!c && check.passed ? `<p style="margin-top:22px"><a class="btn btn-primary btn-lg" href="#/r/${id}/send">Continue to send</a></p>` : ''}`;
  if (!c || !ws.can_edit) return;
  const decide = async (decision, button) => {
    const r = await change(`/claims/${encodeURIComponent(c.key)}`, { decision }, 'POST', button);
    if (r) { if (decision === 'reject') toast(c.kind === 'quote' ? 'Quote removed from the draft' : 'Removed from the draft'); renderWork('check'); }
  };
  $('#accept')?.addEventListener('click', (e) => decide('accept', e.currentTarget));
  $('#reject').onclick = (e) => decide('reject', e.currentTarget);
  $('#skip')?.addEventListener('click', () => { S.checkIndex = (S.checkIndex + 1) % pending.length; checkStep(el, ws); });
  $('#prev')?.addEventListener('click', () => { S.checkIndex = (S.checkIndex - 1 + pending.length) % pending.length; checkStep(el, ws); });
}

function claimCard(c, ws) {
  if (!c) return '';
  const quote = c.kind === 'quote';
  const origin = { 'Calculated': 'Calculated from the data', 'AI-written': 'Written by Gemini', 'Human-edited': 'Written or changed by a person' }[c.origin] || c.origin;
  const decided = c.decision !== 'pending';
  return `<article class="focus-card">
    <div class="where"><span class="pill">${esc(c.section)}</span><span>${quote ? 'Learner quote' : origin}</span>
      ${decided ? `<span class="pill ${['accepted', 'cleared'].includes(c.decision) ? 'approved' : 'changes'}">${esc(c.decision)}</span>` : ''}</div>
    <blockquote class="${quote ? 'is-quote' : ''}">${esc(c.text)}</blockquote>
    ${c.checks.length ? `<div class="evidence"><h4>Numbers in this statement</h4><ul>${c.checks.map((k) => `<li><span class="${k.supported ? 'check-ok' : 'check-bad'}">${k.supported ? 'Matches the data' : 'Not found in the data'}</span>: ${esc(k.text)}</li>`).join('')}</ul></div>` : ''}
    ${c.evidence.length ? `<div class="evidence"><h4>Gemini based this on</h4><ul>${c.evidence.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}
    ${quote ? `<div class="evidence"><h4>Before you clear this quote</h4>Make sure it can't identify the learner, a colleague or the client.${c.possible_names.length ? ` Possible names: <b>${c.possible_names.map(esc).join(', ')}</b>.` : ''}</div>`
      : c.possible_names.length ? `<div class="notice warn" style="margin-bottom:14px">Possible names: <b>${c.possible_names.map(esc).join(', ')}</b>. Remove anything that identifies a person.</div>` : ''}
    ${c.problems.filter((p) => !p.startsWith('Unsupported')).map((p) => `<div class="notice ${c.blocking ? 'bad' : 'warn'}" style="margin-bottom:10px">${esc(p)}</div>`).join('')}
    ${ws.can_edit && !decided ? `<div class="decide">
      <button class="btn btn-quiet" id="prev">Back</button><span class="grow"></span>
      <button class="btn btn-quiet" id="skip">Skip for now</button>
      <button class="btn btn-bad btn-lg" id="reject">${quote ? 'Remove quote' : 'Remove it'} <span class="key">R</span></button>
      ${c.blocking ? '' : `<button class="btn btn-good btn-lg" id="accept">${c.possible_names.length ? 'Not a name, keep it' : quote ? 'Safe to keep' : 'Looks right'} <span class="key">A</span></button>`}
    </div>${c.blocking ? '<p class="faint" style="margin-top:10px">This can only be removed, or fixed by editing the draft, because it does not match the data.</p>' : ''}` : ''}
  </article>`;
}

document.addEventListener('keydown', (e) => {
  if (!location.hash.endsWith('/check') || e.target.closest('input, textarea, select') || e.metaKey || e.ctrlKey || $('.overlay')) return;
  const key = e.key.toLowerCase();
  if (key === 'a') $('#accept')?.click();
  else if (key === 'r') $('#reject')?.click();
  else if (e.key === 'ArrowRight') $('#skip')?.click();
  else if (e.key === 'ArrowLeft') $('#prev')?.click();
});

// step 5: send for review
function sendStep(el, ws) {
  const id = S.work.report.id;
  const status = ws.workflow.status;
  if (status === 'AWAITING HUMAN REVIEW' || status === 'HUMAN REVIEWED') return reviewStep(el, ws);
  const items = [
    ['Every theme reviewed', ws.themes_progress.reviewed === ws.themes_progress.total],
    ['Draft created from the kept themes', !!ws.report && !ws.themes_changed_since_draft],
    ['Automatic fact check passed', !!ws.clear && ws.clear.check.passed && ws.claims.every((c) => c.decision !== 'pending')],
    ['Numbers and quotes match the data', !ws.blockers.some((b) => b.startsWith('Fix'))],
    ['No suggested change left open', !ws.revision],
  ];
  const ready = ws.blockers.length === 0;
  el.innerHTML = `${returnedBanner(ws)}
    <div class="stage-head"><div><h1>Send it for a second review</h1>
      <p>A second person reads the report, answers ${ws.clear ? ws.clear.level.questions.length : 3} short questions only a person can answer, then approves it or sends it back with notes. It's locked while they review it.</p></div></div>
    <ul class="checklist">${items.map(([text, ok]) => `<li class="${ok ? 'ok' : ''}"><span class="mark">${ok ? '✓' : '○'}</span>${esc(text)}</li>`).join('')}</ul>
    ${ready ? '' : `<div class="notice warn banner">${ws.blockers.map(esc).join('<br>')}</div>`}
    <label class="field narrow" id="reviewer-field"><span>Who should review it?</span>
      <select class="input" id="reviewer" disabled><option>Loading reviewers…</option></select></label>
    <button class="btn btn-primary btn-lg" id="submit" disabled>Send for review</button>`;
  let people = [];
  api('/api/reviewers').then((list) => {
    people = list;
    const select = $('#reviewer');
    if (!select) return;
    if (!list.length) {
      $('#reviewer-field').innerHTML = `<div class="notice warn">${S.user.role === 'admin'
        ? 'There is nobody else to review your report yet. Add or approve another account under Accounts.'
        : 'There is no administrator to review this report yet. Ask an administrator to set one up.'}</div>`;
      return;
    }
    const option = (p) => `<option value="${esc(p.username)}">${person(p.display_name, p.username)}</option>`;
    const admins = list.filter((p) => p.role === 'admin'), members = list.filter((p) => p.role !== 'admin');
    select.innerHTML = admins.length && members.length
      ? `<optgroup label="Administrators">${admins.map(option).join('')}</optgroup><optgroup label="Team members">${members.map(option).join('')}</optgroup>`
      : list.map(option).join('');
    select.disabled = false;
    $('#submit').disabled = !(ready && ws.can_edit);
  }).catch((error) => toast(error.message, true));
  $('#submit').onclick = (e) => busy(e.currentTarget, async () => {
    const reviewer = $('#reviewer').value;
    await api(`/reports/${id}/transition`, { method: 'POST', body: { version: S.work.report.version, action: 'submit', reviewer } });
    S.work = await api(`/api/reports/${id}`);
    const chosen = people.find((p) => p.username === reviewer);
    toast(`Sent to ${chosen?.display_name || reviewer} for review`);
    location.hash = `#/r/${id}/review`;
  });
}

// review: the CLEAR questions (reviewer) and the read-only states
const CHOICE_LABELS = { yes: 'Yes', partly: 'Partly', no: 'No', keep: 'Keep as it is', caveat: 'Add a caveat' };

function clearQuestion(q, ex, n) {
  const seg = (name, choices) => `<div class="segmented" role="radiogroup" aria-label="${esc(q.title)}">${Object.entries(choices)
    .map(([value, label]) => `<button type="button" role="radio" aria-checked="false" data-q="${name}" data-v="${value}">${esc(label)}</button>`).join('')}</div>`;
  let body = '';
  if (q.id === 'faithful') {
    body = `<ul class="voices">${ex.comments.map((c) => `<li><small>${esc(c.question)}</small>“${esc(c.text)}”</li>`).join('') || '<li>No written comments in this survey.</li>'}</ul>
      ${seg('faithful', q.choices)}
      <label class="field reveal-on" data-for="faithful" data-when="partly,no" hidden><span>What does the report miss?</span><textarea class="input" id="faithful_note" maxlength="600"></textarea></label>`;
  } else if (q.id === 'balanced') {
    body = `<div class="versus"><div><small>The report says</small><b>${esc(ex.claim)}</b></div><div><small>But the data also shows</small><b>${esc(ex.counter.text)}</b></div></div>
      ${seg('balanced', q.choices)}
      <label class="field reveal-on" data-for="balanced" data-when="caveat" hidden><span>Caveat added to the report</span><textarea class="input" id="caveat" maxlength="600">${esc(ex.counter.caveat)}</textarea></label>`;
  } else if (q.id === 'owned') {
    body = `${ex.recommendations.length ? `<div class="chips">${ex.recommendations.map((r, i) => `<button type="button" class="chip" data-rec="${i}">${esc(r.length > 70 ? r.slice(0, 69) + '…' : r)}</button>`).join('')}</div>` : ''}
      <label class="field"><span>Your priority, in your own words</span><textarea class="input" id="owned" maxlength="600" placeholder="For example: Give online groups more structured activities, and compare their satisfaction next term."></textarea></label>`;
  } else if (q.id === 'fair') {
    body = `${seg('fair', q.choices)}
      <label class="field reveal-on" data-for="fair" data-when="yes" hidden><span>Fairness note added to the report</span><textarea class="input" id="fairness_note" maxlength="600" placeholder="For example: Results for this facilitator come from 12 responses and should not be used on their own."></textarea></label>`;
  } else if (q.id === 'fit') {
    body = `${seg('fit', q.choices)}
      <label class="field reveal-on" data-for="fit" data-when="no" hidden><span>What should the author change?</span><textarea class="input" id="fit_note" maxlength="600"></textarea></label>`;
  }
  return `<section class="question" data-question="${q.id}"><div class="q-head"><span class="q-num">${n}</span><div><h3>${esc(q.title)}</h3><p>${esc(q.prompt)}</p></div></div>${body}</section>`;
}

function reviewStep(el, ws) {
  const { report } = S.work;
  const status = ws.workflow.status;
  const s = ws.summary || { themes: {}, claims: {}, pace: {} };
  const approved = status === 'HUMAN REVIEWED';
  const roles = S.config.approver_roles || [];
  const clientReport = ws.report?.audience === 'client';
  const clear = ws.clear || {};
  const ex = clear.examine;
  const answers = clear.answers;
  el.innerHTML = `${returnedBanner(ws)}
    <div class="stage-head"><div><h1>${approved ? 'Approved' : ws.can_review ? 'Your review' : report.reviewer ? `With ${esc(report.reviewer_name || report.reviewer)}` : 'With the reviewer'}</h1>
      <p>${approved ? `Approved by ${person(report.reviewer_name, ws.workflow.approver)} as ${esc(ws.workflow.approver_role)}. Written by ${person(report.owner_name, report.owner)}. The download includes the reviewer's notes and a review record.`
        : ws.can_review ? `Written by ${person(report.owner_name, report.owner)}. The app has already checked every fact. Read the report, then answer ${ex.questions.length} questions only a person can answer.`
        : report.reviewer ? `${person(report.reviewer_name, report.reviewer)} is reviewing this report. You will see it here as approved, or back in your list with their notes.`
        : 'An administrator is reviewing this report. You will see it here as approved, or back in your list with notes.'}</p></div>
      ${approved ? `<div style="display:flex;gap:8px"><button class="btn btn-ghost" data-export="md">Markdown</button><button class="btn btn-ghost" data-export="pdf">PDF</button><button class="btn btn-primary" data-export="docx">Download Word</button></div>` : ''}</div>
    <div class="review-grid">
      <article class="doc">${md(approved ? ws.content : ws.content)}</article>
      <aside class="side">
        <div class="panel"><h3>Already checked</h3><dl class="facts">
          <div><dt>Facts checked automatically</dt><dd>${clear.check?.auto_verified ?? 0}</dd></div>
          <div><dt>Items a person confirmed or removed</dt><dd>${(s.claims.accepted ?? 0) + (s.claims.rejected ?? 0) + (s.claims.cleared ?? 0) + (s.claims.removed ?? 0)}</dd></div>
          <div><dt>Themes kept / left out</dt><dd>${s.themes.confirmed ?? 0} / ${s.themes.rejected ?? 0}</dd></div>
          <div><dt>Written or changed by a person</dt><dd>${s.claims.human_edited ?? 0}</dd></div>
          ${s.ai_retained !== null && s.ai_retained !== undefined ? `<div><dt>AI wording kept</dt><dd>${Math.round(s.ai_retained)}%</dd></div>` : ''}
          <div><dt>Times sent back</dt><dd>${s.returned ?? 0}</dd></div>
          ${clear.level ? `<div><dt>Review level</dt><dd>${esc(clear.level.label)}</dd></div>` : ''}
        </dl>${clear.level && clear.level.level === 'high' ? `<p class="faint" style="margin-top:10px">${clear.level.reasons.map(esc).join(' ')}</p>` : ''}</div>
        ${answers ? `<div class="panel"><h3>The reviewer's answers</h3><dl class="facts">
          <div><dt>Faithful to learners</dt><dd>${esc(CHOICE_LABELS[answers.faithful] || answers.faithful)}</dd></div>
          <div><dt>Strongest claim</dt><dd>${answers.balanced === 'caveat' ? 'Caveat added' : 'Kept'}</dd></div>
          ${answers.fair ? `<div><dt>Fair to people</dt><dd>${answers.fair === 'yes' ? 'Note added' : 'No concern'}</dd></div>` : ''}
          ${answers.fit ? `<div><dt>Fit for the audience</dt><dd>${esc(CHOICE_LABELS[answers.fit])}</dd></div>` : ''}
          ${answers.seconds ? `<div><dt>Time spent</dt><dd>${answers.seconds >= 60 ? Math.round(answers.seconds / 60) + ' min' : answers.seconds + ' s'}</dd></div>` : ''}
        </dl><p class="muted" style="margin-top:10px"><b>Priority:</b> ${esc(answers.owned)}</p></div>` : ''}
        <div class="panel"><h3>History</h3><ol class="timeline">${[...ws.workflow.events].reverse().map((e) => `<li><b>${esc(e.action)}</b>${e.actor ? ` by ${esc(e.actor)}` : ''}${e.action === 'Submitted for review' && report.reviewer && status === 'AWAITING HUMAN REVIEW' ? `, sent to ${esc(report.reviewer_name || report.reviewer)}` : ''}<small>${esc(ago(e.at))}</small>${e.action === 'Returned for changes' ? `<div class="muted">${esc(e.notes)}</div>` : ''}</li>`).join('') || '<li>No review activity yet.</li>'}</ol></div>
      </aside>
    </div>
    ${ws.can_review ? `<section class="clear-review" id="clear">
      <div class="clear-head"><h2>Your judgement</h2><p class="muted">${ex.level.level === 'high' ? `High risk: ${ex.level.reasons.map(esc).join(' ')}` : 'Standard review.'} Your answers go into the report and the audit record.</p></div>
      ${ex.questions.map((q, i) => clearQuestion(q, ex, i + 1)).join('')}
      <div class="question decide-row">
        <label class="field narrow"><span>Approving as</span><select class="input" id="role">${roles.map((r) => `<option ${clientReport && r === S.config.client_approver_role ? 'selected' : ''}>${esc(r)}</option>`).join('')}</select>
          ${clientReport ? `<small>Client reports need a ${esc(S.config.client_approver_role)}.</small>` : ''}</label>
        <div class="decide-buttons"><button class="btn btn-bad" id="return">Send back with notes</button>
          <button class="btn btn-good btn-lg" id="approve">Approve report</button></div>
        <p class="faint">Answering "No" or "Partly" to the first question, or "No" to the last, sends the report back to the author with your note.</p>
      </div></section>` : ''}`;
  $$('[data-export]').forEach((b) => b.onclick = () => download(`/api/reports/${report.id}/export?format=${b.dataset.export}`, `report.${b.dataset.export}`));
  if (!ws.can_review) return;
  if (S.reviewStarted !== report.id + ':' + report.version) {
    S.reviewStarted = report.id + ':' + report.version;
    api(`/api/reports/${report.id}/review/start`, { method: 'POST' }).catch(() => {});
  }
  const picked = {};
  $$('[data-q]').forEach((b) => b.onclick = () => {
    picked[b.dataset.q] = b.dataset.v;
    $$(`[data-q="${b.dataset.q}"]`).forEach((x) => x.setAttribute('aria-checked', String(x === b)));
    $$(`.reveal-on[data-for="${b.dataset.q}"]`).forEach((f) => { f.hidden = !f.dataset.when.split(',').includes(b.dataset.v); });
  });
  $$('[data-rec]').forEach((b) => b.onclick = () => { const t = $('#owned'); t.value = ex.recommendations[Number(b.dataset.rec)]; t.focus(); });
  const transition = async (body, button) => busy(button, async () => {
    await api(`/reports/${report.id}/transition`, { method: 'POST', body: { version: report.version, ...body } });
    S.pendingCount = Math.max(0, (S.pendingCount || 1) - 1);
    S.work = await api(`/api/reports/${report.id}`);
    if (S.work.workspace.workflow.status === 'HUMAN REVIEWED') { toast('Report approved'); renderWork('review'); }
    else { toast('Sent back to the author with your notes'); go('#/'); }
  });
  $('#approve').onclick = (e) => {
    const val = (id) => ($(`#${id}`)?.value || '').trim();
    const missing = ex.questions.find((q) => q.choices && !picked[q.id]) || (!val('owned') && ex.questions.find((q) => q.id === 'owned'));
    if (missing) { toast(`Answer "${missing.title}" first.`, true); $(`[data-question="${missing.id}"]`)?.scrollIntoView({ block: 'center' }); return; }
    const clearAnswers = { ...picked, owned: val('owned'), faithful_note: val('faithful_note'), caveat: val('caveat'),
      fairness_note: val('fairness_note'), fit_note: val('fit_note') };
    transition({ action: 'approve', role: $('#role').value, confirmed: true, clear: clearAnswers }, e.currentTarget);
  };
  $('#return').onclick = async (e) => {
    const r = await dialog({ title: 'Send back with notes', body: `Tell ${esc(report.owner_name || report.owner)} what to change. They'll see this at the top of the report.`, confirm: 'Send back',
      fields: '<label class="field"><span>Notes</span><textarea class="input" name="notes" required maxlength="5000"></textarea></label>' });
    if (r) transition({ action: 'return', notes: r.notes }, e.target);
  };
}

// ---- oversight (administrators): is the human review real? ------------------------------------
async function oversightView() {
  shell('oversight', '<div class="loading"><div class="spinner"></div>Loading the oversight panel…</div>');
  let o;
  try { o = await api('/api/oversight'); } catch (error) { $('#main').innerHTML = `<div class="page"><div class="notice bad">${esc(error.message)}</div></div>`; return; }
  const time = (sec) => sec === null || sec === undefined ? '—' : sec >= 60 ? `${Math.round(sec / 60)} min` : `${Math.round(sec)} s`;
  const pct = (v) => v === null || v === undefined ? '—' : `${Math.round(v)}%`;
  const t = o.totals;
  $('#main').innerHTML = `<div class="page oversight">
    <div class="hello"><h1>Oversight</h1><p>How the human review is really going. Every number comes from the audit chain.</p></div>
    <div class="clear-summary">
      <div class="big"><b>${t.reviews}</b><span>reviews</span></div>
      <div class="big"><b>${time(t.median_seconds)}</b><span>typical time per review</span></div>
      <div class="big"><b>${pct(t.concern_percent)}</b><span>raised a concern or caveat</span></div>
      <div class="big"><b>${pct(t.returned_percent)}</b><span>sent back to the author</span></div>
      <div class="big ${t.quick ? 'warn' : ''}"><b>${t.quick}</b><span>reviews under 2 minutes</span></div>
    </div>
    <h2 class="sub-head">Reviewers</h2>
    <div class="table-wrap" style="max-height:none"><table><thead><tr><th>Reviewer</th><th>Reviews</th><th>Approved</th><th>Sent back</th><th>Typical time</th><th>Raised a concern</th><th>Signals</th></tr></thead><tbody>
      ${o.reviewers.map((r) => `<tr><td><b>${esc(r.name)}</b></td><td>${r.reviews}</td><td>${r.approved}</td><td>${r.returned}</td><td>${time(r.median_seconds)}</td><td>${pct(r.concern_rate)}</td>
        <td>${r.flags.length ? r.flags.map((f) => `<span class="pill changes">${esc(f)}</span>`).join(' ') : '<span class="pill approved">Looks engaged</span>'}</td></tr>`).join('') || '<tr><td colspan="7">No reviews yet.</td></tr>'}
    </tbody></table></div>
    <h2 class="sub-head">Recent reviews</h2>
    <div class="table-wrap" style="max-height:none"><table><thead><tr><th>Report</th><th>Author</th><th>Reviewer</th><th>Decision</th><th>Level</th><th>Time</th><th>Concerns</th><th>When</th></tr></thead><tbody>
      ${o.recent.map((d) => `<tr><td>${esc(d.title)}</td><td>${esc(d.author_name)}</td><td>${esc(d.reviewer_name)}</td>
        <td><span class="pill ${d.decision === 'Approved' ? 'approved' : 'changes'}">${esc(d.decision)}</span></td>
        <td>${d.level === 'high' ? 'High risk' : d.level ? 'Standard' : '—'}</td><td>${time(d.seconds)}</td><td>${d.concerns ?? '—'}</td><td>${esc(ago(d.when))}</td></tr>`).join('') || '<tr><td colspan="8">No reviews yet.</td></tr>'}
    </tbody></table></div>
    <p class="faint" style="margin-top:14px">A reviewer is flagged after 5 reviews with no concern raised, or when their typical review takes under 2 minutes. Flags are prompts for a conversation, not a judgement.</p>
  </div>`;
}

// ---- accounts (administrators) -----------------------------------------------------------------
async function accountsView() {
  shell('accounts', '<div class="loading"><div class="spinner"></div>Loading accounts…</div>');
  let users;
  try { users = await api('/users'); } catch (error) { $('#main').innerHTML = `<div class="page"><div class="notice bad">${esc(error.message)}</div></div>`; return; }
  const waiting = users.filter((u) => !u.approved);
  const state = (u) => !u.approved ? '<span class="pill waiting">Waiting for approval</span>' : u.active ? '<span class="pill approved">Active</span>' : '<span class="pill draft">Disabled</span>';
  const me = S.user.username;
  $('#main').innerHTML = `<div class="page accounts">
    <div class="hello"><h1>Accounts</h1><p>${waiting.length ? `${waiting.length} ${waiting.length === 1 ? 'person is' : 'people are'} waiting for approval.` : 'Approve new people, change roles and reset passwords. Nobody, including you, can see passwords.'}</p></div>
    <div class="table-wrap" style="max-height:none"><table><thead><tr><th>Person</th><th>Email</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody>
    ${users.map((u) => `<tr><td><b>${esc(u.display_name || u.username)}</b><div class="faint">${esc(u.username)}${u.google ? ' · Google connected' : ''}</div></td>
      <td>${esc(u.email || '—')}</td><td>${u.role === 'admin' ? 'Administrator' : 'Member'}</td><td>${state(u)}</td>
      <td><div class="actions">${!u.approved
        ? `<button class="btn btn-good btn-sm" data-act="approve" data-user="${esc(u.username)}">Approve</button><button class="btn btn-bad btn-sm" data-act="reject" data-user="${esc(u.username)}">Reject</button>`
        : `${u.username !== me ? `<button class="btn btn-ghost btn-sm" data-act="role" data-user="${esc(u.username)}" data-role="${u.role}">${u.role === 'admin' ? 'Make member' : 'Make administrator'}</button>
           <button class="btn btn-ghost btn-sm" data-act="active" data-user="${esc(u.username)}" data-active="${u.active}">${u.active ? 'Disable' : 'Enable'}</button>` : ''}
           <button class="btn btn-quiet btn-sm" data-act="password" data-user="${esc(u.username)}">Reset password</button>`}</div></td></tr>`).join('')}
    </tbody></table></div></div>`;
  $$('[data-act]').forEach((b) => b.onclick = async () => {
    const user = encodeURIComponent(b.dataset.user);
    const act = b.dataset.act;
    let call, message;
    if (act === 'approve') { call = () => api(`/users/${user}/approve`, { method: 'POST' }); message = `${b.dataset.user} approved`; }
    if (act === 'reject') {
      if (!await dialog({ title: 'Reject this request?', body: `The account request from ${esc(b.dataset.user)} will be removed.`, confirm: 'Reject', danger: true })) return;
      call = () => api(`/users/${user}/reject`, { method: 'POST' }); message = 'Request rejected';
    }
    if (act === 'role') { const role = b.dataset.role === 'admin' ? 'member' : 'admin'; call = () => api(`/users/${user}/role`, { method: 'POST', body: { role } }); message = `${b.dataset.user} is now ${role === 'admin' ? 'an administrator' : 'a member'}`; }
    if (act === 'active') { const active = b.dataset.active !== 'true'; call = () => api(`/users/${user}/active?active=${active}`, { method: 'POST' }); message = `${b.dataset.user} ${active ? 'enabled' : 'disabled'}`; }
    if (act === 'password') {
      const r = await dialog({ title: `Reset password for ${esc(b.dataset.user)}`, body: 'Tell them the new password; they can change it in their profile.', confirm: 'Reset password',
        fields: '<label class="field"><span>New password</span><input class="input" name="password" type="text" minlength="8" required autocomplete="off"><small>At least 8 characters.</small></label>' });
      if (!r) return;
      call = () => api(`/users/${user}/password`, { method: 'POST', body: { new_password: r.password } }); message = 'Password reset';
    }
    await busy(b, async () => { await call(); toast(message); accountsView(); });
  });
}

// ---- profile -------------------------------------------------------------------------------------
async function profileView() {
  shell('', '<div class="loading"><div class="spinner"></div>Loading your profile…</div>');
  let me;
  try { me = await api('/auth/me'); } catch (error) { $('#main').innerHTML = `<div class="page"><div class="notice bad">${esc(error.message)}</div></div>`; return; }
  $('#main').innerHTML = `<div class="page narrow">
    <div class="hello"><h1>Your profile</h1><p>Signed in as ${esc(me.username)}${me.role === 'admin' ? ', administrator' : ''}.</p></div>
    <form id="details"><h2 style="margin-bottom:16px">Details</h2>
      <label class="field"><span>Full name</span><input class="input" name="display_name" value="${esc(me.display_name)}" maxlength="80"></label>
      <label class="field"><span>Email</span><input class="input" name="email" type="email" value="${esc(me.email)}"></label>
      ${me.has_password ? '<label class="field"><span>Current password</span><input class="input" name="current_password" type="password" autocomplete="current-password"><small>Only needed when you change your email.</small></label>' : ''}
      <label class="field"><span>Username</span><input class="input" value="${esc(me.username)}" disabled><small>Usernames can't change because reports and the audit log record them.</small></label>
      <button class="btn btn-primary">Save details</button></form>
    <form id="password" class="form-section"><h2 style="margin-bottom:16px">${me.has_password ? 'Change password' : 'Set a password'}</h2>
      ${me.has_password ? '<label class="field"><span>Current password</span><div class="reveal"><input class="input" name="current_password" type="password" autocomplete="current-password" required><button type="button" class="reveal-btn" aria-pressed="false">Show</button></div></label>' : ''}
      <label class="field"><span>New password</span><div class="reveal"><input class="input" name="new_password" type="password" autocomplete="new-password" minlength="8" required><button type="button" class="reveal-btn" aria-pressed="false">Show</button></div><small>At least 8 characters.</small></label>
      <button class="btn btn-primary">${me.has_password ? 'Change password' : 'Set password'}</button></form>
    <section class="form-section"><h2 style="margin-bottom:8px">Google</h2>
      <p class="muted" style="margin-bottom:14px">${me.google ? 'Connected. You can use Continue with Google to sign in.' : 'Not connected. Connect it to sign in with your Google account.'}</p>
      ${me.google ? '<button class="btn btn-ghost" id="unlink">Disconnect Google</button>' : S.config.google_web_client_id ? '<div id="link-google"></div>' : '<p class="faint">Google sign-in for the browser is not set up on this server yet.</p>'}
    </section></div>`;
  bindReveal($('#main'));
  $('#details').onsubmit = (e) => { e.preventDefault(); const d = Object.fromEntries(new FormData(e.target));
    busy($('button', e.target), async () => { const r = await api('/auth/me', { method: 'PATCH', body: d }); S.user.display_name = r.display_name; toast('Details saved'); profileView(); }); };
  $('#password').onsubmit = (e) => { e.preventDefault(); const d = Object.fromEntries(new FormData(e.target));
    busy($('button', e.target), async () => { await api('/auth/password', { method: 'POST', body: d }); toast('Password changed'); profileView(); }); };
  $('#unlink')?.addEventListener('click', (e) => busy(e.currentTarget, async () => { await api('/auth/google/link', { method: 'DELETE' }); toast('Google disconnected'); profileView(); }));
  if ($('#link-google')) googleButton($('#link-google'), async (credential) => {
    try { await api('/auth/google/link', { method: 'POST', body: { id_token: credential } }); toast('Google connected'); profileView(); }
    catch (error) { toast(error.message, true); }
  });
}

// ---- start --------------------------------------------------------------------------------------
restore().then(route);
