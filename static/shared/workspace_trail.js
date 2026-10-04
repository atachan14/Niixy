window.NiixyWorkspaceTrail = (() => {
  function workspaceHost() {
    const candidates = [
      ['.thread-workspace', '.thread-workspace', '.thread-track'],
      ['.account-page', '.account-workspace', '.account-track'],
      ['.room-page', '.room-workspace', '.room-track'],
      ['.mypage', '.mypage-viewport', '.mypage-workspace'],
    ];
    for (const [rootSelector, viewportSelector, trackSelector] of candidates) {
      const root = document.querySelector(rootSelector);
      if (!root) continue;
      const viewport = document.querySelector(viewportSelector);
      const track = document.querySelector(trackSelector);
      if (viewport && track) return {root, viewport, track};
    }
    return null;
  }

  function entityLink(anchor) {
    if (!anchor || anchor.closest('.site-header') || anchor.target || anchor.hasAttribute('download')) return null;
    const url = new URL(anchor.href, location.origin);
    if (url.origin !== location.origin) return null;
    let match = url.pathname.match(/^\/accounts\/([^/]+)\/$/);
    if (match) return {kind: 'account', id: decodeURIComponent(match[1]), pageUrl: url, paneUrl: `${url.pathname}pane/`};
    match = url.pathname.match(/^\/rooms\/(\d+)\/$/);
    if (match) return {kind: 'room', id: match[1], pageUrl: url, paneUrl: `${url.pathname}pane/`};
    return null;
  }

  function createPane(title, width = 'full') {
    const pane = document.createElement('section');
    pane.className = 'ui-workspace-trail-pane';
    pane.dataset.workspaceTrailWidth = width;
    const header = document.createElement('header');
    header.className = 'ui-pane-header ui-workspace-trail-header';
    const heading = document.createElement('h2');
    heading.textContent = title;
    const close = document.createElement('button');
    close.className = 'icon-button';
    close.type = 'button';
    close.textContent = '×';
    close.setAttribute('aria-label', '前のPaneに戻る');
    const body = document.createElement('div');
    body.className = 'ui-workspace-trail-body';
    body.innerHTML = '<p class="ui-pane-status">読み込み中...</p>';
    header.append(heading, close);
    pane.append(header, body);
    return {pane, header, heading, close, body};
  }

  function create(host) {
    const {root, viewport, track} = host;
    const entries = [];
    let baseState = null;

    function state() {
      return {
        offset: track.style.getPropertyValue('--ui-workspace-offset'),
        width: viewport.dataset.uiWorkspaceWidth || '',
        url: location.href,
      };
    }

    function align(entry, instant = false) {
      if (!entry?.pane?.isConnected) return;
      const apply = () => {
        const trackRect = track.getBoundingClientRect();
        const paneRect = entry.pane.getBoundingClientRect();
        const width = entry.width;
        const offset = width === 'full'
          ? Math.max(0, paneRect.left - trackRect.left)
          : Math.max(0, paneRect.right - trackRect.left - viewport.clientWidth);
        if (instant) track.classList.add('is-workspace-trail-aligning');
        viewport.scrollLeft = 0;
        viewport.dataset.uiWorkspaceWidth = width;
        track.style.setProperty('--ui-workspace-offset', `${offset}px`);
        if (instant) requestAnimationFrame(() => track.classList.remove('is-workspace-trail-aligning'));
      };
      requestAnimationFrame(() => requestAnimationFrame(apply));
    }

    function restore(snapshot) {
      if (snapshot.width) viewport.dataset.uiWorkspaceWidth = snapshot.width;
      else delete viewport.dataset.uiWorkspaceWidth;
      track.style.setProperty('--ui-workspace-offset', snapshot.offset || '0px');
      history.replaceState(history.state, '', snapshot.url);
    }

    function pop(entry = entries.at(-1)) {
      if (!entry || entries.at(-1) !== entry) return false;
      entry.abort?.abort();
      entry.pane.remove();
      entries.pop();
      if (entries.length) {
        restore(entry.previous);
        align(entries.at(-1));
      } else {
        root.classList.remove('is-workspace-trail-open');
        restore(baseState || entry.previous);
        baseState = null;
      }
      return true;
    }

    function push({title, width = 'full', url = location.href}) {
      if (!entries.length) baseState = state();
      const previous = state();
      const ui = createPane(title, width);
      const entry = {...ui, width, previous, url: String(url), abort: new AbortController()};
      root.classList.add('is-workspace-trail-open');
      track.append(ui.pane);
      entries.push(entry);
      ui.close.addEventListener('click', () => pop(entry));
      history.replaceState(history.state, '', entry.url);
      align(entry);
      return entry;
    }

    window.addEventListener('resize', () => align(entries.at(-1), true));
    function focus(element, width = 'remaining') {
      align({pane: element, width});
    }

    return {align, entries, focus, pop, push, track};
  }

  function paneUrl(template, id) {
    return template.replace('/0/', `/${id}/`);
  }

  async function fetchInto(entry, url, selector = null) {
    const response = await fetch(url, {cache: 'no-store', headers: {'X-Requested-With': 'fetch'}, signal: entry.abort.signal});
    if (!response.ok) throw new Error('Paneを読み込めませんでした。');
    const text = await response.text();
    if (!selector) {
      entry.body.innerHTML = text;
      return entry.body;
    }
    const parsed = new DOMParser().parseFromString(text, 'text/html');
    const fragment = parsed.querySelector(selector);
    if (!fragment) throw new Error('Paneの内容が見つかりませんでした。');
    entry.body.replaceChildren(fragment);
    return fragment;
  }

  function showError(entry, error) {
    if (!entry.pane.isConnected || error.name === 'AbortError') return;
    entry.body.innerHTML = '<p class="ui-pane-status has-load-error"></p>';
    entry.body.firstElementChild.textContent = error.message || '読み込みに失敗しました。';
  }

  function childUrl(base, params) {
    const url = new URL(base, location.origin);
    url.search = '';
    Object.entries(params).forEach(([name, value]) => {
      if (value !== null && value !== undefined && value !== '') url.searchParams.set(name, value);
    });
    return url;
  }

  function bindThreadDetail(entry, detailUrl) {
    entry.body.addEventListener('submit', async (event) => {
      const form = event.target.closest('.thread-reply-form');
      if (!form) return;
      event.preventDefault();
      const result = await NiixyUI.submitThreadReply(form, event.submitter);
      if (!result || !entry.pane.isConnected) return;
      try { await fetchInto(entry, detailUrl); }
      catch (error) { showError(entry, error); }
    });
  }

  function openThreadDetail(trail, source, threadId, postNumber = null) {
    const detailUrl = paneUrl(source.dataset.threadDetailTemplate, threadId);
    const url = childUrl(source.dataset.accountPageUrl || source.dataset.roomPageUrl, {thread: threadId, post: postNumber});
    const entry = trail.push({title: '読み込み中...', width: 'remaining', url});
    fetchInto(entry, detailUrl).then(() => {
      const detail = entry.body.querySelector('[data-thread-title], [data-thread-detail-pane]');
      entry.heading.textContent = detail?.dataset.threadTitle || '';
      if (postNumber) {
        const target = entry.body.querySelector(`[data-thread-post-number="${postNumber}"]`);
        target?.scrollIntoView({block: 'center'});
      }
      bindThreadDetail(entry, detailUrl);
    }).catch((error) => showError(entry, error));
  }

  function openAccountFeature(trail, account, kind) {
    const definitions = {
      thread: ['Thread一覧', account.dataset.threadPaneUrl],
      response: ['Response一覧', account.dataset.responsePaneUrl],
      room: ['Room一覧', account.dataset.roomPaneUrl],
      module: ['Module一覧', account.dataset.modulePaneUrl],
    };
    const definition = definitions[kind];
    if (!definition) {
      const entry = trail.push({title: kind === 'account-if' ? 'AccountIF一覧' : 'People一覧', width: 'fixed', url: childUrl(account.dataset.accountPageUrl, {pane: kind})});
      entry.body.innerHTML = '<p class="ui-pane-status">未実装</p>';
      return;
    }
    const [title, listUrl] = definition;
    const entry = trail.push({title, width: 'fixed', url: childUrl(account.dataset.accountPageUrl, {pane: kind})});
    entry.body.addEventListener('click', (event) => {
      const pagination = event.target.closest('[data-pane-pagination], [data-room-pagination], [data-summary-page]');
      if (pagination) {
        event.preventDefault();
        fetchInto(entry, pagination.href).then(() => NiixyUI.bindTabs(entry.body)).catch((error) => showError(entry, error));
        return;
      }
      const detail = event.target.closest('[data-thread-detail]');
      if (detail) openThreadDetail(trail, account, detail.dataset.threadDetail);
      const response = event.target.closest('[data-response-thread]');
      if (response) openThreadDetail(trail, account, response.dataset.responseThread, response.dataset.responsePost);
      const module = event.target.closest('[data-detail-url]');
      if (module) {
        event.preventDefault();
        const moduleEntry = trail.push({title: '読み込み中...', width: 'remaining', url: module.href});
        fetchInto(moduleEntry, module.dataset.detailUrl).then(() => {
          moduleEntry.heading.textContent = moduleEntry.body.querySelector('.ui-detail-pane h2, h2')?.textContent || 'Module詳細';
        }).catch((error) => showError(moduleEntry, error));
      }
    });
    fetchInto(entry, listUrl).then(() => NiixyUI.bindTabs(entry.body)).catch((error) => showError(entry, error));
  }

  function bindAccount(trail, entry, account) {
    const actions = [
      ['[data-open-account-threads]', 'thread'],
      ['[data-open-account-responses]', 'response'],
      ['[data-open-account-rooms]', 'room'],
      ['[data-open-account-modules]', 'module'],
      ['[data-open-account-account-if]', 'account-if'],
      ['[data-open-account-people]', 'people'],
    ];
    actions.forEach(([selector, kind]) => account.querySelector(selector)?.addEventListener('click', () => openAccountFeature(trail, account, kind)));
  }

  async function submitJsonForm(form, submitter = null) {
    if (form.dataset.confirmMessage && !window.confirm(form.dataset.confirmMessage)) return null;
    const error = form.querySelector('.room-form-error');
    if (error) error.hidden = true;
    const pending = NiixyUI.beginPendingAction(submitter || form.querySelector('[type="submit"]'));
    if (!pending) return null;
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form)});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || Object.values(result.errors || {}).flat().join(' ') || '処理に失敗しました。');
      return result;
    } catch (exception) {
      if (error) {
        error.textContent = exception.message || '処理に失敗しました。';
        error.hidden = false;
      }
      pending.restore();
      return null;
    }
  }

  function initializeCollectionControls(root) {
    root.querySelectorAll('[data-collection-panel-id]:not([data-workspace-trail-collection-ready])').forEach((collection) => {
      collection.dataset.workspaceTrailCollectionReady = 'true';
      const informationToggle = collection.querySelector('[data-collection-information-toggle]');
      const createToggle = collection.querySelector('[data-collection-create-toggle]');
      const editToggle = collection.querySelector('[data-collection-edit-toggle]');
      const informationWindow = collection.querySelector('[data-collection-information-window]');
      const createWindow = collection.querySelector('[data-collection-create-window]');
      const informationView = collection.querySelector('[data-collection-information-view]');
      const editor = collection.querySelector('[data-collection-editor]');
      const editForm = editor?.querySelector('.room-collection-edit');
      const showInformation = () => {
        if (!editor || !editToggle) return;
        editor.hidden = true;
        informationView.hidden = false;
        editToggle.textContent = '編集';
        editToggle.setAttribute('aria-expanded', 'false');
        editForm?.reset();
      };
      NiixyUI.createExclusivePanels(collection, {
        information: {toggle: informationToggle, panel: informationWindow, label: '詳細確認', onClose: showInformation},
        create: {toggle: createToggle, panel: createWindow, label: 'Board作成'},
      });
      editToggle?.addEventListener('click', () => {
        const open = editor.hidden;
        editor.hidden = !open;
        informationView.hidden = open;
        editToggle.textContent = open ? 'キャンセル' : '編集';
        editToggle.setAttribute('aria-expanded', String(open));
        if (!open) editForm?.reset();
      });
    });
  }

  function openRoomList(trail, room, kind) {
    const boards = kind === 'boards';
    const entry = trail.push({
      title: boards ? 'Board一覧' : '参加者一覧',
      width: 'fixed',
      url: childUrl(room.dataset.roomPageUrl, {[kind]: 1}),
    });
    const listUrl = boards ? room.dataset.boardsUrl : room.dataset.membersUrl;
    const fields = JSON.parse(room.querySelector('#room-pane-field-catalog')?.textContent || '[]');
    const interfaces = JSON.parse(room.querySelector('#room-pane-interface-catalog')?.textContent || '[]');

    const loadList = async () => {
      await fetchInto(entry, listUrl);
      NiixyUI.bindTabs(entry.body);
      initializeCollectionControls(entry.body);
    };

    const openBoard = (board) => {
      const boardEntry = trail.push({
        title: board.dataset.boardTitle,
        width: 'fixed',
        url: childUrl(room.dataset.roomPageUrl, {boards: 1, collection: board.dataset.boardCollection, board: board.dataset.openBoard}),
      });
      const boardUrl = board.dataset.boardUrl;
      let accountConditions = null;

      const loadBoard = async () => {
        accountConditions?.destroy();
        accountConditions = null;
        await fetchInto(boardEntry, boardUrl);
        boardEntry.heading.textContent = boardEntry.body.querySelector('[data-board-name]')?.dataset.boardName || board.dataset.boardTitle;
          const focusStage = (stage) => {
            if (stage === 'thread-list') {
              trail.align(boardEntry);
              return;
            }
            const widths = {
              'account-conditions': ['.account-condition-pane', 'fixed'],
              'account-selector': ['.account-selector-pane', 'fixed'],
              'account-condition-detail': ['.account-condition-detail-pane', 'remaining'],
              'account-condition-history-edit': ['.account-condition-detail-pane', 'remaining'],
            };
            if (widths[stage]) {
              const [selector, width] = widths[stage];
              const pane = Array.from(trail.track.querySelectorAll(selector)).at(-1);
              if (pane) trail.focus(pane, width);
              return;
            }
            const field = stage.startsWith('field-');
            const detail = stage.endsWith('-detail');
            const selector = detail
              ? `.thread-create-module-detail-pane${field ? '.thread-field-detail-pane' : ':not(.thread-field-detail-pane)'}`
              : `.thread-create-module-list-pane${field ? '.thread-field-list-pane' : ':not(.thread-field-list-pane)'}`;
            const pane = Array.from(trail.track.querySelectorAll(selector)).at(-1);
            if (pane) trail.focus(pane, detail ? 'remaining' : 'fixed');
          };
          if (window.NiixyRoomForms) {
            NiixyRoomForms.initialize(boardEntry.body, fields, interfaces, {
              selectorHost: trail.track,
              returnStage: 'thread-list',
              currentAccount: room.dataset.currentAccount,
              setStage: focusStage,
            });
          }
          if (window.NiixyAccountConditions) {
            accountConditions = NiixyAccountConditions.create({
              root: boardEntry.body,
              track: trail.track,
              setStage: focusStage,
              historyStage: 'account-conditions',
              selectorStage: 'account-selector',
              detailStage: 'account-condition-detail',
              historyEditStage: 'account-condition-history-edit',
              defaultReturnStage: 'thread-list',
              getReturnStage: () => 'thread-list',
              fieldCatalog: fields,
              authenticated: room.dataset.authenticated === 'true',
              currentAccount: room.dataset.currentAccount,
              listUrl: room.dataset.accountConditionListUrl,
              saveUrl: room.dataset.accountConditionSaveUrl,
              deleteUrl: room.dataset.accountConditionDeleteUrl,
              accountSearchUrl: room.dataset.accountSearchUrl,
              roomSearchUrl: room.dataset.accountConditionRoomSearchUrl,
              csrfToken: () => boardEntry.body.querySelector('[name="csrfmiddlewaretoken"]')?.value || '',
              conditionKindAllowed: (conditionKind) => ['default', 'account', 'room'].includes(conditionKind),
              conditionAllowed: (condition) => condition.kind !== 'default'
                || ['guest', 'account', 'self'].includes(condition.definition.code),
            });
          }
      };

      boardEntry.body.addEventListener('click', (event) => {
        const thread = event.target.closest('[data-room-thread]');
        if (thread) openThreadDetail(trail, room, thread.dataset.roomThread);
      });
      boardEntry.body.addEventListener('submit', async (event) => {
        const form = event.target.closest('[data-board-action], [data-board-thread-create]');
        if (!form) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const result = await submitJsonForm(form, event.submitter);
        if (!result) return;
        if (form.dataset.boardActionKind === 'delete') {
          accountConditions?.destroy();
          trail.pop(boardEntry);
          await loadList();
          return;
        }
        await loadBoard();
        if (result.thread_id) openThreadDetail(trail, room, result.thread_id);
      }, true);
      loadBoard().catch((error) => showError(boardEntry, error));
    };

    entry.body.addEventListener('click', (event) => {
      const board = event.target.closest('[data-open-board]');
      if (board) openBoard(board);
    });
    entry.body.addEventListener('submit', async (event) => {
      const form = event.target.closest('[data-board-action], [data-collection-action]');
      if (!form) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const result = await submitJsonForm(form, event.submitter);
      if (!result) return;
      await loadList();
      if (result.board_id) {
        const board = entry.body.querySelector(`[data-open-board="${result.board_id}"]`);
        if (board) openBoard(board);
      }
    }, true);
    loadList().catch((error) => showError(entry, error));
  }

  function bindRoom(trail, entry, room) {
    room.querySelector('[data-open-room-members]')?.addEventListener('click', () => openRoomList(trail, room, 'members'));
    room.querySelector('[data-open-room-boards]')?.addEventListener('click', () => openRoomList(trail, room, 'boards'));
    room.addEventListener('submit', async (event) => {
      const form = event.target.closest('[data-room-action]');
      if (!form) return;
      event.preventDefault();
      const pending = NiixyUI.beginPendingAction(event.submitter || form.querySelector('[type="submit"]'));
      if (!pending) return;
      try {
        const response = await fetch(form.action, {method: 'POST', body: new FormData(form)});
        if (!response.ok) throw new Error('処理に失敗しました。');
        const fresh = await NiixyUI.fetchFragment(`${room.dataset.roomPageUrl}pane/`);
        room.replaceWith(fresh);
        bindRoom(trail, entry, fresh);
      } catch (error) {
        pending.restore();
      }
    });
  }

  async function openEntity(trail, entity) {
    const entry = trail.push({title: '読み込み中...', width: 'full', url: entity.pageUrl});
    try {
      const selector = entity.kind === 'account' ? '[data-account-fragment]' : '[data-room-fragment]';
      const fragment = await fetchInto(entry, entity.paneUrl, selector);
      entry.heading.textContent = entity.kind === 'account' ? fragment.dataset.accountTitle : fragment.dataset.roomTitle;
      if (entity.kind === 'account') bindAccount(trail, entry, fragment);
      else bindRoom(trail, entry, fragment);
    } catch (error) {
      showError(entry, error);
    }
  }

  const host = workspaceHost();
  if (!host) return {open() {}};
  const trail = create(host);
  document.addEventListener('click', (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const anchor = event.target.closest('a[href]');
    if (anchor?.hasAttribute('data-detail-url')) return;
    const entity = entityLink(anchor);
    if (!entity) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openEntity(trail, entity);
  }, true);
  return {open: (url) => {
    const anchor = document.createElement('a');
    anchor.href = url;
    const entity = entityLink(anchor);
    if (entity) openEntity(trail, entity);
  }};
})();
