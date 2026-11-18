// Run with: node --test tools/tests/test_superadmin_browser.mjs
// Exercise the actual dashboard and busy handler with an in-memory API and DOM.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import test from 'node:test';

const source = await readFile(new URL('../../ai-learning-evaluation/web/app.js', import.meta.url), 'utf8');
const view = source.slice(source.indexOf('async function accountsView()'), source.indexOf('// ---- profile'));
const busy = source.slice(source.indexOf('async function busy('), source.indexOf('\nfunction dialog('));
const home = source.slice(source.indexOf('async function homeView()'), source.indexOf('\nfunction person('));
const router = source.slice(source.indexOf('async function route()'), source.indexOf("window.addEventListener('hashchange'"));
const escape = source.split('\n').find((line) => line.startsWith('const esc ='));
const roleLabels = source.slice(source.indexOf('const ROLE_LABELS ='), source.indexOf('\n};', source.indexOf('const ROLE_LABELS =')) + 3);
const roleHelpers = source.split('\n').filter((line) => /^const (roleLabel|canManageUsers|canReview) =/.test(line)).join('\n');
export const results = [];

async function check(name, work) {
  let failure;
  await test(name, async () => {
    try { await work(); results.push({ name, passed: true }); }
    catch (error) { failure = error; throw error; }
  });
  if (failure) throw failure;
}

function fixture(active = 1, operatorRole = 'superadmin', targetRole = 'member') {
  const roles = ['member', 'admin', 'facilitator', 'client', 'superadmin'];
  const users = [
    { username: 'owner', display_name: 'Owner', email: '', role: 'superadmin', active: 1, approved: 1 },
    { username: 'target', display_name: 'Test Person', email: 'person@example.com', role: targetRole, active, approved: 1 },
  ];
  const calls = [], messages = [], answers = [], dialogs = [], redirects = [];
  let buttons = [], rowButtons = [], html = '', rowsHtml = '', failActive = false, nodes = {};
  let reportsGate, usersGate;
  const attributes = (text) => Object.fromEntries([...text.matchAll(/([\w-]+)="([^"]*)"/g)].map((m) => [m[1], m[2]]));
  const element = (text, innerHTML) => {
    const attrs = attributes(text);
    const node = { id: attrs.id, innerHTML, disabled: false,
      dataset: Object.fromEntries(Object.entries(attrs).filter(([key]) => key.startsWith('data-')).map(([key, value]) => [key.slice(5), value])) };
    node.closest = () => node;
    return node;
  };
  const parseButtons = (value) => [...value.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)].map((m) => element(m[1], m[2]));
  const main = {
    get innerHTML() { return html; },
    set innerHTML(value) {
      html = value;
      buttons = parseButtons(value);
      rowButtons = [];
      nodes = {
        'user-search': { value: '' },
        'user-role-filter': { value: '' },
        'user-rows': {
          get innerHTML() { return rowsHtml; },
          set innerHTML(rows) { rowsHtml = rows; rowButtons = parseButtons(rows); },
        },
      };
    },
  };
  const context = vm.createContext({
    S: { user: { username: 'owner', role: operatorRole }, config: { user_roles: roles }, navigation: 0 },
    location: { hash: '#/superadmin' },
    document: { body: { contains: (node) => [...buttons, ...rowButtons].includes(node) } },
    $: (selector) => selector === '#main' ? main : nodes[selector.slice(1)] || buttons.find((node) => '#' + node.id === selector),
    $$: () => [],
    shell: (active, content) => { main.innerHTML = content; }, go: (path) => redirects.push(path),
    greeting: () => 'Hello', firstName: () => 'Owner', bindUpload: () => {},
    toast: (message, bad) => messages.push({ message, bad: Boolean(bad) }),
    dialog: async (options) => {
      dialogs.push(options);
      const answer = answers.shift() ?? null;
      if (answer && options.validate) assert.equal(options.validate(answer), '');
      return answer;
    },
    api: async (path, options = {}) => {
      calls.push({ path, method: options.method || 'GET', body: options.body });
      if (path.startsWith('/reports?view=')) return reportsGate ? await reportsGate.promise : [];
      if (path === '/users' && !options.method) {
        if (usersGate) await usersGate.promise;
        return structuredClone(users);
      }
      if (path === '/users' && options.method === 'POST') {
        users.push({ ...options.body, active: 1, approved: 1 });
        return { username: options.body.username, role: options.body.role };
      }
      const match = /^\/users\/([^/?]+)(?:\/(\w+))?(?:\?active=(true|false))?$/.exec(path);
      assert.ok(match, `Unexpected API path: ${path}`);
      const user = users.find((u) => u.username === decodeURIComponent(match[1]));
      assert.ok(user);
      if (match[2] === 'active') {
        if (failActive) throw new Error('Could not update account');
        user.active = match[3] === 'true' ? 1 : 0;
      } else if (options.method === 'PATCH') Object.assign(user, options.body);
      else if (options.method === 'DELETE') users.splice(users.indexOf(user), 1);
      else throw new Error(`Unexpected operation: ${options.method} ${path}`);
      return { username: user.username };
    },
  });
  vm.runInContext(`${roleLabels}\n${roleHelpers}\n${escape}\n${busy}\n${view}\n${home}\n${router}`, context);
  const button = (action, username = 'target') => rowButtons.find((node) => node.dataset.act === action && node.dataset.user === username);
  return {
    users, calls, messages, answers, dialogs, redirects, main, button,
    render: () => context.accountsView(),
    navigate: (hash) => { context.location.hash = hash; return context.route(); },
    byId: (id) => nodes[id] || buttons.find((node) => node.id === id),
    click: (action, username) => nodes['user-rows'].onclick({ target: button(action, username) }),
    failActive() { failActive = true; },
    holdReports() { reportsGate = deferred(); return reportsGate; },
    holdUsers() { usersGate = deferred(); return usersGate; },
  };
}

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

for (const active of [1, true, 0, false]) {
  await check(`Enable/Disable round trips from API status ${JSON.stringify(active)}`, async () => {
    const app = fixture(active);
    await app.render();
    let enabled = Boolean(active);
    for (let step = 0; step < 4; step++) {
      assert.equal(app.button('active').innerHTML, enabled ? 'Disable' : 'Enable');
      await app.click('active');
      enabled = !enabled;
      assert.equal(Boolean(app.users[1].active), enabled);
      assert.equal(app.button('active').innerHTML, enabled ? 'Disable' : 'Enable');
      assert.equal(app.button('active').disabled, false);
    }
  });
}

await check('Failed status changes keep the previous label and allow retry', async () => {
  const app = fixture();
  await app.render();
  app.failActive();
  await app.click('active');
  assert.equal(app.button('active').innerHTML, 'Disable');
  assert.equal(app.button('active').disabled, false);
  assert.equal(app.users[1].active, 1);
  assert.ok(app.messages.some((item) => item.bad && item.message === 'Could not update account'));
});

for (const role of ['facilitator', 'client']) {
  await check(`Editing a ${role} preserves its role and exposes all five choices`, async () => {
    const app = fixture(1, 'superadmin', role);
    await app.render();
    app.answers.push({ display_name: 'Updated Person', email: 'updated@example.com', role });
    await app.click('edit');
    assert.equal(app.users[1].role, role);
    assert.equal(app.users[1].display_name, 'Updated Person');
    assert.ok(app.dialogs[0].fields.includes(`value="${role}" selected`));
    for (const option of ['facilitator', 'client', 'superadmin']) {
      assert.ok(app.dialogs[0].fields.includes(`value="${option}"`));
      assert.ok(app.main.innerHTML.includes(`value="${option}"`));
    }
  });
}

await check('Creating a facilitator uses the existing superadmin form', async () => {
  const app = fixture();
  await app.render();
  app.answers.push({ username: 'new.person', display_name: 'New Person', email: 'new@example.com',
    role: 'facilitator', password: 'new-person-pass', confirm: 'new-person-pass' });
  const create = app.byId('create-user');
  await create.onclick({ currentTarget: create });
  assert.equal(app.users.find((u) => u.username === 'new.person').role, 'facilitator');
  assert.ok(app.button('edit', 'new.person'));
  assert.equal(app.calls.find((call) => call.method === 'POST').body.confirm, undefined);
});

await check('Role filtering includes existing facilitator accounts', async () => {
  const app = fixture(1, 'superadmin', 'facilitator');
  await app.render();
  app.byId('user-role-filter').value = 'facilitator';
  app.byId('user-role-filter').onchange();
  assert.ok(app.button('edit', 'target'));
  assert.equal(app.button('edit', 'owner'), undefined);
});

await check('Removing a user requires confirmation and refreshes the table', async () => {
  const app = fixture();
  await app.render();
  app.answers.push(null);
  await app.click('remove');
  assert.equal(app.calls.filter((call) => call.method === 'DELETE').length, 0);
  app.answers.push({});
  await app.click('remove');
  assert.equal(app.calls.filter((call) => call.method === 'DELETE').length, 1);
  assert.equal(app.button('edit'), undefined);
});

for (const role of ['member', 'admin', 'facilitator', 'client']) {
  await check(`${role} cannot open the user-management dashboard`, async () => {
    const app = fixture(1, role);
    await app.render();
    assert.deepEqual(app.redirects, ['#/']);
    assert.equal(app.calls.length, 0);
  });
}

await check('The signed-in superadmin has no self-disable or self-remove controls', async () => {
  const app = fixture();
  await app.render();
  assert.equal(app.button('active', 'owner'), undefined);
  assert.equal(app.button('remove', 'owner'), undefined);
});

await check('A late report response cannot replace the superadmin dashboard', async () => {
  const app = fixture();
  const pending = app.holdReports();
  const reports = app.navigate('#/');
  await app.navigate('#/superadmin');
  pending.resolve([]);
  await reports;
  assert.ok(app.main.innerHTML.includes('Superadmin dashboard'));
  assert.ok(app.button('active'));
});

await check('A late report failure cannot overwrite a newer dashboard', async () => {
  const app = fixture();
  const pending = app.holdReports();
  const reports = app.navigate('#/');
  await app.navigate('#/superadmin');
  pending.reject(new Error('Old report request failed'));
  await reports;
  assert.ok(app.main.innerHTML.includes('Superadmin dashboard'));
  assert.ok(!app.main.innerHTML.includes('Old report request failed'));
});

await check('A late account response cannot replace the reports screen', async () => {
  const app = fixture();
  const pending = app.holdUsers();
  const dashboard = app.navigate('#/superadmin');
  await app.navigate('#/');
  pending.resolve();
  await dashboard;
  assert.ok(app.main.innerHTML.includes('Start a new report'));
  assert.ok(!app.main.innerHTML.includes('Superadmin dashboard'));
});
