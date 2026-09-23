const accountPage = document.querySelector('.account-page');
const accountWorkspace = document.querySelector('.account-workspace');
const threadWorkspace = document.querySelector('.account-thread-workspace');
const accountId = accountPage.dataset.accountId;
const paneStorageKey = `niixy:account:${accountId}:thread-pane`;
const threadDetailStorageKey = `niixy:account:${accountId}:thread-detail`;
const paneContainer = document.querySelector('[data-thread-pane-container]');
const threadDetailContainer = document.querySelector('[data-thread-detail-container]');
const paneUrls = {thread: threadWorkspace.dataset.threadPaneUrl, response: threadWorkspace.dataset.responsePaneUrl};
const threadDetailUrlTemplate = threadWorkspace.dataset.threadDetailUrlTemplate;
const paneCache = new Map();
let requestedPaneKey = null;
let activePane = 'thread';
let highlightTimer = null;
let isApplyingHistory = false;
const detailTitle = document.getElementById('account-thread-detail-title');
const detailEmpty = document.getElementById('account-thread-detail-empty');
const accountContext = document.getElementById('account-page-context');
const accountIdentity = document.getElementById('account-page-identity');

function updateAccountContext() {
  const isPaneOpen = accountWorkspace.classList.contains('is-thread-pane-open');
  accountContext.hidden = !isPaneOpen;
  accountContext.textContent = ` > ${activePane === 'response' ? 'Response' : 'Thread'}`;
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
    return true;
  }
  paneContainer.innerHTML = '<p class="account-pane-loading">読み込み中...</p>';
  try {
    const response = await fetch(`${paneUrls[pane]}${query}`, {headers: {'X-Requested-With': 'fetch'}});
    if (!response.ok) throw new Error('Account pane request failed');
    const html = await response.text();
    paneCache.set(cacheKey, html);
    if (requestedPaneKey === cacheKey) paneContainer.innerHTML = html;
    return true;
  } catch {
    if (requestedPaneKey === cacheKey) renderPaneError(paneContainer);
    return false;
  }
}

function openPane(pane, shouldPersist = true, query = '', shouldUpdateUrl = true) {
  activePane = pane;
  accountWorkspace.classList.add('is-thread-pane-open');
  if (shouldPersist) sessionStorage.setItem(paneStorageKey, pane);
  updateAccountContext();
  if (shouldUpdateUrl) updateUrl(paneParams({pane, query}));
  loadPane(pane, query);
}

function clearTargetHighlight() {
  window.clearTimeout(highlightTimer);
  document.querySelectorAll('.is-response-target').forEach((post) => post.classList.remove('is-response-target'));
}

function closeDetail(shouldUpdateUrl = true) {
  threadWorkspace.classList.remove('is-detail-open');
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  clearTargetHighlight();
  detailEmpty.hidden = false;
  detailEmpty.textContent = 'Threadを選択してください';
  detailTitle.textContent = '';
  sessionStorage.removeItem(threadDetailStorageKey);
  if (shouldUpdateUrl && accountWorkspace.classList.contains('is-thread-pane-open')) {
    updateUrl(paneParams({query: paneQueryFromParams(new URLSearchParams(window.location.search))}));
  }
}

function closePane() {
  closeDetail(false);
  accountWorkspace.classList.remove('is-thread-pane-open');
  sessionStorage.removeItem(paneStorageKey);
  updateAccountContext();
  updateUrl(new URLSearchParams());
}

function setPreview(preview, isOpen) {
  if (isOpen) {
    preview.hidden = false;
    requestAnimationFrame(() => preview.classList.add('is-open'));
    return;
  }
  preview.classList.remove('is-open');
  const hideWhenClosed = (event) => {
    if (event.target !== preview || event.propertyName !== 'grid-template-rows') return;
    preview.removeEventListener('transitionend', hideWhenClosed);
    if (!preview.classList.contains('is-open')) preview.hidden = true;
  };
  preview.addEventListener('transitionend', hideWhenClosed);
}

function selectSummary(item) {
  paneContainer.querySelectorAll('.summary-item').forEach((summary) => {
    const selected = summary === item;
    summary.classList.toggle('is-open', selected);
    setPreview(summary.querySelector('.summary-item-preview'), selected);
  });
}

async function openDetail(threadId, postNumber = null, shouldPersist = true, shouldUpdateUrl = true) {
  let detail = document.querySelector(`[data-thread-detail-pane="${threadId}"]`);
  if (!detail) {
    detailEmpty.hidden = false;
    detailEmpty.textContent = '読み込み中...';
    try {
      const response = await fetch(detailUrl(threadId), {headers: {'X-Requested-With': 'fetch'}});
      if (!response.ok) throw new Error('Thread detail request failed');
      threadDetailContainer.insertAdjacentHTML('beforeend', await response.text());
      detail = document.querySelector(`[data-thread-detail-pane="${threadId}"]`);
    } catch {
      detailEmpty.textContent = '読み込みに失敗しました。';
      return false;
    }
  }
  if (!detail) return false;
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = pane !== detail; });
  detailEmpty.hidden = true;
  detailTitle.textContent = `${detail.dataset.threadTitle} (${detail.dataset.threadPostCount})`;
  threadWorkspace.classList.add('is-detail-open');
  clearTargetHighlight();
  const target = postNumber ? detail.querySelector(`[data-thread-post-number="${postNumber}"]`) : null;
  if (target) {
    target.classList.add('is-response-target');
    target.scrollIntoView({behavior: 'smooth', block: 'center'});
    highlightTimer = window.setTimeout(() => target.classList.remove('is-response-target'), 2200);
  } else {
    document.querySelector('.account-thread-detail-pane').scrollTo({top: 0});
  }
  if (shouldPersist) sessionStorage.setItem(threadDetailStorageKey, JSON.stringify({threadId, postNumber}));
  if (shouldUpdateUrl) updateUrl(paneParams({threadId, postNumber, query: paneQueryFromParams(new URLSearchParams(window.location.search))}));
  return true;
}

document.querySelectorAll('[data-open-account-threads]').forEach((button) => button.addEventListener('click', () => openPane('thread')));
document.querySelectorAll('[data-open-account-responses]').forEach((button) => button.addEventListener('click', () => openPane('response')));
accountIdentity.addEventListener('click', closePane);
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
  const header = event.target.closest('.summary-item-header');
  if (header) selectSummary(header.closest('.summary-item'));
  const detailTrigger = event.target.closest('[data-thread-detail]');
  if (detailTrigger) openDetail(detailTrigger.dataset.threadDetail);
  const responseHeader = event.target.closest('[data-response-thread]');
  if (responseHeader) openDetail(responseHeader.dataset.responseThread, responseHeader.dataset.responsePost);
  const tab = event.target.closest('[data-thread-tab]');
  if (!tab) return;
  paneContainer.querySelectorAll('[data-thread-tab]').forEach((item) => {
    const selected = item === tab;
    item.classList.toggle('is-active', selected);
    item.setAttribute('aria-selected', String(selected));
  });
  paneContainer.querySelectorAll('.account-thread-column').forEach((column) => column.classList.toggle('is-tab-active', column.dataset.threadColumn === tab.dataset.threadTab));
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
      sessionStorage.setItem(paneStorageKey, activePane);
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
    activePane = pane;
    accountWorkspace.classList.add('is-thread-pane-open');
    sessionStorage.setItem(paneStorageKey, pane);
    updateAccountContext();
    loadPane(pane, paneQueryFromParams(params, pane));
    const threadId = params.get('thread');
    if (threadId) openDetail(threadId, params.get('post'), false, false);
    else closeDetail(false);
  } else {
    closeDetail(false);
    accountWorkspace.classList.remove('is-thread-pane-open');
    sessionStorage.removeItem(paneStorageKey);
    updateAccountContext();
  }
  isApplyingHistory = false;
}

window.addEventListener('popstate', applyStateFromUrl);

const initialParams = new URLSearchParams(window.location.search);
const storedPane = sessionStorage.getItem(paneStorageKey);
if (storedPane || ['thread', 'response'].includes(initialParams.get('pane'))) {
  const pane = ['thread', 'response'].includes(initialParams.get('pane')) ? initialParams.get('pane') : (storedPane === 'response' ? 'response' : 'thread');
  const query = paneQueryFromParams(initialParams, pane);
  openPane(pane, false, query, initialParams.get('pane') !== pane);
  let restoredDetail = null;
  try { restoredDetail = JSON.parse(sessionStorage.getItem(threadDetailStorageKey)); } catch { restoredDetail = {threadId: sessionStorage.getItem(threadDetailStorageKey)}; }
  if (restoredDetail && typeof restoredDetail !== 'object') restoredDetail = {threadId: restoredDetail};
  const threadId = initialParams.get('thread') || restoredDetail?.threadId;
  const postNumber = initialParams.get('post') || restoredDetail?.postNumber;
  if (threadId) openDetail(threadId, postNumber, false, initialParams.get('thread') !== String(threadId));
} else {
  updateAccountContext();
}

document.documentElement.classList.remove('has-restored-account-thread-pane');
