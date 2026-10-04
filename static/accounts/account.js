const accountPage = document.querySelector('.account-page');
const accountWorkspace = document.querySelector('.account-workspace');
const threadWorkspace = document.querySelector('.account-thread-workspace');
const accountId = accountPage.dataset.accountId;
const modulePaneUrl = accountPage.dataset.modulePaneUrl;
const moduleFieldDetailTemplate = accountPage.dataset.moduleFieldDetailTemplate;
const moduleInterfaceDetailTemplate = accountPage.dataset.moduleInterfaceDetailTemplate;
const roomPaneUrl = accountPage.dataset.roomPaneUrl;
const roomDetailTemplate = accountPage.dataset.roomDetailTemplate;
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
const accountRoomListContainer = document.querySelector('[data-account-room-list-container]');
const accountRoomDetailContainer = document.querySelector('[data-account-room-detail-container]');
const accountRoomDetailTitle = document.getElementById('account-room-detail-title');
const roomPaneCache = new Map();
let roomRequestId = 0;
let activeRoomQuery = '';
const profileStack = NiixyUI.createWorkspace(accountWorkspace, {
  overview: {root: true},
  list: {target: '.account-thread-pane', width: 'fixed'},
  detail: {target: '.account-thread-detail-pane', width: 'remaining'},
  'room-list': {target: '.account-room-list-pane', width: 'fixed'},
  'room-detail': {target: '.account-room-detail-pane', width: 'full'},
  'account-if-list': {target: '#account-if-list-pane', width: 'fixed'},
  'account-if-detail': {target: '#account-if-detail-pane', width: 'remaining'},
  'people-list': {target: '#people-list-pane', width: 'fixed'},
  'module-list': {target: '.profile-module-list-pane', width: 'fixed'},
  'module-detail': {target: '.profile-module-management .ui-detail-pane', width: 'remaining'},
}, {track: document.querySelector('.account-track')});
const profileFeatures = NiixyUI.createFeatureWorkspaceController(document.querySelector('.account-track'));
let activeModuleState = {type: 'element', subtype: 'field', collection: 'self'};

function updateAccountNavigation() {
  const isPaneOpen = !profileStack.is('overview');
  const label = {'account-if': 'AccountIF', people: 'People', response: 'Response', room: 'Room', module: 'Module'}[activePane] || 'Thread';
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
  resetAccountRoomDetail();
  resetThreadDetail();
  profileFeatures.activate('conversation');
  activePane = pane;
  profileStack.set('list');
  updateAccountNavigation();
  if (shouldUpdateUrl) updateUrl(paneParams({pane, query}));
  loadPane(pane, query);
}

function openStaticFeature(pane, stage, shouldUpdateUrl = true) {
  removeProfileModule();
  resetThreadDetail();
  resetAccountRoomDetail();
  activePane = pane;
  profileFeatures.activate(pane);
  profileStack.set(stage);
  updateAccountNavigation();
  if (shouldUpdateUrl) updateUrl(new URLSearchParams({pane}));
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
  resetAccountRoomDetail();
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

function accountRoomParams(query = activeRoomQuery, roomId = null) {
  const params = new URLSearchParams(query);
  params.set('pane', 'room');
  if (roomId) params.set('room', roomId);
  return params;
}

function resetAccountRoomDetail() {
  roomRequestId += 1;
  accountRoomDetailTitle.textContent = '';
  accountRoomDetailContainer.innerHTML = '<p class="account-thread-detail-empty">Roomを選択してください。</p>';
}

function bindAccountRoomList(query = '') {
  NiixyUI.bindTabs(accountRoomListContainer);
  if (new URLSearchParams(query).has('member_page')) {
    accountRoomListContainer.querySelector('[data-ui-tab="member"]')?.click();
  }
}

async function loadAccountRoomPane(query = '') {
  const cacheKey = query || 'default';
  activeRoomQuery = query;
  if (roomPaneCache.has(cacheKey)) {
    accountRoomListContainer.innerHTML = roomPaneCache.get(cacheKey);
    bindAccountRoomList(query);
    return true;
  }
  accountRoomListContainer.innerHTML = '<p class="account-pane-loading">読み込み中...</p>';
  try {
    const response = await fetch(`${roomPaneUrl}${query}`, {headers: {'X-Requested-With': 'fetch'}});
    if (!response.ok) throw new Error('Room pane request failed');
    const html = await response.text();
    roomPaneCache.set(cacheKey, html);
    if (activeRoomQuery === query) {
      accountRoomListContainer.innerHTML = html;
      bindAccountRoomList(query);
    }
    return true;
  } catch {
    if (activeRoomQuery === query) renderPaneError(accountRoomListContainer);
    return false;
  }
}

async function openAccountRooms(query = '', shouldUpdateUrl = true) {
  removeProfileModule();
  resetThreadDetail();
  resetAccountRoomDetail();
  activePane = 'room';
  profileFeatures.activate('room');
  profileStack.set('room-list');
  updateAccountNavigation();
  if (shouldUpdateUrl) updateUrl(accountRoomParams(query));
  return loadAccountRoomPane(query);
}

function roomDetailUrl(roomId) {
  return roomDetailTemplate.replace('/0/', `/${roomId}/`);
}

function roomPageSectionUrl(fragment, section) {
  const url = new URL(fragment.dataset.roomPageUrl, location.origin);
  url.searchParams.set(section, '1');
  return url;
}

function bindAccountRoomDetail(fragment, roomId) {
  fragment.querySelector('[data-open-room-members]')?.addEventListener('click', () => {
    location.assign(roomPageSectionUrl(fragment, 'members'));
  });
  fragment.querySelector('[data-open-room-boards]')?.addEventListener('click', () => {
    location.assign(roomPageSectionUrl(fragment, 'boards'));
  });
  fragment.addEventListener('submit', async (event) => {
    const form = event.target.closest('[data-room-action]');
    if (!form) return;
    event.preventDefault();
    const pending = NiixyUI.beginPendingAction(event.submitter || form.querySelector('[type="submit"]'));
    if (!pending) return;
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form)});
      if (!response.ok) throw new Error();
      roomPaneCache.clear();
      await loadAccountRoomPane(activeRoomQuery);
      await openAccountRoomDetail(roomId, false);
    } catch {
      pending.restore();
    }
  });
}

async function openAccountRoomDetail(roomId, shouldUpdateUrl = true) {
  const requestId = ++roomRequestId;
  accountRoomDetailTitle.textContent = '読み込み中...';
  accountRoomDetailContainer.innerHTML = '<p class="account-pane-loading">読み込み中...</p>';
  profileStack.set('room-detail');
  document.querySelector('.account-room-detail-pane').scrollTo({top: 0});
  if (shouldUpdateUrl) updateUrl(accountRoomParams(activeRoomQuery, roomId));
  try {
    const fragment = await NiixyUI.fetchFragment(roomDetailUrl(roomId));
    if (requestId !== roomRequestId) return false;
    accountRoomDetailTitle.textContent = fragment.dataset.roomTitle;
    accountRoomDetailContainer.replaceChildren(fragment);
    bindAccountRoomDetail(fragment, roomId);
    return true;
  } catch {
    if (requestId === roomRequestId) {
      accountRoomDetailTitle.textContent = '';
      renderPaneError(accountRoomDetailContainer);
    }
    return false;
  }
}

function closeAccountRoomDetail(shouldUpdateUrl = true) {
  resetAccountRoomDetail();
  profileStack.set('room-list');
  if (shouldUpdateUrl) updateUrl(accountRoomParams());
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
  resetAccountRoomDetail();
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
    const detailPane = document.querySelector('.account-thread-detail-pane');
    const paneRect = detailPane.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const centeredTop = detailPane.scrollTop
      + targetRect.top - paneRect.top
      - ((detailPane.clientHeight - targetRect.height) / 2);
    detailPane.scrollTo({top: Math.max(0, centeredTop), behavior: 'smooth'});
    highlightTimer = window.setTimeout(() => target.classList.remove('is-response-target'), 2200);
  } else {
    document.querySelector('.account-thread-detail-pane').scrollTo({top: 0});
  }
  if (shouldUpdateUrl) updateUrl(paneParams({threadId, postNumber, query: paneQueryFromParams(new URLSearchParams(window.location.search))}));
  return true;
}

document.querySelectorAll('[data-open-account-threads]').forEach((button) => button.addEventListener('click', () => openPane('thread')));
document.querySelectorAll('[data-open-account-responses]').forEach((button) => button.addEventListener('click', () => openPane('response')));
document.querySelectorAll('[data-open-account-rooms]').forEach((button) => button.addEventListener('click', () => openAccountRooms()));
document.querySelectorAll('[data-open-account-account-if]').forEach((button) => button.addEventListener('click', () => openStaticFeature('account-if', 'account-if-list')));
document.querySelectorAll('[data-open-account-people]').forEach((button) => button.addEventListener('click', () => openStaticFeature('people', 'people-list')));
document.querySelectorAll('[data-open-account-modules]').forEach((button) => button.addEventListener('click', () => openProfileModule()));
NiixyUI.bindTabs(document.querySelector('.account-people-list-pane'));
accountIdentity.addEventListener('click', closePane);
document.getElementById('close-account-list').addEventListener('click', closePane);
document.getElementById('close-account-thread-detail').addEventListener('click', () => closeDetail());
document.getElementById('close-account-room-list').addEventListener('click', closePane);
document.getElementById('close-account-room-detail').addEventListener('click', () => closeAccountRoomDetail());
document.getElementById('close-account-if-list').addEventListener('click', closePane);
document.getElementById('close-account-if-detail').addEventListener('click', () => {
  profileStack.set('account-if-list');
  updateUrl(new URLSearchParams({pane: 'account-if'}));
});
document.getElementById('close-people-list').addEventListener('click', closePane);

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

accountRoomListContainer.addEventListener('click', (event) => {
  const pagination = event.target.closest('[data-room-pagination]');
  if (pagination) {
    event.preventDefault();
    const query = new URL(pagination.href, location.origin).search;
    closeAccountRoomDetail(false);
    updateUrl(accountRoomParams(query));
    loadAccountRoomPane(query);
    return;
  }
  const room = event.target.closest('[data-account-room-detail]');
  if (!room) return;
  event.preventDefault();
  openAccountRoomDetail(room.dataset.accountRoomDetail);
});

threadDetailContainer.addEventListener('submit', async (event) => {
  const form = event.target.closest('.thread-reply-form');
  if (!form) return;
  event.preventDefault();
  const result = await NiixyUI.submitThreadReply(form, event.submitter);
  if (result) location.reload();
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
  } else if (pane === 'room') {
    const roomQuery = new URLSearchParams(params);
    roomQuery.delete('pane');
    roomQuery.delete('room');
    const query = roomQuery.toString() ? `?${roomQuery}` : '';
    openAccountRooms(query, false).then(() => {
      const roomId = params.get('room');
      if (roomId) openAccountRoomDetail(roomId, false);
    });
  } else if (pane === 'account-if') {
    openStaticFeature('account-if', 'account-if-list', false);
  } else if (pane === 'people') {
    openStaticFeature('people', 'people-list', false);
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
} else if (initialParams.get('pane') === 'room') {
  const roomQuery = new URLSearchParams(initialParams);
  roomQuery.delete('pane');
  roomQuery.delete('room');
  const query = roomQuery.toString() ? `?${roomQuery}` : '';
  openAccountRooms(query, false).then(() => {
    const roomId = initialParams.get('room');
    if (roomId) openAccountRoomDetail(roomId, false);
  });
} else if (initialParams.get('pane') === 'account-if') {
  openStaticFeature('account-if', 'account-if-list', false);
} else if (initialParams.get('pane') === 'people') {
  openStaticFeature('people', 'people-list', false);
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
