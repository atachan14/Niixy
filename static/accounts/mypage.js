const myPage = document.querySelector('.mypage');
const workspace = document.querySelector('.mypage-workspace');
const identity = document.getElementById('mypage-identity');
const contextLabel = document.getElementById('mypage-context');
const pageStack = NiixyUI.createWorkspace(document.querySelector('.mypage-viewport'), {
  overview: {root: true},
  basic: {target: '.basic-info-pane'},
  interface: {target: '.interface-list-pane'},
  'interface-detail': {target: '.interface-detail-pane'},
  'add-list': {target: '.add-require-list-pane'},
  'add-detail': {target: '.add-require-detail-pane'},
}, {track: workspace});

function updateContext(feature = null) {
  identity.disabled = !feature;
  contextLabel.hidden = !feature;
  contextLabel.textContent = ` > ${feature === 'interface' ? 'Interface' : '基本情報'}`;
}

function showOverview() {
  pageStack.set('overview');
  updateContext();
  history.pushState({}, '', myPage.dataset.paneUrl);
}

function loadingPane(className, paneName) {
  return NiixyUI.createStatusPane({
    tagName: className === 'interface-detail-pane' ? 'aside' : 'section',
    className,
    attributes: {mypagePane: paneName},
  });
}

const interfaceTrack = () => workspace.querySelector('.interface-track');

function setInterfaceStage(stage) {
  const pageStage = {list: 'interface', detail: 'interface-detail', 'add-list': 'add-list', 'add-detail': 'add-detail'}[stage];
  if (pageStage) pageStack.set(pageStage);
}

function removePanes(...names) {
  names.forEach((name) => interfaceTrack()?.querySelector(`[data-mypage-pane="${name}"]`)?.remove());
}

async function openBasic(updateHistory = true) {
  const url = new URL(myPage.dataset.paneUrl, location.origin);
  url.searchParams.set('_panes', '1');
  workspace.querySelector('.basic-info-pane, .interface-management')?.remove();
  const loading = loadingPane('basic-info-pane', 'basic-info');
  workspace.append(loading);
  pageStack.set('basic');
  updateContext('basic');
  if (updateHistory) history.pushState({}, '', myPage.dataset.paneUrl);
  let pane;
  try { pane = await NiixyUI.fetchFragment(url, '.basic-info-pane'); } catch { NiixyUI.showPaneError(loading); return; }
  loading.replaceWith(pane);
  pane.querySelector('#close-basic-info')?.addEventListener('click', showOverview);
  setTimeout(() => pane.querySelector('#id_display_name')?.focus(), 260);
}

async function openInterfaceList(updateHistory = true) {
  workspace.querySelector('.basic-info-pane, .interface-management')?.remove();
  const management = document.createElement('section');
  management.className = 'interface-management';
  const track = document.createElement('div');
  track.className = 'interface-track';
  const loading = loadingPane('interface-list-pane', 'interface-list');
  track.append(loading);
  management.append(track);
  workspace.append(management);
  pageStack.set('interface');
  updateContext('interface');
  if (updateHistory) history.pushState({}, '', `${myPage.dataset.paneUrl}?section=interface`);
  let list;
  try { list = await NiixyUI.fetchFragment(myPage.dataset.interfaceListUrl); } catch { NiixyUI.showPaneError(loading); return; }
  loading.replaceWith(list);
  bindInterfaceList(list);
}

function bindInterfaceList(list) {
  NiixyUI.bindTabs(list);
  list.querySelector('[data-close-interface-list]')?.addEventListener('click', showOverview);
  list.addEventListener('click', async (event) => {
    const item = event.target.closest('[data-detail-url]');
    if (!item) return;
    event.preventDefault();
    await openInterfaceDetail(item.dataset.detailUrl, item.getAttribute('href'));
  });
  bindAjaxForms(list);
}

async function openInterfaceDetail(url, historyUrl = null) {
  removePanes('interface-detail', 'add-require-list', 'add-require-detail');
  const loading = loadingPane('interface-detail-pane', 'interface-detail');
  interfaceTrack().append(loading);
  setInterfaceStage('detail');
  if (historyUrl) history.pushState({}, '', historyUrl);
  let detail;
  try { detail = await NiixyUI.fetchFragment(url); } catch { NiixyUI.showPaneError(loading); return; }
  loading.replaceWith(detail);
  bindInterfaceDetail(detail);
}

function bindAjaxForms(root) {
  root.querySelectorAll('form').forEach((form) => form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const refreshInterfaceList = form.hasAttribute('data-refresh-interface-list');
    const data = new FormData(form);
    if (event.submitter?.name) data.set(event.submitter.name, event.submitter.value);
    if (event.submitter) event.submitter.disabled = true;
    try {
      const response = await fetch(form.action || location.href, {method: 'POST', body: data});
      if (!response.ok) throw new Error('Interface operation failed');
      if (refreshInterfaceList) {
        await openInterfaceList(true);
        return;
      }
      const target = new URL(response.url);
      const draftId = target.searchParams.get('draft');
      const interfaceId = target.searchParams.get('interface');
      if (draftId) await openInterfaceDetail(`/mypage/interfaces/manage/drafts/${draftId}/`, `${target.pathname}${target.search}`);
      else if (interfaceId) await openInterfaceDetail(`/mypage/interfaces/manage/${interfaceId}/`, `${target.pathname}${target.search}`);
      else await openInterfaceList(true);
    } catch {
      if (event.submitter) event.submitter.disabled = false;
    }
  }));
}

function bindInterfaceDetail(detail) {
  detail.querySelector('[data-close-interface-detail]')?.addEventListener('click', () => {
    setInterfaceStage('list');
    removePanes('interface-detail', 'add-require-list', 'add-require-detail');
    history.pushState({}, '', `${myPage.dataset.paneUrl}?section=interface`);
  });
  detail.querySelector('[data-open-add-require]')?.addEventListener('click', async (event) => {
    removePanes('add-require-list', 'add-require-detail');
    const loading = loadingPane('add-require-list-pane', 'add-require-list');
    interfaceTrack().append(loading);
    setInterfaceStage('add-list');
    let pane;
    try { pane = await NiixyUI.fetchFragment(event.currentTarget.dataset.url); } catch { NiixyUI.showPaneError(loading); return; }
    loading.replaceWith(pane);
    bindAddRequireList(pane);
  });
  detail.querySelectorAll('.interface-field-editor').forEach(bindFieldEditor);
  detail.querySelector('#add-interface-field')?.addEventListener('click', () => addField(detail));
  bindRemoveRequireButtons(detail);
  bindAjaxForms(detail);
}

function bindAddRequireList(pane) {
  NiixyUI.bindTabs(pane);
  pane.querySelector('[data-close-add-require]')?.addEventListener('click', () => setInterfaceStage('detail'));
  pane.querySelectorAll('[data-detail-url]').forEach((item) => item.addEventListener('click', async () => {
    removePanes('add-require-detail');
    const loading = loadingPane('add-require-detail-pane', 'add-require-detail');
    interfaceTrack().append(loading);
    setInterfaceStage('add-detail');
    let detail;
    try { detail = await NiixyUI.fetchFragment(item.dataset.detailUrl); } catch { NiixyUI.showPaneError(loading); return; }
    loading.replaceWith(detail);
    bindAddRequireDetail(detail);
  }));
}

function bindAddRequireDetail(pane) {
  pane.querySelector('[data-back-add-require-list]')?.addEventListener('click', () => setInterfaceStage('add-list'));
  const button = pane.querySelector('.add-interface-require');
  const inputs = workspace.querySelector('#interface-require-inputs');
  const selected = Boolean(inputs?.querySelector(`[value="${pane.dataset.requireId}"]`));
  button.disabled = selected;
  button.textContent = selected ? '追加済み' : '追加';
  button.addEventListener('click', () => {
    if (!inputs || inputs.querySelector(`[value="${pane.dataset.requireId}"]`)) return;
    const input = document.createElement('input');
    input.type = 'hidden'; input.name = 'required_interfaces'; input.value = pane.dataset.requireId;
    inputs.append(input);
    workspace.querySelector('#empty-interface-requires')?.remove();
    workspace.querySelector('#selected-interface-requires').append(pane.querySelector('[data-require-summary]').content.cloneNode(true));
    workspace.querySelector('#required-interface-field-groups').append(pane.querySelector('[data-require-fields]').content.cloneNode(true));
    bindRemoveRequireButtons(workspace);
    button.disabled = true; button.textContent = '追加済み';
  });
}

function bindRemoveRequireButtons(root) {
  root.querySelectorAll('.remove-interface-require:not([data-bound])').forEach((button) => {
    button.dataset.bound = 'true';
    button.addEventListener('click', () => {
      workspace.querySelector(`#interface-require-inputs [value="${button.dataset.requireId}"]`)?.remove();
      workspace.querySelector(`[data-selected-require="${button.dataset.requireId}"]`)?.remove();
      workspace.querySelector(`[data-required-field-group="${button.dataset.requireId}"]`)?.remove();
    });
  });
}

function bindFieldEditor(editor) {
  const select = editor.querySelector('select[name$="-field_type"]');
  const update = () => editor.querySelector('.interface-options-field')?.toggleAttribute('hidden', !['single_choice', 'multiple_choice'].includes(select?.value));
  update();
  select?.addEventListener('change', update);
  editor.querySelector('.remove-interface-field')?.addEventListener('click', () => {
    const input = editor.querySelector('input[name$="-DELETE"]');
    if (input) input.value = 'on';
    editor.hidden = true;
  });
}

function addField(detail) {
  const total = detail.querySelector('#id_fields-TOTAL_FORMS');
  const template = detail.querySelector('#interface-field-template');
  const index = Number(total.value);
  const fragment = template.content.cloneNode(true);
  fragment.querySelectorAll('[name], [id], label[for]').forEach((element) => {
    if (element.name) element.name = element.name.replaceAll('__prefix__', index);
    if (element.id) element.id = element.id.replaceAll('__prefix__', index);
    if (element.htmlFor) element.htmlFor = element.htmlFor.replaceAll('__prefix__', index);
  });
  const editor = fragment.querySelector('.interface-field-editor');
  detail.querySelector('#interface-field-list').append(fragment);
  total.value = index + 1;
  bindFieldEditor(editor);
  editor.querySelector('input[name$="-label"]')?.focus();
}

document.getElementById('open-basic-info').addEventListener('click', () => openBasic());
document.getElementById('open-interface').addEventListener('click', () => openInterfaceList());
identity.addEventListener('click', showOverview);

const initialParams = new URLSearchParams(location.search);
if (initialParams.get('section') === 'interface') {
  openInterfaceList(false).then(async () => {
    if (initialParams.get('draft')) await openInterfaceDetail(`/mypage/interfaces/manage/drafts/${initialParams.get('draft')}/`);
    else if (initialParams.get('interface')) await openInterfaceDetail(`/mypage/interfaces/manage/${initialParams.get('interface')}/`);
  });
} else if (myPage.dataset.initialSection === 'basic') openBasic(false);
else updateContext();
