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
const roomBoardEdit = document.getElementById('edit-room-board');
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
}, {track: roomTrack});
let activeBoardId = null;
const requests = {list: 0, threads: 0, detail: 0};

function roomUrl(template, id) {
  return template.replace('/0/', `/${id}/`);
}

function updateUrl(values = {}) {
  const url = new URL(location.href);
  url.search = new URLSearchParams(values).toString();
  history.pushState({}, '', url);
}

function clearThreadPanes() {
  requests.threads += 1;
  requests.detail += 1;
  activeBoardId = null;
  roomThreadListTitle.textContent = '';
  roomBoardEdit.hidden = true;
  roomThreadListContent.innerHTML = '<p class="room-pane-loading">読み込み中...</p>';
  roomDetailTitle.textContent = '';
  roomDetailContent.innerHTML = '<p class="empty">Threadを選択してください。</p>';
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
  } catch {
    if (current === requests.list) roomListContent.innerHTML = '<p class="empty">読み込みに失敗しました。</p>';
  }
}

async function openBoard(boardId, title, url, updateHistory = true) {
  const current = ++requests.threads;
  requests.detail += 1;
  activeBoardId = String(boardId);
  roomThreadListTitle.textContent = title;
  roomBoardEdit.hidden = true;
  roomThreadListContent.innerHTML = '<p class="room-pane-loading">読み込み中...</p>';
  roomDetailTitle.textContent = '';
  roomDetailContent.innerHTML = '<p class="empty">Threadを選択してください。</p>';
  roomStack.set('thread-list');
  if (updateHistory) updateUrl({boards: 1, board: activeBoardId});
  try {
    const response = await fetch(url, {cache: 'no-store', headers: {'X-Requested-With': 'fetch'}});
    if (!response.ok) throw new Error();
    const html = await response.text();
    if (current !== requests.threads) return;
    roomThreadListContent.innerHTML = html;
    NiixyRoomForms.initialize(roomThreadListContent, roomFieldCatalog, roomInterfaceCatalog);
    const boardPane = roomThreadListContent.querySelector('.room-board-thread-list');
    roomBoardEdit.hidden = boardPane?.dataset.boardManageable !== 'true';
  } catch {
    if (current === requests.threads) roomThreadListContent.innerHTML = '<p class="empty">読み込みに失敗しました。</p>';
  }
}

async function openThread(threadId, updateHistory = true) {
  const current = ++requests.detail;
  roomDetailTitle.textContent = '';
  roomDetailContent.innerHTML = '<p class="room-pane-loading">読み込み中...</p>';
  roomStack.set('detail');
  if (updateHistory) updateUrl({boards: 1, board: activeBoardId, thread: threadId});
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
  roomBoardEdit.hidden = true;
  roomStack.set('list');
  updateUrl({boards: 1});
});
roomBoardEdit.addEventListener('click', () => {
  const actions = roomThreadListContent.querySelector('.room-board-actions');
  if (actions) actions.hidden = !actions.hidden;
});
document.getElementById('close-room-thread-detail').addEventListener('click', () => {
  requests.detail += 1;
  roomStack.set('thread-list');
  updateUrl({boards: 1, board: activeBoardId});
});

roomListContent.addEventListener('click', (event) => {
  const board = event.target.closest('[data-open-board]');
  if (!board) return;
  openBoard(board.dataset.openBoard, board.querySelector('.ui-summary-item-title').textContent, board.dataset.boardUrl);
});
roomThreadListContent.addEventListener('click', (event) => {
  const trigger = event.target.closest('[data-room-thread]');
  if (trigger) openThread(trigger.dataset.roomThread);
});

async function submitJsonForm(form, onSuccess) {
  const error = form.querySelector('.room-form-error');
  if (error) error.hidden = true;
  const pending = NiixyUI.beginPendingAction(form.querySelector('[type="submit"]'));
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
    submitJsonForm(roomAction, () => location.reload());
    return;
  }
  const boardAction = event.target.closest('[data-board-action]');
  if (boardAction) {
    event.preventDefault();
    if (boardAction.dataset.confirmMessage && !window.confirm(boardAction.dataset.confirmMessage)) return;
    submitJsonForm(boardAction, (result) => location.assign(result.redirect_url));
    return;
  }
  const create = event.target.closest('[data-board-thread-create]');
  if (create) {
    event.preventDefault();
    submitJsonForm(create, (result) => location.assign(result.redirect_url));
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
if (initialBoard) {
  openRoomList('Board一覧', roomPage.dataset.boardsUrl, 'boards', false).then(() => {
    const board = roomListContent.querySelector(`[data-open-board="${initialBoard}"]`);
    if (!board) return;
    openBoard(initialBoard, board.querySelector('.ui-summary-item-title').textContent, board.dataset.boardUrl, false).then(() => {
      const thread = initial.get('thread');
      if (thread) openThread(thread, false);
    });
  });
} else if (initial.has('boards')) {
  openRoomList('Board一覧', roomPage.dataset.boardsUrl, 'boards', false);
} else if (initial.has('members')) {
  openRoomList('参加者一覧', roomPage.dataset.membersUrl, 'members', false);
}
