const accountPage = document.querySelector('.account-page');
const accountWorkspace = document.querySelector('.account-workspace');
const threadWorkspace = document.querySelector('.account-thread-workspace');
const accountId = accountPage.dataset.accountId;
const modulePaneUrl = accountPage.dataset.modulePaneUrl;
const moduleFieldDetailTemplate = accountPage.dataset.moduleFieldDetailTemplate;
const moduleInterfaceDetailTemplate = accountPage.dataset.moduleInterfaceDetailTemplate;
sessionStorage.removeItem(`niixy:account:${accountId}:thread-pane`);
sessionStorage.removeItem(`niixy:account:${accountId}:thread-detail`);
const paneContainer = document.querySelector('[data-thread-pane-container]');
const threadDetailContainer = document.querySelector('[data-thread-detail-container]');
const paneUrls = {thread: threadWorkspace.dataset.threadPaneUrl, response: threadWorkspace.dataset.responsePaneUrl};
const threadDetailUrlTemplate = threadWorkspace.dataset.threadDetailUrlTemplate;
const paneCache = new Map();
let requestedPaneKey = null;
let activePane = 'thread';
let highlightTimer = null;
let isApplyingHistory = false;
let detailRequestId = 0;
const detailTitle = document.getElementById('account-thread-detail-title');
const detailEmpty = document.getElementById('account-thread-detail-empty');
const accountIdentity = document.getElementById('account-page-identity');
const accountListTitle = document.getElementById('account-list-title');
const profileStack = NiixyUI.createWorkspace(accountWorkspace, {
  overview: {root: true},
  list: {target: '.account-thread-pane'},
  detail: {target: '.account-thread-detail-pane'},
  'module-list': {target: '.profile-module-list-pane'},
  'module-detail': {target: '.profile-module-management .ui-detail-pane'},
}, {track: document.querySelector('.account-track')});
const profileFeatures = NiixyUI.createFeatureWorkspaceController(document.querySelector('.account-track'));
let activeModuleState = {type: 'element', subtype: 'field', collection: 'self'};

function updateAccountNavigation() {
  const isPaneOpen = !profileStack.is('overview');
  const label = activePane === 'response' ? 'Response' : activePane === 'module' ? 'Module' : 'Thread';
  accountListTitle.textContent = `${label}一覧`;
  accountIdentity.disabled = !isPaneOpen;
}

function renderPaneError(container) {
  container.innerHTML = '<p class="empty">読み込みに失敗しました。</p>';
}

function detailUrl(threadId) {
  return threadDetailUrlTemplate.replace('/0/', `/${threadId}/`);
}

function paneQueryFromParams(params, pane = activePane) {
  const key = pane === 'response' ? 'response_page' : 'created_page';
  const page = params.get(key);
  return page ? `?${key}=${encodeURIComponent(page)}` : '';
}

function updateUrl(params, replace = false) {
  if (isApplyingHistory) return;
  const url = new URL(window.location.href);
  url.search = params.toString();
  window.history[replace ? 'replaceState' : 'pushState']({}, '', url);
}

function paneParams({pane = activePane, threadId = null, postNumber = null, query = ''} = {}) {
  const params = new URLSearchParams(query);
  params.set('pane', pane);
  if (threadId) params.set('thread', threadId);
  if (postNumber) params.set('post', postNumber);
  return params;
}

async function loadPane(pane, query = '') {
  const cacheKey = `${pane}:${query}`;
  requestedPaneKey = cacheKey;
  if (paneCache.has(cacheKey)) {
    paneContainer.innerHTML = paneCache.get(cacheKey);
    NiixyUI.bindTabs(paneContainer);
    return true;
  }
  paneContainer.innerHTML = '<p class="account-pane-loading">読み込み中...</p>';
  try {
    const response = await fetch(`${paneUrls[pane]}${query}`, {headers: {'X-Requested-With': 'fetch'}});
    if (!response.ok) throw new Error('Account pane request failed');
    const html = await response.text();
    paneCache.set(cacheKey, html);
    if (requestedPaneKey === cacheKey) {
      paneContainer.innerHTML = html;
      NiixyUI.bindTabs(paneContainer);
    }
    return true;
  } catch {
    if (requestedPaneKey === cacheKey) renderPaneError(paneContainer);
    return false;
  }
}

function openPane(pane, query = '', shouldUpdateUrl = true) {
  removeProfileModule();
  resetThreadDetail();
  profileFeatures.activate('conversation');
  activePane = pane;
  profileStack.set('list');
  updateAccountNavigation();
  if (shouldUpdateUrl) updateUrl(paneParams({pane, query}));
  loadPane(pane, query);
}

function moduleStateFromParams(params = new URLSearchParams(window.location.search)) {
  const requestedType = params.get('type') || 'element';
  const type = requestedType === 'field' ? 'element' : requestedType;
  return {
    type,
    subtype: requestedType === 'field'
      ? 'field'
      : params.get('subtype') || ({element: 'field', interface: 'thread', layout: 'thread_post'}[type]),
    collection: params.get('collection') || 'self',
  };
}

function moduleParams(state = activeModuleState, detail = {}) {
  const params = new URLSearchParams({
    pane: 'module',
    type: state.type,
    subtype: state.subtype,
  });
  if (state.collection !== 'self') params.set('collection', state.collection);
  if (detail.field) params.set('field', detail.field);
  if (detail.interface) params.set('interface', detail.interface);
  return params;
}

function replaceTemplateId(template, id) {
  return template.replace('/0/', `/${id}/`);
}

function removeProfileModule() {
  profileFeatures.remove('module');
}

async function openProfileModule(initialState = moduleStateFromParams(), shouldUpdateUrl = true) {
  removeProfileModule();
  resetThreadDetail();
  activePane = 'module';
  activeModuleState = initialState;
  const management = document.createElement('section');
  management.className = 'module-management profile-module-management';
  const track = document.createElement('div');
  track.className = 'module-track';
  const loading = NiixyUI.createStatusPane({
    className: 'module-list-pane profile-module-list-pane',
    attributes: {accountPane: 'module-list'},
  });
  track.append(loading);
  management.append(track);
  profileFeatures.register('module', management);
  profileStack.set('module-list');
  updateAccountNavigation();
  if (shouldUpdateUrl) updateUrl(moduleParams(initialState));
  let list;
  try {
    list = await NiixyUI.fetchFragment(modulePaneUrl);
  } catch {
    NiixyUI.showPaneError(loading);
    return false;
  }
  loading.replaceWith(list);
  bindProfileModuleList(list, initialState);
  return true;
}

function bindProfileModuleList(list, initialState) {
  NiixyUI.bindModuleFilters(list, initialState, {
    onChange: (state) => {
      activeModuleState = state;
      updateUrl(moduleParams(state), true);
    },
  });
  list.querySelector('[data-close-module-list]')?.addEventListener('click', closePane);
  list.addEventListener('click', (event) => {
    const item = event.target.closest('[data-detail-url]');
    if (!item) return;
    event.preventDefault();
    const panelParts = item.closest('[data-module-panel]').dataset.modulePanel.split(':');
    const type = panelParts[0];
    if (type === 'element' && panelParts[1] === 'field') {
      openProfileModuleDetail('field', item.dataset.detailUrl, new URL(item.href).searchParams.get('field'));
    } else if (type === 'interface') {
      openProfileModuleDetail('interface', item.dataset.detailUrl, new URL(item.href).searchParams.get('interface'));
    }
  });
}

async function openProfileModuleDetail(type, url, id, shouldUpdateUrl = true) {
  const management = document.querySelector('.profile-module-management');
  if (!management) return false;
  management.querySelector('.profile-module-detail-pane')?.remove();
  const loading = NiixyUI.createStatusPane({
    tagName: 'aside',
    className: `ui-detail-pane ${type === 'field' ? 'field-detail-pane' : 'interface-detail-pane'} profile-module-detail-pane`,
    attributes: {accountPane: 'module-detail'},
  });
  management.querySelector('.module-track').append(loading);
  profileStack.set('module-detail');
  if (shouldUpdateUrl) updateUrl(moduleParams(activeModuleState, {[type]: id}));
  let detail;
  try {
    detail = await NiixyUI.fetchFragment(url);
  } catch {
    NiixyUI.showPaneError(loading);
    return false;
  }
  detail.classList.add('profile-module-detail-pane');
  loading.replaceWith(detail);
  profileStack.align();
  const closeSelector = type === 'field' ? '[data-close-field-detail]' : '[data-close-interface-detail]';
  detail.querySelector(closeSelector)?.addEventListener('click', () => {
    detail.remove();
    profileStack.set('module-list');
    updateUrl(moduleParams());
  });
  return true;
}

function clearTargetHighlight() {
  window.clearTimeout(highlightTimer);
  document.querySelectorAll('.is-response-target').forEach((post) => post.classList.remove('is-response-target'));
}

function resetThreadDetail() {
  detailRequestId += 1;
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  clearTargetHighlight();
  detailEmpty.hidden = false;
  detailEmpty.textContent = 'Threadを選択してください';
  detailTitle.textContent = '';
}

function closeDetail(shouldUpdateUrl = true) {
  resetThreadDetail();
  profileStack.set('list');
  if (shouldUpdateUrl && !profileStack.is('overview')) {
    updateUrl(paneParams({query: paneQueryFromParams(new URLSearchParams(window.location.search))}));
  }
}

function closePane() {
  resetThreadDetail();
  removeProfileModule();
  profileFeatures.clear();
  profileStack.set('overview');
  updateAccountNavigation();
  updateUrl(new URLSearchParams());
}

async function openDetail(threadId, postNumber = null, shouldUpdateUrl = true) {
  const requestId = ++detailRequestId;
  let detail = document.querySelector(`[data-thread-detail-pane="${threadId}"]`);
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  clearTargetHighlight();
  detailTitle.textContent = '';
  detailEmpty.hidden = false;
  detailEmpty.textContent = '読み込み中...';
  profileStack.set('detail');
  document.querySelector('.account-thread-detail-pane').scrollTo({top: 0});
  if (!detail) {
    try {
      const response = await fetch(detailUrl(threadId), {headers: {'X-Requested-With': 'fetch'}});
      if (!response.ok) throw new Error('Thread detail request failed');
      const html = await response.text();
      if (requestId !== detailRequestId) return false;
      threadDetailContainer.insertAdjacentHTML('beforeend', html);
      detail = document.querySelector(`[data-thread-detail-pane="${threadId}"]`);
    } catch {
      if (requestId !== detailRequestId) return false;
      detailEmpty.textContent = '読み込みに失敗しました。';
      return false;
    }
  }
  if (!detail || requestId !== detailRequestId) return false;
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = pane !== detail; });
  detailEmpty.hidden = true;
  detailTitle.textContent = `${detail.dataset.threadTitle} (${detail.dataset.threadPostCount})`;
  const target = postNumber ? detail.querySelector(`[data-thread-post-number="${postNumber}"]`) : null;
  if (target) {
    target.classList.add('is-response-target');
    target.scrollIntoView({behavior: 'smooth', block: 'center'});
    highlightTimer = window.setTimeout(() => target.classList.remove('is-response-target'), 2200);
  } else {
    document.querySelector('.account-thread-detail-pane').scrollTo({top: 0});
  }
  if (shouldUpdateUrl) updateUrl(paneParams({threadId, postNumber, query: paneQueryFromParams(new URLSearchParams(window.location.search))}));
  return true;
}

document.querySelectorAll('[data-open-account-threads]').forEach((button) => button.addEventListener('click', () => openPane('thread')));
document.querySelectorAll('[data-open-account-responses]').forEach((button) => button.addEventListener('click', () => openPane('response')));
document.querySelectorAll('[data-open-account-modules]').forEach((button) => button.addEventListener('click', () => openProfileModule()));
accountIdentity.addEventListener('click', closePane);
document.getElementById('close-account-list').addEventListener('click', closePane);
document.getElementById('close-account-thread-detail').addEventListener('click', () => closeDetail());

paneContainer.addEventListener('click', (event) => {
  const pagination = event.target.closest('[data-pane-pagination]');
  if (pagination) {
    event.preventDefault();
    const query = new URL(pagination.href).search;
    closeDetail(false);
    updateUrl(paneParams({query}));
    loadPane(activePane, query);
    return;
  }
  const detailTrigger = event.target.closest('[data-thread-detail]');
  if (detailTrigger) openDetail(detailTrigger.dataset.threadDetail);
  const responseHeader = event.target.closest('[data-response-thread]');
  if (responseHeader) openDetail(responseHeader.dataset.responseThread, responseHeader.dataset.responsePost);
});

threadDetailContainer.addEventListener('submit', async (event) => {
  const form = event.target.closest('.account-thread-reply-form');
  if (!form) return;
  event.preventDefault();
  const button = form.querySelector('button[type="submit"]');
  const error = form.querySelector('.reply-form-error');
  if (button.disabled) return;
  button.disabled = true;
  button.textContent = '送信中...';
  error.hidden = true;
  const data = new FormData(form);
  form.dataset.submissionId ||= crypto.randomUUID();
  data.append('submission_id', form.dataset.submissionId);
  let sent = false;
  try {
    const response = await fetch(form.action, {method: 'POST', body: data});
    const result = await response.json();
    if (response.ok) {
      sent = true;
      location.reload();
      return;
    }
    error.textContent = result.error || Object.values(result.errors || {}).flat().join(' ') || '送信に失敗しました。';
    error.hidden = false;
  } catch {
    error.textContent = '通信に失敗しました。もう一度お試しください。';
    error.hidden = false;
  } finally {
    if (!sent) {
      button.disabled = false;
      button.textContent = '送信';
    }
  }
});

function applyStateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const pane = params.get('pane');
  isApplyingHistory = true;
  if (pane === 'thread' || pane === 'response') {
    removeProfileModule();
    resetThreadDetail();
    profileFeatures.activate('conversation');
    activePane = pane;
    profileStack.set('list');
    updateAccountNavigation();
    loadPane(pane, paneQueryFromParams(params, pane));
    const threadId = params.get('thread');
    if (threadId) openDetail(threadId, params.get('post'), false);
    else closeDetail(false);
  } else if (pane === 'module') {
    const state = moduleStateFromParams(params);
    openProfileModule(state, false).then(() => {
      const fieldId = params.get('field');
      const interfaceId = params.get('interface');
      if (fieldId) openProfileModuleDetail('field', replaceTemplateId(moduleFieldDetailTemplate, fieldId), fieldId, false);
      else if (interfaceId) openProfileModuleDetail('interface', replaceTemplateId(moduleInterfaceDetailTemplate, interfaceId), interfaceId, false);
    });
  } else {
    removeProfileModule();
    resetThreadDetail();
    profileFeatures.clear();
    profileStack.set('overview');
    updateAccountNavigation();
  }
  isApplyingHistory = false;
}

window.addEventListener('popstate', applyStateFromUrl);

const initialParams = new URLSearchParams(window.location.search);
if (['thread', 'response'].includes(initialParams.get('pane'))) {
  const pane = initialParams.get('pane');
  const query = paneQueryFromParams(initialParams, pane);
  openPane(pane, query, false);
  const threadId = initialParams.get('thread');
  if (threadId) openDetail(threadId, initialParams.get('post'), false);
} else if (initialParams.get('pane') === 'module') {
  const state = moduleStateFromParams(initialParams);
  openProfileModule(state, false).then(() => {
    const fieldId = initialParams.get('field');
    const interfaceId = initialParams.get('interface');
    if (fieldId) openProfileModuleDetail('field', replaceTemplateId(moduleFieldDetailTemplate, fieldId), fieldId, false);
    else if (interfaceId) openProfileModuleDetail('interface', replaceTemplateId(moduleInterfaceDetailTemplate, interfaceId), interfaceId, false);
  });
} else {
  updateAccountNavigation();
}

document.documentElement.classList.remove('has-restored-account-thread-pane');
