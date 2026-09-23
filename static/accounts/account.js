const accountPage = document.querySelector('.account-page');
const accountWorkspace = document.querySelector('.account-workspace');
const threadWorkspace = document.querySelector('.account-thread-workspace');
const accountId = accountPage.dataset.accountId;
const threadPaneStorageKey = `niixy:account:${accountId}:thread-pane`;
const threadDetailStorageKey = `niixy:account:${accountId}:thread-detail`;
const detailTitle = document.getElementById('account-thread-detail-title');
const detailEmpty = document.getElementById('account-thread-detail-empty');
const accountContext = document.getElementById('account-page-context');
const accountIdentity = document.getElementById('account-page-identity');

function updateAccountContext() {
  const mode = accountWorkspace.dataset.mode;
  accountContext.hidden = !mode;
  accountContext.textContent = mode ? ` > ${mode}` : '';
  accountIdentity.disabled = !mode;
}

function openThreadPane(shouldPersist = true) {
  accountWorkspace.dataset.mode = 'Thread';
  accountWorkspace.classList.remove('is-response-mode');
  accountWorkspace.classList.add('is-thread-pane-open');
  if (shouldPersist) sessionStorage.setItem(threadPaneStorageKey, 'true');
  updateAccountContext();
}

function openResponsePane() {
  accountWorkspace.dataset.mode = 'Response';
  accountWorkspace.classList.add('is-thread-pane-open', 'is-response-mode');
  updateAccountContext();
}

function closeDetail() {
  threadWorkspace.classList.remove('is-detail-open');
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  detailEmpty.hidden = false;
  detailTitle.textContent = '';
  sessionStorage.removeItem(threadDetailStorageKey);
}

function closeThreadPane() {
  closeDetail();
  accountWorkspace.classList.remove('is-thread-pane-open');
  delete accountWorkspace.dataset.mode;
  sessionStorage.removeItem(threadPaneStorageKey);
  updateAccountContext();
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

function openDetail(threadId, shouldPersist = true) {
  const detail = document.querySelector(`[data-thread-detail-pane="${threadId}"]`);
  if (!detail) return false;
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = pane !== detail; });
  detailEmpty.hidden = true;
  detailTitle.textContent = `${detail.dataset.threadTitle} (${detail.dataset.threadPostCount})`;
  threadWorkspace.classList.add('is-detail-open');
  document.querySelector('.account-thread-detail-pane').scrollTo({top: 0});
  if (shouldPersist) sessionStorage.setItem(threadDetailStorageKey, threadId);
  return true;
}

document.querySelectorAll('[data-open-account-threads]').forEach((button) => button.addEventListener('click', () => openThreadPane()));
document.querySelectorAll('[data-open-account-responses]').forEach((button) => button.addEventListener('click', openResponsePane));
accountIdentity.addEventListener('click', closeThreadPane);
document.getElementById('close-account-thread-detail').addEventListener('click', closeDetail);

document.querySelector('.account-thread-lists').addEventListener('click', (event) => {
  const header = event.target.closest('.summary-item-header');
  if (header) selectSummary(header.closest('.summary-item'));
  const detailTrigger = event.target.closest('[data-thread-detail]');
  if (detailTrigger) openDetail(detailTrigger.dataset.threadDetail);
});

document.querySelector('.account-response-pane').addEventListener('click', (event) => {
  const header = event.target.closest('[data-response-detail]');
  if (!header) return;
  if (openDetail(header.dataset.responseDetail)) {
    const target = document.querySelector(`[data-thread-detail-pane="${header.dataset.responseDetail}"] .thread-post:nth-of-type(${header.dataset.responseNumber})`);
    target?.scrollIntoView({block: 'center'});
    target?.classList.add('is-response-target');
    window.setTimeout(() => target?.classList.remove('is-response-target'), 1600);
  }
});

document.querySelectorAll('[data-thread-pane-pagination]').forEach((link) => link.addEventListener('click', () => {
  sessionStorage.setItem(threadPaneStorageKey, 'true');
  sessionStorage.removeItem(threadDetailStorageKey);
}));

document.querySelectorAll('[data-thread-tab]').forEach((tab) => tab.addEventListener('click', () => {
  document.querySelectorAll('[data-thread-tab]').forEach((item) => {
    const active = item === tab;
    item.classList.toggle('is-active', active);
    item.setAttribute('aria-selected', String(active));
  });
  document.querySelectorAll('.account-thread-column').forEach((column) => {
    column.classList.toggle('is-tab-active', column.dataset.threadColumn === tab.dataset.threadTab);
  });
}));

document.querySelectorAll('.account-thread-reply-form').forEach((form) => form.addEventListener('submit', async (event) => {
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
}));

if (sessionStorage.getItem(threadPaneStorageKey)) {
  openThreadPane(false);
  const restoredDetailId = sessionStorage.getItem(threadDetailStorageKey);
  if (restoredDetailId && !openDetail(restoredDetailId, false)) sessionStorage.removeItem(threadDetailStorageKey);
} else {
  updateAccountContext();
}

document.documentElement.classList.remove('has-restored-account-thread-pane');
