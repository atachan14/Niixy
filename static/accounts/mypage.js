const myPage = document.querySelector('.mypage');
const workspace = document.querySelector('.mypage-workspace');
const identity = document.getElementById('mypage-identity');
const pageStack = NiixyUI.createWorkspace(document.querySelector('.mypage-viewport'), {
  overview: {root: true},
  basic: {target: '.basic-info-pane'},
  module: {target: '.module-list-pane'},
  'interface-detail': {target: '.interface-detail-pane'},
  'field-detail': {target: '.field-detail-pane'},
  'synonym-list': {target: '[data-mypage-pane="add-synonym-list"]'},
  'synonym-detail': {target: '[data-mypage-pane="add-synonym-detail"]'},
  'add-list': {target: '.add-field-list-pane'},
  'add-detail': {target: '.add-field-detail-pane'},
}, {track: workspace});

function updateHeaderNavigation(feature = null) {
  identity.disabled = !feature;
}

function showOverview() {
  pageStack.set('overview');
  updateHeaderNavigation();
  history.pushState({}, '', myPage.dataset.paneUrl);
}

function loadingPane(className, paneName) {
  return NiixyUI.createStatusPane({
    tagName: className === 'interface-detail-pane' ? 'aside' : 'section',
    className,
    attributes: {mypagePane: paneName},
  });
}

const moduleTrack = () => workspace.querySelector('.module-track');

function setInterfaceStage(stage) {
  const pageStage = {list: 'module', detail: 'interface-detail', 'add-list': 'add-list', 'add-detail': 'add-detail'}[stage];
  if (pageStage) pageStack.set(pageStage);
}

function removePanes(...names) {
  names.forEach((name) => moduleTrack()?.querySelector(`[data-mypage-pane="${name}"]`)?.remove());
}

function removeModuleDetailPanes() {
  removePanes(
    'field-detail',
    'add-synonym-list',
    'add-synonym-detail',
    'interface-detail',
    'add-field-list',
    'add-field-detail',
  );
}

async function openBasic(updateHistory = true) {
  const url = new URL(myPage.dataset.paneUrl, location.origin);
  url.searchParams.set('_panes', '1');
  workspace.querySelector('.basic-info-pane, .module-management, .interface-management')?.remove();
  const loading = loadingPane('basic-info-pane', 'basic-info');
  workspace.append(loading);
  pageStack.set('basic');
  updateHeaderNavigation('basic');
  if (updateHistory) history.pushState({}, '', myPage.dataset.paneUrl);
  let pane;
  try { pane = await NiixyUI.fetchFragment(url, '.basic-info-pane'); } catch { NiixyUI.showPaneError(loading); return; }
  loading.replaceWith(pane);
  pane.querySelector('#close-basic-info')?.addEventListener('click', showOverview);
  setTimeout(() => pane.querySelector('#id_display_name')?.focus(), 260);
}

function currentModuleState(defaultType = 'element') {
  const params = new URLSearchParams(location.search);
  const requestedType = params.get('type') || defaultType;
  const type = requestedType === 'field' ? 'element' : requestedType;
  return {
    type,
    subtype: requestedType === 'field'
      ? 'field'
      : params.get('subtype') || ({element: 'field', interface: 'thread', layout: 'thread_post'}[type]),
    collection: params.get('collection') || (params.has('draft') ? 'editing' : 'self'),
  };
}

function moduleLocation(state) {
  const params = new URLSearchParams({section: 'module', type: state.type});
  params.set('subtype', state.subtype);
  if (state.collection !== 'self') params.set('collection', state.collection);
  return `${myPage.dataset.paneUrl}?${params}`;
}

async function openModuleList(initialState = currentModuleState(), updateHistory = true) {
  workspace.querySelector('.basic-info-pane, .module-management, .interface-management')?.remove();
  const management = document.createElement('section');
  management.className = 'module-management';
  const track = document.createElement('div');
  track.className = 'module-track';
  const loading = loadingPane('module-list-pane', 'module-list');
  track.append(loading);
  management.append(track);
  workspace.append(management);
  pageStack.set('module');
  updateHeaderNavigation('module');
  if (updateHistory) history.pushState({}, '', moduleLocation(initialState));
  let list;
  try { list = await NiixyUI.fetchFragment(myPage.dataset.moduleListUrl); } catch { NiixyUI.showPaneError(loading); return; }
  loading.replaceWith(list);
  bindModuleList(list, initialState);
}

function openInterfaceList(updateHistory = true) {
  const state = currentModuleState('interface');
  state.type = 'interface';
  if (!['account', 'thread', 'thread_post'].includes(state.subtype)) state.subtype = 'thread';
  return openModuleList(state, updateHistory);
}

function openFieldList(updateHistory = true) {
  const state = currentModuleState('element');
  state.type = 'element';
  state.subtype = 'field';
  return openModuleList(state, updateHistory);
}

function bindModuleList(list, initialState) {
  NiixyUI.bindModuleFilters(list, initialState, {
    onChange: (state) => history.replaceState({}, '', moduleLocation(state)),
  });
  list.querySelector('[data-close-module-list]')?.addEventListener('click', showOverview);
  list.querySelector('[data-field-create-url]')?.addEventListener('click', (event) => openFieldDetail(event.currentTarget.dataset.fieldCreateUrl));
  bindFieldSearch(list);
  list.addEventListener('click', (event) => {
    const item = event.target.closest('[data-detail-url]');
    if (!item) return;
    event.preventDefault();
    const [type, subtype] = item.closest('[data-module-panel]').dataset.modulePanel.split(':');
    if (type === 'element' && subtype === 'field') openFieldDetail(item.dataset.detailUrl);
    else if (type === 'interface') openInterfaceDetail(item.dataset.detailUrl, item.getAttribute('href'));
  });
  bindAjaxForms(list);
}

function bindFieldSearch(list) {
  const form = list.querySelector('[data-field-search-form]');
  if (!form) return;

  const loadResults = async (url) => {
    const current = list.querySelector('[data-field-search-results]');
    current.setAttribute('aria-busy', 'true');
    try {
      const results = await NiixyUI.fetchFragment(url, '[data-field-search-results]');
      current.replaceWith(results);
    } catch {
      current.removeAttribute('aria-busy');
    }
  };

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const url = new URL(form.action, location.origin);
    new FormData(form).forEach((value, key) => {
      if (String(value).trim()) url.searchParams.set(key, value);
    });
    const details = form.closest('details');
    if (details?.open) details.querySelector(':scope > summary')?.click();
    loadResults(url);
  });

  list.addEventListener('click', (event) => {
    const link = event.target.closest('[data-field-search-page]');
    if (!link) return;
    event.preventDefault();
    loadResults(new URL(link.href, location.origin));
  });
}

async function openFieldDetail(url) {
  removeModuleDetailPanes();
  const loading = loadingPane('field-detail-pane', 'field-detail');
  moduleTrack().append(loading);
  pageStack.set('field-detail');
  let detail;
  try { detail = await NiixyUI.fetchFragment(url); } catch { NiixyUI.showPaneError(loading); return; }
  loading.replaceWith(detail);
  bindFieldDetail(detail);
}

function bindFieldDetail(detail) {
  detail.querySelector('[data-close-field-detail]')?.addEventListener('click', () => {
    pageStack.set('module');
    removePanes('field-detail', 'add-synonym-list', 'add-synonym-detail');
    history.pushState({}, '', moduleLocation(currentModuleState('field')));
  });
  detail.querySelector('[data-field-edit-url]')?.addEventListener('click', (event) => {
    event.preventDefault();
    openFieldDetail(event.currentTarget.href);
  });
  bindRemoveSynonymButtons(detail);
  detail.querySelector('[data-open-add-synonym]')?.addEventListener('click', async (event) => {
    moduleTrack().querySelectorAll('[data-mypage-pane="add-synonym-list"], [data-mypage-pane="add-synonym-detail"]').forEach((pane) => pane.remove());
    const loading = loadingPane('add-field-list-pane', 'add-synonym-list');
    moduleTrack().append(loading);
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
    moduleTrack().querySelector('[data-mypage-pane="add-synonym-detail"]')?.remove();
    const loading = loadingPane('add-field-detail-pane', 'add-synonym-detail');
    moduleTrack().append(loading);
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

async function openInterfaceDetail(url, historyUrl = null) {
  removeModuleDetailPanes();
  const loading = loadingPane('interface-detail-pane', 'interface-detail');
  moduleTrack().append(loading);
  setInterfaceStage('detail');
  if (historyUrl) history.pushState({}, '', historyUrl);
  let detail;
  try { detail = await NiixyUI.fetchFragment(url); } catch { NiixyUI.showPaneError(loading); return; }
  loading.replaceWith(detail);
  bindInterfaceDetail(detail);
}

function bindAjaxForms(root) {
  root.querySelectorAll('form:not([data-field-search-form])').forEach((form) => form.addEventListener('submit', async (event) => {
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
      if (draftId) {
        await openModuleList({
          type: 'interface',
          subtype: target.searchParams.get('subtype') || 'thread',
          collection: 'editing',
        }, false);
        await openInterfaceDetail(`/mypage/interfaces/manage/drafts/${draftId}/`, `${target.pathname}${target.search}`);
      }
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
    history.pushState({}, '', moduleLocation(currentModuleState('interface')));
  });
  detail.querySelector('[data-open-add-field]')?.addEventListener('click', async (event) => {
    removePanes('add-field-list', 'add-field-detail');
    const loading = loadingPane('add-field-list-pane', 'add-field-list');
    moduleTrack().append(loading);
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
    moduleTrack().append(loading);
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
document.getElementById('open-module').addEventListener('click', () => openModuleList({
  type: 'element',
  subtype: 'field',
  collection: 'self',
}));
identity.addEventListener('click', showOverview);

const initialParams = new URLSearchParams(location.search);
if (initialParams.get('section') === 'module') {
  const type = initialParams.get('type') || 'field';
  openModuleList(currentModuleState(type), false).then(async () => {
    if (initialParams.get('field_edit')) await openFieldDetail(`/mypage/interfaces/manage/fields/${initialParams.get('field_edit')}/edit/`);
    else if (initialParams.get('field')) await openFieldDetail(`/mypage/interfaces/manage/fields/${initialParams.get('field')}/`);
    if (initialParams.get('draft')) await openInterfaceDetail(`/mypage/interfaces/manage/drafts/${initialParams.get('draft')}/`);
    else if (initialParams.get('interface')) await openInterfaceDetail(`/mypage/interfaces/manage/${initialParams.get('interface')}/`);
  });
} else if (initialParams.get('section') === 'definition' && initialParams.get('kind') === 'field') {
  history.replaceState({}, '', `${myPage.dataset.paneUrl}?section=module&type=element&subtype=field${initialParams.get('field') ? `&field=${initialParams.get('field')}` : ''}`);
  openFieldList(false).then(async () => {
    if (initialParams.get('field')) await openFieldDetail(`/mypage/interfaces/manage/fields/${initialParams.get('field')}/`);
  });
} else if (initialParams.get('section') === 'interface') {
  const legacyTarget = `${myPage.dataset.paneUrl}?section=module&type=interface&subtype=thread${initialParams.get('draft') ? `&collection=editing&draft=${initialParams.get('draft')}` : ''}${initialParams.get('interface') ? `&interface=${initialParams.get('interface')}` : ''}`;
  history.replaceState({}, '', legacyTarget);
  openInterfaceList(false).then(async () => {
    if (initialParams.get('draft')) await openInterfaceDetail(`/mypage/interfaces/manage/drafts/${initialParams.get('draft')}/`);
    else if (initialParams.get('interface')) await openInterfaceDetail(`/mypage/interfaces/manage/${initialParams.get('interface')}/`);
  });
} else if (myPage.dataset.initialSection === 'basic') openBasic(false);
else updateHeaderNavigation();
