const roomPage = document.querySelector('.room-page');
const roomWorkspace = document.querySelector('.room-workspace');
const roomTrack = document.querySelector('.room-track');
const roomListPane = document.querySelector('.room-list-pane');
const roomThreadListPane = document.querySelector('.room-thread-list-pane');
const roomDetailPane = document.querySelector('.room-thread-detail-pane');
const roomListTitle = document.getElementById('room-list-title');
const roomListContent = document.getElementById('room-list-content');
const roomThreadListTitle = document.getElementById('room-thread-list-title');
const roomThreadListContent = document.getElementById('room-thread-list-content');
const roomDetailTitle = document.getElementById('room-thread-detail-title');
const roomDetailContent = document.getElementById('room-thread-detail-content');
const roomIdentity = document.getElementById('room-page-identity');
const roomFieldCatalog = JSON.parse(document.getElementById('room-thread-field-catalog').textContent);
const roomInterfaceCatalog = JSON.parse(document.getElementById('room-thread-interface-catalog').textContent);
const roomStack = NiixyUI.createWorkspace(roomWorkspace, {
  overview: {root: true},
  list: {target: roomListPane},
  'thread-list': {target: roomThreadListPane},
  detail: {target: roomDetailPane},
  'interface-list': {target: '.thread-create-module-list-pane:not(.thread-field-list-pane)'},
  'interface-detail': {target: '.thread-create-module-detail-pane:not(.thread-field-detail-pane)'},
  'field-list': {target: '.thread-create-module-list-pane.thread-field-list-pane'},
  'field-detail': {target: '.thread-create-module-detail-pane.thread-field-detail-pane'},
  'account-conditions': {target: '.account-condition-pane', width: 'fixed'},
  'account-selector': {target: '.account-selector-pane', width: 'fixed'},
  'account-condition-detail': {target: '.account-condition-detail-pane', width: 'remaining'},
  'account-condition-history-edit': {target: '.account-condition-detail-pane', width: 'remaining'},
}, {track: roomTrack});
const roomAccountConditions = NiixyAccountConditions.create({
  root: roomPage,
  track: roomTrack,
  setStage: (stage) => roomStack.set(stage),
  historyStage: 'account-conditions',
  selectorStage: 'account-selector',
  detailStage: 'account-condition-detail',
  historyEditStage: 'account-condition-history-edit',
  defaultReturnStage: 'thread-list',
  getReturnStage: () => roomStack.stage,
  fieldCatalog: roomFieldCatalog,
  authenticated: roomPage.dataset.authenticated === 'true',
  currentAccount: roomPage.dataset.currentAccount,
  listUrl: roomPage.dataset.accountConditionListUrl,
  saveUrl: roomPage.dataset.accountConditionSaveUrl,
  deleteUrl: roomPage.dataset.accountConditionDeleteUrl,
  accountSearchUrl: roomPage.dataset.accountSearchUrl,
  roomSearchUrl: roomPage.dataset.accountConditionRoomSearchUrl,
  csrfToken: () => roomPage.querySelector('[name="csrfmiddlewaretoken"]').value,
  conditionKindAllowed: (kind) => ['default', 'account', 'room'].includes(kind),
  conditionAllowed: (condition) => condition.kind !== 'default'
    || ['guest', 'account', 'self'].includes(condition.definition.code),
});
let activeBoardId = null;
let activeCollectionId = null;
const requests = {list: 0, threads: 0, detail: 0};

function roomUrl(template, id) {
  return template.replace('/0/', `/${id}/`);
}

function updateUrl(values = {}) {
  const url = new URL(location.href);
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') params.set(key, value);
  });
  url.search = params.toString();
  history.pushState({}, '', url);
}

function clearThreadPanes() {
  requests.threads += 1;
  requests.detail += 1;
  activeBoardId = null;
  roomThreadListTitle.textContent = '';
  roomThreadListContent.innerHTML = '<p class="room-pane-loading">読み込み中...</p>';
  roomDetailTitle.textContent = '';
  roomDetailContent.innerHTML = '<p class="empty">Threadを選択してください。</p>';
}

function activateCollectionTab(tab) {
  if (!tab) return;
  roomListContent.querySelectorAll('[data-ui-tab]').forEach((item) => {
    const selected = item === tab;
    item.classList.toggle('is-active', selected);
    item.setAttribute('aria-selected', String(selected));
  });
  roomListContent.querySelectorAll('[data-ui-tab-panel]').forEach((panel) => {
    panel.classList.toggle('is-active', panel.dataset.uiTabPanel === tab.dataset.uiTab);
  });
}

function activateCollection(collectionId) {
  if (!collectionId) return;
  const tab = roomListContent.querySelector(`[data-collection-id="${collectionId}"]`);
  if (!tab) return;
  activeCollectionId = String(collectionId);
  activateCollectionTab(tab);
}

function activateCollectionManagement() {
  activeCollectionId = null;
  activateCollectionTab(roomListContent.querySelector('[data-collection-management-tab]'));
}

function initializeCollectionControls(root) {
  root.querySelectorAll('[data-collection-panel-id]:not([data-collection-controls-ready])').forEach((collection) => {
    collection.dataset.collectionControlsReady = 'true';
    const informationToggle = collection.querySelector('[data-collection-information-toggle]');
    const createToggle = collection.querySelector('[data-collection-create-toggle]');
    const editToggle = collection.querySelector('[data-collection-edit-toggle]');
    const informationWindow = collection.querySelector('[data-collection-information-window]');
    const createWindow = collection.querySelector('[data-collection-create-window]');
    const informationView = collection.querySelector('[data-collection-information-view]');
    const editor = collection.querySelector('[data-collection-editor]');
    const editForm = editor?.querySelector('.room-collection-edit');

    const showInformationView = () => {
      if (!editor || !editToggle) return;
      editor.hidden = true;
      informationView.hidden = false;
      editToggle.textContent = '編集';
      editToggle.setAttribute('aria-expanded', 'false');
      editForm?.reset();
    };

    NiixyUI.createExclusivePanels(collection, {
      information: {
        toggle: informationToggle,
        panel: informationWindow,
        label: '詳細確認',
        onClose: showInformationView,
      },
      create: {
        toggle: createToggle,
        panel: createWindow,
        label: 'Board作成',
      },
    });

    editToggle?.addEventListener('click', () => {
      const shouldOpen = editor.hidden;
      if (shouldOpen) {
        informationView.hidden = true;
        editor.hidden = false;
        editToggle.textContent = 'キャンセル';
        editToggle.setAttribute('aria-expanded', 'true');
      } else {
        showInformationView();
      }
    });
  });
}

async function openRoomList(title, url, listKind = 'members', updateHistory = true) {
  const current = ++requests.list;
  clearThreadPanes();
  roomListTitle.textContent = title;
  roomListContent.innerHTML = '<p class="room-pane-loading">読み込み中...</p>';
  roomStack.set('list');
  roomIdentity.disabled = false;
  if (updateHistory) updateUrl({[listKind]: 1});
  try {
    const response = await fetch(url, {cache: 'no-store', headers: {'X-Requested-With': 'fetch'}});
    if (!response.ok) throw new Error();
    const html = await response.text();
    if (current !== requests.list) return;
    roomListContent.innerHTML = html;
    NiixyUI.bindTabs(roomListContent);
    initializeCollectionControls(roomListContent);
    const params = new URLSearchParams(location.search);
    if (params.has('manage')) activateCollectionManagement();
    else activateCollection(params.get('collection'));
  } catch {
    if (current === requests.list) roomListContent.innerHTML = '<p class="empty">読み込みに失敗しました。</p>';
  }
}

async function openBoard(boardId, title, url, collectionId = null, updateHistory = true) {
  const current = ++requests.threads;
  requests.detail += 1;
  activeBoardId = String(boardId);
  activeCollectionId = collectionId ? String(collectionId) : activeCollectionId;
  roomThreadListTitle.textContent = title;
  roomThreadListContent.innerHTML = '<p class="room-pane-loading">読み込み中...</p>';
  roomDetailTitle.textContent = '';
  roomDetailContent.innerHTML = '<p class="empty">Threadを選択してください。</p>';
  roomStack.set('thread-list');
  if (updateHistory) updateUrl({boards: 1, collection: activeCollectionId, board: activeBoardId});
  try {
    const response = await fetch(url, {cache: 'no-store', headers: {'X-Requested-With': 'fetch'}});
    if (!response.ok) throw new Error();
    const html = await response.text();
    if (current !== requests.threads) return;
    roomThreadListContent.innerHTML = html;
    NiixyRoomForms.initialize(roomThreadListContent, roomFieldCatalog, roomInterfaceCatalog, {
      selectorHost: roomTrack,
      setStage: (stage) => roomStack.set(stage),
      returnStage: 'thread-list',
      currentAccount: roomPage.dataset.currentAccount,
    });
  } catch {
    if (current === requests.threads) roomThreadListContent.innerHTML = '<p class="empty">読み込みに失敗しました。</p>';
  }
}

async function openThread(threadId, updateHistory = true) {
  const current = ++requests.detail;
  roomDetailTitle.textContent = '';
  roomDetailContent.innerHTML = '<p class="room-pane-loading">読み込み中...</p>';
  roomStack.set('detail');
  if (updateHistory) updateUrl({boards: 1, collection: activeCollectionId, board: activeBoardId, thread: threadId});
  try {
    const response = await fetch(roomUrl(roomPage.dataset.threadDetailTemplate, threadId), {cache: 'no-store', headers: {'X-Requested-With': 'fetch'}});
    if (!response.ok) throw new Error();
    const html = await response.text();
    if (current !== requests.detail) return;
    roomDetailContent.innerHTML = html;
    roomDetailTitle.textContent = roomDetailContent.querySelector('[data-thread-title]')?.dataset.threadTitle || '';
  } catch {
    if (current === requests.detail) roomDetailContent.innerHTML = '<p class="empty">読み込みに失敗しました。</p>';
  }
}

function showOverview() {
  Object.keys(requests).forEach((key) => { requests[key] += 1; });
  roomStack.set('overview');
  roomIdentity.disabled = true;
  activeBoardId = null;
  activeCollectionId = null;
  updateUrl();
}

document.querySelector('[data-open-room-members]')?.addEventListener('click', () => openRoomList('参加者一覧', roomPage.dataset.membersUrl));
document.querySelector('[data-open-room-boards]')?.addEventListener('click', () => openRoomList('Board一覧', roomPage.dataset.boardsUrl, 'boards'));
roomIdentity.addEventListener('click', showOverview);
document.getElementById('close-room-list').addEventListener('click', showOverview);
document.getElementById('close-room-thread-list').addEventListener('click', () => {
  requests.threads += 1;
  requests.detail += 1;
  activeBoardId = null;
  roomStack.set('list');
  updateUrl({boards: 1, collection: activeCollectionId});
});
document.getElementById('close-room-thread-detail').addEventListener('click', () => {
  requests.detail += 1;
  roomStack.set('thread-list');
  updateUrl({boards: 1, collection: activeCollectionId, board: activeBoardId});
});

roomListContent.addEventListener('click', (event) => {
  const managementTab = event.target.closest('[data-collection-management-tab]');
  if (managementTab) {
    activeCollectionId = null;
    updateUrl({boards: 1, manage: 1});
    return;
  }
  const collectionTab = event.target.closest('[data-collection-id]');
  if (collectionTab) {
    activeCollectionId = collectionTab.dataset.collectionId;
    updateUrl({boards: 1, collection: activeCollectionId});
    return;
  }
  const board = event.target.closest('[data-open-board]');
  if (!board) return;
  openBoard(board.dataset.openBoard, board.dataset.boardTitle, board.dataset.boardUrl, board.dataset.boardCollection);
});
roomThreadListContent.addEventListener('click', (event) => {
  const trigger = event.target.closest('[data-room-thread]');
  if (trigger) openThread(trigger.dataset.roomThread);
});

async function submitJsonForm(form, onSuccess, submitter = null) {
  const error = form.querySelector('.room-form-error');
  if (error) error.hidden = true;
  const pending = NiixyUI.beginPendingAction(submitter || form.querySelector('[type="submit"]'));
  if (!pending) return;
  try {
    const response = await fetch(form.action, {method: 'POST', body: new FormData(form)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || Object.values(result.errors || {}).flat().join(' '));
    onSuccess(result);
  } catch (exception) {
    if (error) {
      error.textContent = exception.message || '処理に失敗しました。';
      error.hidden = false;
    }
    pending.restore();
  }
}

document.addEventListener('submit', (event) => {
  const roomAction = event.target.closest('[data-room-action]');
  if (roomAction) {
    event.preventDefault();
    submitJsonForm(roomAction, () => location.reload(), event.submitter);
    return;
  }
  const boardAction = event.target.closest('[data-board-action]');
  if (boardAction) {
    event.preventDefault();
    if (boardAction.dataset.confirmMessage && !window.confirm(boardAction.dataset.confirmMessage)) return;
    submitJsonForm(boardAction, (result) => location.assign(result.redirect_url), event.submitter);
    return;
  }
  const collectionAction = event.target.closest('[data-collection-action]');
  if (collectionAction) {
    event.preventDefault();
    if (collectionAction.dataset.confirmMessage && !window.confirm(collectionAction.dataset.confirmMessage)) return;
    submitJsonForm(collectionAction, (result) => location.assign(result.redirect_url), event.submitter);
    return;
  }
  const create = event.target.closest('[data-board-thread-create]');
  if (create) {
    event.preventDefault();
    submitJsonForm(create, (result) => location.assign(result.redirect_url), event.submitter);
  }
});

roomDetailContent.addEventListener('submit', async (event) => {
  const form = event.target.closest('.thread-reply-form');
  if (!form) return;
  event.preventDefault();
  const result = await NiixyUI.submitThreadReply(form, event.submitter);
  if (result) await openThread(roomDetailContent.querySelector('[data-thread-id]').dataset.threadId, false);
});

window.addEventListener('popstate', () => location.reload());

const initial = new URLSearchParams(location.search);
const initialBoard = initial.get('board');
async function restoreInitialRoomWorkspace() {
  if (initialBoard) {
    await openRoomList('Board一覧', roomPage.dataset.boardsUrl, 'boards', false);
    const board = roomListContent.querySelector(`[data-open-board="${initialBoard}"]`);
    if (!board) return;
    activateCollection(board.dataset.boardCollection);
    await openBoard(initialBoard, board.dataset.boardTitle, board.dataset.boardUrl, board.dataset.boardCollection, false);
    const thread = initial.get('thread');
    if (thread) await openThread(thread, false);
  } else if (initial.has('boards')) {
    await openRoomList('Board一覧', roomPage.dataset.boardsUrl, 'boards', false);
  } else if (initial.has('members')) {
    await openRoomList('参加者一覧', roomPage.dataset.membersUrl, 'members', false);
  }
}

restoreInitialRoomWorkspace().finally(() => requestAnimationFrame(() => requestAnimationFrame(() => {
  document.documentElement.classList.remove('has-restored-room-workspace');
})));
