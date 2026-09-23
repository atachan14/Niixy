const accountPage = document.querySelector('.account-page');
const accountWorkspace = document.querySelector('.account-workspace');
const threadWorkspace = document.querySelector('.account-thread-workspace');
const accountId = accountPage.dataset.accountId;
const threadPaneStorageKey = `niixy:account:${accountId}:thread-pane`;
const threadDetailStorageKey = `niixy:account:${accountId}:thread-detail`;
const threadPaneContainer = document.querySelector('[data-thread-pane-container]');
const threadDetailContainer = document.querySelector('[data-thread-detail-container]');
const threadPaneUrl = threadWorkspace.dataset.threadPaneUrl;
const threadDetailUrlTemplate = threadWorkspace.dataset.threadDetailUrlTemplate;
let loadedThreadPaneQuery = null;
let isApplyingHistory = false;
const detailTitle = document.getElementById('account-thread-detail-title');
const detailEmpty = document.getElementById('account-thread-detail-empty');
const accountContext = document.getElementById('account-page-context');
const accountIdentity = document.getElementById('account-page-identity');

function updateAccountContext() {
  const isThreadPaneOpen = accountWorkspace.classList.contains('is-thread-pane-open');
  accountContext.hidden = !isThreadPaneOpen;
  accountContext.textContent = ' > Thread';
  accountIdentity.disabled = !isThreadPaneOpen;
}

function renderPaneError(container) {
  container.innerHTML = '<p class="empty">読み込みに失敗しました。</p>';
}

function detailUrl(threadId) {
  return threadDetailUrlTemplate.replace('/0/', `/${threadId}/`);
}

function paneQueryFromParams(params) {
  const page = params.get('created_page');
  return page ? `?created_page=${encodeURIComponent(page)}` : '';
}

function updateUrl(params, replace = false) {
  if (isApplyingHistory) return;
  const url = new URL(window.location.href);
  url.search = params.toString();
  window.history[replace ? 'replaceState' : 'pushState']({}, '', url);
}

function threadParams({threadId = null, query = ''} = {}) {
  const params = new URLSearchParams(query);
  params.set('pane', 'thread');
  if (threadId) params.set('thread', threadId);
  return params;
}

async function loadThreadPane(query = '') {
  if (loadedThreadPaneQuery === query) return true;
  threadPaneContainer.innerHTML = '<p class="account-pane-loading">読み込み中...</p>';
  try {
    const response = await fetch(`${threadPaneUrl}${query}`, {headers: {'X-Requested-With': 'fetch'}});
    if (!response.ok) throw new Error('Thread pane request failed');
    threadPaneContainer.innerHTML = await response.text();
    loadedThreadPaneQuery = query;
    return true;
  } catch {
    renderPaneError(threadPaneContainer);
    return false;
  }
}

function openThreadPane(shouldPersist = true, query = '', shouldUpdateUrl = true) {
  accountWorkspace.classList.add('is-thread-pane-open');
  if (shouldPersist) sessionStorage.setItem(threadPaneStorageKey, 'true');
  updateAccountContext();
  if (shouldUpdateUrl) updateUrl(threadParams({query}));
  loadThreadPane(query);
}

function closeDetail(shouldUpdateUrl = true) {
  threadWorkspace.classList.remove('is-detail-open');
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  detailEmpty.hidden = false;
  detailEmpty.textContent = 'Threadを選択してください';
  detailTitle.textContent = '';
  sessionStorage.removeItem(threadDetailStorageKey);
  if (shouldUpdateUrl && accountWorkspace.classList.contains('is-thread-pane-open')) {
    updateUrl(threadParams({query: paneQueryFromParams(new URLSearchParams(window.location.search))}));
  }
}

function closeThreadPane() {
  closeDetail(false);
  accountWorkspace.classList.remove('is-thread-pane-open');
  sessionStorage.removeItem(threadPaneStorageKey);
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
  document.querySelectorAll('.summary-item').forEach((summary) => {
    const selected = summary === item;
    summary.classList.toggle('is-open', selected);
    setPreview(summary.querySelector('.summary-item-preview'), selected);
  });
}

async function openDetail(threadId, shouldPersist = true, shouldUpdateUrl = true) {
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
  document.querySelector('.account-thread-detail-pane').scrollTo({top: 0});
  if (shouldPersist) sessionStorage.setItem(threadDetailStorageKey, threadId);
  if (shouldUpdateUrl) {
    updateUrl(threadParams({threadId, query: paneQueryFromParams(new URLSearchParams(window.location.search))}));
  }
  return true;
}

document.querySelectorAll('[data-open-account-threads]').forEach((button) => button.addEventListener('click', () => openThreadPane()));
accountIdentity.addEventListener('click', closeThreadPane);
document.getElementById('close-account-thread-detail').addEventListener('click', closeDetail);

threadPaneContainer.addEventListener('click', (event) => {
  const pagination = event.target.closest('[data-thread-pane-pagination]');
  if (pagination) {
    event.preventDefault();
    const query = new URL(pagination.href).search;
    closeDetail(false);
    updateUrl(threadParams({query}));
    loadThreadPane(query);
    return;
  }
  const header = event.target.closest('.summary-item-header');
  if (header) selectSummary(header.closest('.summary-item'));
  const detailTrigger = event.target.closest('[data-thread-detail]');
  if (detailTrigger) openDetail(detailTrigger.dataset.threadDetail);

  const tab = event.target.closest('[data-thread-tab]');
  if (!tab) return;
  threadPaneContainer.querySelectorAll('[data-thread-tab]').forEach((item) => {
    const active = item === tab;
    item.classList.toggle('is-active', active);
    item.setAttribute('aria-selected', String(active));
  });
  threadPaneContainer.querySelectorAll('.account-thread-column').forEach((column) => {
    column.classList.toggle('is-tab-active', column.dataset.threadColumn === tab.dataset.threadTab);
  });
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
      sessionStorage.setItem(threadPaneStorageKey, 'true');
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
  const query = paneQueryFromParams(params);
  isApplyingHistory = true;
  if (params.get('pane') === 'thread') {
    accountWorkspace.classList.add('is-thread-pane-open');
    sessionStorage.setItem(threadPaneStorageKey, 'true');
    updateAccountContext();
    loadThreadPane(query);
    const threadId = params.get('thread');
    if (threadId) openDetail(threadId, false, false);
    else closeDetail(false);
  } else {
    closeDetail(false);
    accountWorkspace.classList.remove('is-thread-pane-open');
    sessionStorage.removeItem(threadPaneStorageKey);
    updateAccountContext();
  }
  isApplyingHistory = false;
}

window.addEventListener('popstate', applyStateFromUrl);

if (sessionStorage.getItem(threadPaneStorageKey)) {
  const params = new URLSearchParams(window.location.search);
  const query = paneQueryFromParams(params);
  const restoredDetailId = params.get('thread') || sessionStorage.getItem(threadDetailStorageKey);
  openThreadPane(false, query, params.get('pane') !== 'thread');
  if (restoredDetailId) openDetail(restoredDetailId, false, params.get('thread') !== restoredDetailId).then((opened) => {
    if (!opened) sessionStorage.removeItem(threadDetailStorageKey);
  });
} else if (new URLSearchParams(window.location.search).get('pane') === 'thread') {
  applyStateFromUrl();
} else {
  updateAccountContext();
}

document.documentElement.classList.remove('has-restored-account-thread-pane');
