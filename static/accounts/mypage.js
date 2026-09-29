const myPage = document.querySelector('.mypage');
const workspace = document.querySelector('.mypage-workspace');
const identity = document.getElementById('mypage-identity');
const contextLabel = document.getElementById('mypage-context');
const pageStack = NiixyUI.createWorkspace(document.querySelector('.mypage-viewport'), {
  overview: {root: true},
  basic: {target: '.basic-info-pane'},
  interface: {target: '.interface-list-pane'},
  'interface-detail': {target: '.interface-detail-pane'},
  field: {target: '.field-list-pane'},
  'field-detail': {target: '.field-detail-pane'},
  'synonym-list': {target: '[data-mypage-pane="add-synonym-list"]'},
  'synonym-detail': {target: '[data-mypage-pane="add-synonym-detail"]'},
  'add-list': {target: '.add-field-list-pane'},
  'add-detail': {target: '.add-field-detail-pane'},
}, {track: workspace});

function updateContext(feature = null) {
  identity.disabled = !feature;
  contextLabel.hidden = !feature;
  const labels = {interface: '定義 > Interface', field: '定義 > Field', basic: '基本情報'};
  contextLabel.textContent = ` > ${labels[feature]}`;
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

async function openFieldList(updateHistory = true) {
  workspace.querySelector('.basic-info-pane, .interface-management')?.remove();
  const management = document.createElement('section');
  management.className = 'interface-management';
  const track = document.createElement('div');
  track.className = 'interface-track';
  const loading = loadingPane('field-list-pane', 'field-list');
  track.append(loading);
  management.append(track);
  workspace.append(management);
  pageStack.set('field');
  updateContext('field');
  if (updateHistory) history.pushState({}, '', `${myPage.dataset.paneUrl}?section=definition&kind=field`);
  let list;
  try { list = await NiixyUI.fetchFragment(myPage.dataset.fieldListUrl); } catch { NiixyUI.showPaneError(loading); return; }
  loading.replaceWith(list);
  bindFieldList(list);
}

function bindFieldList(list) {
  NiixyUI.bindTabs(list);
  list.querySelector('[data-close-field-list]')?.addEventListener('click', showOverview);
  list.querySelector('[data-field-create-url]')?.addEventListener('click', (event) => openFieldDetail(event.currentTarget.dataset.fieldCreateUrl));
  list.querySelectorAll('[data-detail-url]').forEach((item) => item.addEventListener('click', () => openFieldDetail(item.dataset.detailUrl)));
}

async function openFieldDetail(url) {
  interfaceTrack()?.querySelector('[data-mypage-pane="field-detail"]')?.remove();
  const loading = loadingPane('field-detail-pane', 'field-detail');
  interfaceTrack().append(loading);
  pageStack.set('field-detail');
  let detail;
  try { detail = await NiixyUI.fetchFragment(url); } catch { NiixyUI.showPaneError(loading); return; }
  loading.replaceWith(detail);
  bindFieldDetail(detail);
}

function bindFieldDetail(detail) {
  detail.querySelector('[data-close-field-detail]')?.addEventListener('click', () => pageStack.set('field'));
  detail.querySelector('[data-field-edit-url]')?.addEventListener('click', (event) => {
    event.preventDefault();
    openFieldDetail(event.currentTarget.href);
  });
  bindRemoveSynonymButtons(detail);
  detail.querySelector('[data-open-add-synonym]')?.addEventListener('click', async (event) => {
    interfaceTrack().querySelectorAll('[data-mypage-pane="add-synonym-list"], [data-mypage-pane="add-synonym-detail"]').forEach((pane) => pane.remove());
    const loading = loadingPane('add-field-list-pane', 'add-synonym-list');
    interfaceTrack().append(loading);
    pageStack.set('synonym-list');
    let pane;
    try { pane = await NiixyUI.fetchFragment(event.currentTarget.dataset.url); } catch { NiixyUI.showPaneError(loading); return; }
    loading.replaceWith(pane);
    bindSynonymList(pane);
  });
  detail.querySelectorAll('form').forEach((form) => form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    if (event.submitter) event.submitter.disabled = true;
    try {
      const response = await fetch(form.action, {method: 'POST', body: data});
      if (!response.ok) throw new Error('Field operation failed');
      const target = new URL(response.url);
      const fieldId = target.searchParams.get('field');
      await openFieldList(false);
      if (fieldId) await openFieldDetail(`/mypage/interfaces/manage/fields/${fieldId}/`);
    } catch {
      if (event.submitter) event.submitter.disabled = false;
    }
  }));
}

function bindSynonymList(pane) {
  NiixyUI.bindTabs(pane);
  pane.querySelector('[data-close-add-synonym]')?.addEventListener('click', () => pageStack.set('field-detail'));
  pane.querySelectorAll('[data-detail-url]').forEach((item) => item.addEventListener('click', async () => {
    interfaceTrack().querySelector('[data-mypage-pane="add-synonym-detail"]')?.remove();
    const loading = loadingPane('add-field-detail-pane', 'add-synonym-detail');
    interfaceTrack().append(loading);
    pageStack.set('synonym-detail');
    let detail;
    try { detail = await NiixyUI.fetchFragment(item.dataset.detailUrl); } catch { NiixyUI.showPaneError(loading); return; }
    loading.replaceWith(detail);
    bindSynonymDetail(detail);
  }));
}

function bindSynonymDetail(pane) {
  pane.querySelector('[data-back-add-synonym-list]')?.addEventListener('click', () => pageStack.set('synonym-list'));
  const button = pane.querySelector('[data-add-synonym]');
  const form = workspace.querySelector('#field-definition-form');
  const selected = Boolean(form?.querySelector(`#field-synonym-inputs [value="${pane.dataset.fieldId}"]`));
  const compatible = form?.querySelector('#id_field_type')?.value === pane.dataset.fieldType;
  button.disabled = selected || !compatible;
  button.textContent = selected ? '追加済み' : compatible ? '片同義に追加' : '型が異なります';
  button.addEventListener('click', () => {
    if (!form || button.disabled) return;
    const input = document.createElement('input');
    input.type = 'hidden'; input.name = 'synonym_targets'; input.value = pane.dataset.fieldId;
    form.querySelector('#field-synonym-inputs').append(input);
    form.querySelector('#empty-field-synonyms')?.remove();
    const item = document.createElement('div');
    item.className = 'selected-interface-require';
    item.dataset.selectedSynonym = pane.dataset.fieldId;
    item.innerHTML = `<span><strong></strong><small></small></span><button class="icon-button remove-field-synonym" type="button" aria-label="片同義を解除">×</button>`;
    item.querySelector('strong').textContent = `${pane.dataset.fieldName}@${pane.dataset.fieldCreator}`;
    item.querySelector('small').textContent = `v${pane.dataset.fieldVersion}/Field`;
    item.querySelector('button').dataset.fieldId = pane.dataset.fieldId;
    form.querySelector('#selected-field-synonyms').append(item);
    bindRemoveSynonymButtons(form);
    pageStack.set('field-detail');
  });
}

function bindRemoveSynonymButtons(root) {
  root.querySelectorAll('.remove-field-synonym:not([data-bound])').forEach((button) => {
    button.dataset.bound = 'true';
    button.addEventListener('click', () => {
      const form = workspace.querySelector('#field-definition-form');
      form?.querySelector(`#field-synonym-inputs [value="${button.dataset.fieldId}"]`)?.remove();
      button.closest('[data-selected-synonym]')?.remove();
    });
  });
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
  removePanes('interface-detail', 'add-field-list', 'add-field-detail');
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
    removePanes('interface-detail', 'add-field-list', 'add-field-detail');
    history.pushState({}, '', `${myPage.dataset.paneUrl}?section=interface`);
  });
  detail.querySelector('[data-open-add-field]')?.addEventListener('click', async (event) => {
    removePanes('add-field-list', 'add-field-detail');
    const loading = loadingPane('add-field-list-pane', 'add-field-list');
    interfaceTrack().append(loading);
    setInterfaceStage('add-list');
    let pane;
    try { pane = await NiixyUI.fetchFragment(event.currentTarget.dataset.url); } catch { NiixyUI.showPaneError(loading); return; }
    loading.replaceWith(pane);
    bindAddFieldList(pane);
  });
  detail.querySelectorAll('.interface-field-editor').forEach(bindFieldEditor);
  bindAjaxForms(detail);
}

function bindAddFieldList(pane) {
  NiixyUI.bindTabs(pane);
  pane.querySelector('[data-close-add-field]')?.addEventListener('click', () => setInterfaceStage('detail'));
  pane.querySelectorAll('[data-detail-url]').forEach((item) => item.addEventListener('click', async () => {
    removePanes('add-field-detail');
    const loading = loadingPane('add-field-detail-pane', 'add-field-detail');
    interfaceTrack().append(loading);
    setInterfaceStage('add-detail');
    let detail;
    try { detail = await NiixyUI.fetchFragment(item.dataset.detailUrl); } catch { NiixyUI.showPaneError(loading); return; }
    loading.replaceWith(detail);
    bindAddFieldDetail(detail);
  }));
}

function bindAddFieldDetail(pane) {
  pane.querySelector('[data-back-add-field-list]')?.addEventListener('click', () => setInterfaceStage('add-list'));
  const button = pane.querySelector('[data-add-field]');
  const selected = Boolean(workspace.querySelector(`[data-field-definition="${pane.dataset.fieldId}"]:not([hidden])`));
  button.disabled = selected;
  button.textContent = selected ? '使用中' : 'このFieldを使用';
  button.addEventListener('click', () => {
    if (workspace.querySelector(`[data-field-definition="${pane.dataset.fieldId}"]:not([hidden])`)) return;
    appendFieldFromPicker(pane);
    setInterfaceStage('detail');
  });
}

function bindFieldEditor(editor) {
  editor.querySelector('.remove-interface-field')?.addEventListener('click', () => {
    const input = editor.querySelector('input[name$="-DELETE"]');
    if (input) input.value = 'on';
    editor.hidden = true;
  });
}

function appendFieldFromPicker(pane) {
  const detail = workspace.querySelector('[data-mypage-pane="interface-detail"]');
  const total = detail.querySelector('#id_fields-TOTAL_FORMS');
  const template = detail.querySelector('#interface-field-template');
  const index = Number(total.value);
  const html = template.innerHTML.replaceAll('__prefix__', index);
  const wrapper = document.createElement('div');
  wrapper.innerHTML = html;
  const fragment = document.createDocumentFragment();
  while (wrapper.firstChild) fragment.append(wrapper.firstChild);
  const editor = fragment.querySelector('.interface-field-editor');
  editor.dataset.fieldDefinition = pane.dataset.fieldId;
  editor.querySelector('input[name$="-definition_id"]').value = pane.dataset.fieldId;
  editor.querySelector('.interface-field-identity strong').textContent = `${pane.dataset.fieldName}@${pane.dataset.fieldCreator}`;
  editor.querySelector('.interface-field-identity small').textContent = `v${pane.dataset.fieldVersion}/Field`;
  detail.querySelector('#empty-interface-fields')?.remove();
  detail.querySelector('#interface-field-list').append(fragment);
  total.value = index + 1;
  bindFieldEditor(editor);
}

document.getElementById('open-basic-info').addEventListener('click', () => openBasic());
document.getElementById('open-field').addEventListener('click', () => openFieldList());
document.getElementById('open-interface').addEventListener('click', () => openInterfaceList());
identity.addEventListener('click', showOverview);

const initialParams = new URLSearchParams(location.search);
if (initialParams.get('section') === 'definition' && initialParams.get('kind') === 'field') {
  openFieldList(false).then(async () => {
    if (initialParams.get('field')) await openFieldDetail(`/mypage/interfaces/manage/fields/${initialParams.get('field')}/`);
  });
} else if (initialParams.get('section') === 'interface') {
  openInterfaceList(false).then(async () => {
    if (initialParams.get('draft')) await openInterfaceDetail(`/mypage/interfaces/manage/drafts/${initialParams.get('draft')}/`);
    else if (initialParams.get('interface')) await openInterfaceDetail(`/mypage/interfaces/manage/${initialParams.get('interface')}/`);
  });
} else if (myPage.dataset.initialSection === 'basic') openBasic(false);
else updateContext();
