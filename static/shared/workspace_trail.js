window.NiixyWorkspaceTrail = (() => {
  function workspaceHost() {
    const candidates = [
      ['.reference-page', '.reference-workspace', '.reference-track'],
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
    if (url.pathname === '/' && /^\d+$/.test(url.searchParams.get('board') || '') && !url.searchParams.has('room')) return {kind: 'board', id: url.searchParams.get('board'), pageUrl: url};
    const referenceMatch = url.pathname.match(/^\/(boards|interfaces|board-lists|interface-lists)\/(\d+)\/$/);
    if (referenceMatch) return {kind:'content-reference', pageUrl:url};
    let listMatch = url.pathname.match(/^\/accounts\/lists\/(\d+)\/$/);
    if (listMatch) return {kind:'account-list', id:listMatch[1], pageUrl:url};
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
    let alignment = 0;
    let focusedPane = null;

    function state() {
      return {
        offset: track.style.getPropertyValue('--ui-workspace-offset'),
        width: viewport.dataset.uiWorkspaceWidth || '',
        url: location.href,
      };
    }

    function align(entry, instant = false) {
      if (!entry?.pane?.isConnected) return;
      focusedPane = entry;
      const revision = ++alignment;
      const apply = () => {
        if (!entry.pane.isConnected || revision !== alignment) return;
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
      if (instant) apply();
      else requestAnimationFrame(() => requestAnimationFrame(apply));
    }

    function restore(snapshot) {
      alignment += 1;
      if (snapshot.width) viewport.dataset.uiWorkspaceWidth = snapshot.width;
      else delete viewport.dataset.uiWorkspaceWidth;
      track.style.setProperty('--ui-workspace-offset', snapshot.offset || '0px');
      history.replaceState(history.state, '', snapshot.url);
    }

    function pop(entry = entries.at(-1)) {
      const index = entries.indexOf(entry);
      if (index < 0) return false;
      discardAfter(entries[index - 1] || null);
      if (entries.length) align(entries.at(-1));
      return true;
    }

    function discardAfter(anchor = null) {
      const index = anchor ? entries.indexOf(anchor) : -1;
      if (anchor && index < 0) return false;
      const removed = entries.splice(index + 1);
      if (!removed.length) return false;
      removed.slice().reverse().forEach((entry) => {
        entry.abort?.abort();
        entry.request?.abort();
        entry.dispose?.();
        entry.pane.remove();
      });
      restore(removed[0].previous);
      if (!entries.length) {
        root.classList.remove('is-workspace-trail-open');
      }
      return true;
    }

    function prepare(source) {
      const origin = source?.pane ? source : entries.find((entry) => entry.pane.contains(source));
      if (origin) {
        if (!entries.includes(origin)) throw new DOMException('Pane was closed', 'AbortError');
        discardAfter(origin);
        origin.pane.dispatchEvent(new Event('ui-workspace-retain'));
      } else {
        discardAfter();
        track.niixyWorkspace?.retain(source);
      }
      return origin || null;
    }

    function push({title, width = 'full', url = location.href, after = undefined}) {
      if (after !== undefined) prepare(after);
      const previous = state();
      const ui = createPane(title, width);
      const entry = {...ui, width, previous, url: String(url), abort: new AbortController()};
      root.classList.add('is-workspace-trail-open');
      track.append(ui.pane);
      entries.push(entry);
      ui.close.addEventListener('click', () => pop(entry));
      history.replaceState(history.state, '', entry.url);
      // Source retention/replacement must not suppress the opening transition.
      align(entry);
      return entry;
    }

    window.addEventListener('resize', () => align(focusedPane?.pane.isConnected ? focusedPane : entries.at(-1), true));
    function focus(element, width = 'remaining') {
      let entry = entries.find((candidate) => candidate.pane === element);
      if (entry) discardAfter(entry);
      else {
        entry = {pane: element, width, previous: state(), url: location.href, abort: new AbortController()};
        entries.push(entry);
      }
      element.classList.add('ui-workspace-trail-auxiliary');
      element.dataset.workspaceTrailWidth = width;
      element.hidden = false;
      for (let next = element.nextElementSibling; next; next = next.nextElementSibling) {
        if (next.classList.contains('ui-workspace-trail-auxiliary')) next.hidden = true;
      }
      align(entry);
    }

    return {align, discardAfter, entries, focus, pop, prepare, push, track};
  }

  function paneUrl(template, id) {
    return template.replace('/0/', `/${id}/`);
  }

  async function fetchInto(entry, url, selector = null) {
    entry.request?.abort();
    const request = new AbortController();
    entry.request = request;
    const assertCurrent = () => {
      if (!entry.pane.isConnected || entry.abort.signal.aborted || request.signal.aborted || entry.request !== request) {
        throw new DOMException('Pane request was superseded', 'AbortError');
      }
    };
    assertCurrent();
    const response = await fetch(url, {cache: 'no-store', headers: {'X-Requested-With': 'fetch'}, signal: request.signal});
    assertCurrent();
    if (!response.ok) throw new Error('Paneを読み込めませんでした。');
    const text = await response.text();
    assertCurrent();
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

  function openThreadDetail(trail, source, threadId, postNumber = null, origin) {
    const detailUrl = paneUrl(source.dataset.threadDetailTemplate, threadId);
    const url = new URL(origin?.url || source.dataset.accountPageUrl || source.dataset.roomPageUrl, location.origin);
    url.searchParams.set('thread', threadId);
    if (postNumber) url.searchParams.set('post', postNumber);
    else url.searchParams.delete('post');
    const entry = trail.push({title: '読み込み中...', width: 'remaining', url, after: origin});
    fetchInto(entry, detailUrl).then(() => {
      const detail = entry.body.querySelector('[data-thread-title], [data-thread-detail-pane]');
      entry.heading.textContent = detail?.dataset.threadTitle || '';
      if (postNumber) {
        const target = entry.body.querySelector(`[data-thread-post-number="${postNumber}"]`);
        if (target) entry.body.scrollTop += target.getBoundingClientRect().top - entry.body.getBoundingClientRect().top - entry.body.clientHeight / 2;
      }
      bindThreadDetail(entry, detailUrl);
    }).catch((error) => showError(entry, error));
  }

  function openAccountFeature(trail, account, kind, origin) {
    if (kind === 'people') return window.NiixyAccountLists.openIndex(account);
    if (kind === 'board') return openRoomList(trail, account, 'boards', origin);
    const definitions = {
      thread: ['Thread一覧', account.dataset.threadPaneUrl],
      response: ['Response一覧', account.dataset.responsePaneUrl],
      room: ['Room一覧', account.dataset.roomPaneUrl],
      module: ['Module一覧', account.dataset.modulePaneUrl],
      'account-if': ['Applied一覧', account.dataset.appliedUrl],
    };
    const definition = definitions[kind];
    if (!definition) {
      const entry = trail.push({title: kind === 'account-if' ? 'AccountIF一覧' : 'People一覧', width: 'fixed', url: childUrl(account.dataset.accountPageUrl, {pane: kind}), after: origin});
      entry.body.innerHTML = '<p class="ui-pane-status">未実装</p>';
      return;
    }
    const [title, listUrl] = definition;
    const entry = trail.push({title, width: 'fixed', url: childUrl(account.dataset.accountPageUrl, {pane: kind}), after: origin});
    if (kind === 'account-if') entry.body.addEventListener('focusin', (event) => {
      const tab = event.target;
      if (!tab.matches('[data-ui-tab]')) return;
      requestAnimationFrame(() => { if (entry.pane.isConnected && document.activeElement === tab) trail.align(entry); });
    });
    entry.body.addEventListener('click', (event) => {
      const pagination = event.target.closest('[data-pane-pagination], [data-room-pagination], [data-summary-page]');
      if (pagination) {
        event.preventDefault();
        fetchInto(entry, pagination.href).then(() => NiixyUI.bindTabs(entry.body)).catch((error) => showError(entry, error));
        return;
      }
      const detail = event.target.closest('[data-thread-detail]');
      if (detail) openThreadDetail(trail, account, detail.dataset.threadDetail, null, entry);
      const response = event.target.closest('[data-response-thread]');
      if (response) openThreadDetail(trail, account, response.dataset.responseThread, response.dataset.responsePost, entry);
      const module = event.target.closest('[data-detail-url]');
      if (module) {
        event.preventDefault();
        const moduleEntry = trail.push({title: '読み込み中...', width: 'remaining', url: module.href, after: entry});
        fetchInto(moduleEntry, module.dataset.detailUrl).then(() => {
          moduleEntry.heading.textContent = moduleEntry.body.querySelector('.ui-detail-pane h2, h2')?.textContent || 'Module詳細';
          const layout = moduleEntry.body.querySelector('[data-layout-detail]');
          if (layout) window.NiixyAccountLayouts?.bind(layout, {inline: true});
        }).catch((error) => showError(moduleEntry, error));
      }
    });
    fetchInto(entry, listUrl, kind === 'account-if' ? '.applied-list-content' : null).then(() => NiixyUI.bindTabs(entry.body)).catch((error) => showError(entry, error));
  }

  function bindAccount(trail, entry, account) {
    const actions = [
      ['[data-open-account-threads]', 'thread'],
      ['[data-open-account-responses]', 'response'],
      ['[data-open-account-rooms]', 'room'],
      ['[data-open-account-boards]', 'board'],
      ['[data-open-account-modules]', 'module'],
      ['[data-open-account-account-if]', 'account-if'],
      ['[data-open-account-people]', 'people'],
    ];
    actions.forEach(([selector, kind]) => account.querySelector(selector)?.addEventListener('click', () => openAccountFeature(trail, account, kind, entry)));
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

  function openBoardPane(trail, room, board, origin, onDelete = null) {
    const accountScope = Boolean(room.dataset.accountPageUrl);
    const pageUrl = room.dataset.accountPageUrl || room.dataset.roomPageUrl || '/';
    const listParams = room.dataset.mapBoard === 'true' ? {} : (accountScope ? {pane: 'board'} : {boards: 1});
    const threadSource = accountScope ? {dataset: {...room.dataset, threadDetailTemplate: room.dataset.boardThreadDetailTemplate}} : room;
    const fields = JSON.parse(room.querySelector('#board-pane-field-catalog, #room-pane-field-catalog, #thread-field-catalog-data')?.textContent || '[]');
    const interfaces = JSON.parse(room.querySelector('#board-pane-interface-catalog, #room-pane-interface-catalog, #thread-interface-catalog-data')?.textContent || '[]');
    const boardEntry = trail.push({
      title: board.dataset.boardTitle,
      width: 'fixed',
      url: board.dataset.boardPageUrl || childUrl(pageUrl, {...listParams, collection: board.dataset.boardCollection, board: board.dataset.openBoard}),
      after: origin,
    });
    const boardUrl = board.dataset.boardUrl;
    let accountConditions = null;
    const removeSelectors = () => trail.track.querySelectorAll('.thread-create-module-selector-pane').forEach((pane) => {
      if (pane.workspaceOwner === boardEntry.pane) pane.remove();
    });
    boardEntry.dispose = () => { accountConditions?.destroy(); removeSelectors(); };
    boardEntry.pane.addEventListener('ui-workspace-retain', () => { accountConditions?.close(); removeSelectors(); });

    const loadBoard = async () => {
      accountConditions?.destroy();
      accountConditions = null;
      await fetchInto(boardEntry, boardUrl);
      boardEntry.heading.textContent = boardEntry.body.querySelector('[data-board-name]')?.dataset.boardName || board.dataset.boardTitle;
        const focusStage = (stage) => {
          if (stage === 'thread-list') {
            trail.discardAfter(boardEntry);
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
            owner: boardEntry.pane,
            beforeSelectorOpen: () => trail.prepare(boardEntry),
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
            extraDefaultCodes: () => ['guest', 'account'],
          conditionKindAllowed: (conditionKind) => ['default', 'account', 'room'].includes(conditionKind),
            conditionAllowed: (condition) => condition.kind !== 'default'
              || ['guest', 'account', 'self'].includes(condition.definition.code),
          });
        }
    };

    boardEntry.body.addEventListener('click', (event) => {
      const thread = event.target.closest('[data-room-thread]');
      if (thread) openThreadDetail(trail, threadSource, thread.dataset.roomThread, null, boardEntry);
    });
    boardEntry.body.addEventListener('submit', async (event) => {
      const form = event.target.closest('[data-board-action], [data-board-thread-create]');
      if (!form) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const result = await submitJsonForm(form, event.submitter);
      if (!result || !boardEntry.pane.isConnected || !form.isConnected) return;
      if (form.dataset.boardActionKind === 'delete') {
        accountConditions?.destroy();
        trail.pop(boardEntry);
        if (onDelete) await onDelete();
        return;
      }
      try {
        await loadBoard();
        if (result.thread_id) openThreadDetail(trail, threadSource, result.thread_id, null, boardEntry);
      } catch (error) { showError(boardEntry, error); }
    }, true);
    return loadBoard().then(() => boardEntry).catch((error) => showError(boardEntry, error));
    }

  function openRoomList(trail, room, kind, origin, restoreParams = null) {
    const boards = kind === 'boards';
    const accountScope = Boolean(room.dataset.accountPageUrl);
    const pageUrl = room.dataset.accountPageUrl || room.dataset.roomPageUrl;
    const listParams = accountScope ? {pane: 'board'} : {[kind]: 1};
    const initial = restoreParams || new URLSearchParams();
    const threadSource = accountScope ? {dataset: {...room.dataset, threadDetailTemplate: room.dataset.boardThreadDetailTemplate}} : room;
    const entry = trail.push({
      title: boards ? 'Board一覧' : '参加者一覧',
      width: 'fixed',
      url: childUrl(pageUrl, {...listParams, collection: initial.get('collection'), tab: initial.get('tab')}),
      after: origin,
    });
    const listUrl = boards ? room.dataset.boardsUrl : room.dataset.membersUrl;
    const fields = JSON.parse(room.querySelector('#board-pane-field-catalog, #room-pane-field-catalog')?.textContent || '[]');
    const interfaces = JSON.parse(room.querySelector('#board-pane-interface-catalog, #room-pane-interface-catalog')?.textContent || '[]');

    let listAccountConditions = null;
    entry.dispose = () => listAccountConditions?.destroy();
    entry.pane.addEventListener('ui-workspace-retain', () => listAccountConditions?.close());
    const loadList = async (collectionId = null) => {
      listAccountConditions?.destroy();
      listAccountConditions = null;
      await fetchInto(entry, listUrl);
      NiixyUI.bindTabs(entry.body);
      initializeCollectionControls(entry.body);
      const selectedId = collectionId || new URL(entry.url).searchParams.get('collection');
      const selected = selectedId && entry.body.querySelector(`[data-collection-id="${selectedId}"]`);
      if (selected) selected.click();
      if (boards && window.NiixyAccountConditions) {
        listAccountConditions = NiixyAccountConditions.create({
          root: entry.body,
          track: trail.track,
          setStage: (stage) => {
            if (stage === 'room-list') {
              trail.discardAfter(entry);
              trail.align(entry);
              return;
            }
            const selector = {
              'account-conditions': '.account-condition-pane',
              'account-selector': '.account-selector-pane',
              'account-condition-detail': '.account-condition-detail-pane',
              'account-condition-history-edit': '.account-condition-detail-pane',
            }[stage];
            const pane = selector && Array.from(trail.track.querySelectorAll(selector)).at(-1);
            if (pane) trail.focus(pane, stage.startsWith('account-condition-detail') || stage.endsWith('history-edit') ? 'remaining' : 'fixed');
          },
          historyStage: 'account-conditions',
          selectorStage: 'account-selector',
          detailStage: 'account-condition-detail',
          historyEditStage: 'account-condition-history-edit',
          defaultReturnStage: 'room-list',
          getReturnStage: () => 'room-list',
          fieldCatalog: fields,
          authenticated: room.dataset.authenticated === 'true',
          currentAccount: room.dataset.currentAccount,
          listUrl: room.dataset.accountConditionListUrl,
          saveUrl: room.dataset.accountConditionSaveUrl,
          deleteUrl: room.dataset.accountConditionDeleteUrl,
          accountSearchUrl: room.dataset.accountSearchUrl,
          roomSearchUrl: room.dataset.accountConditionRoomSearchUrl,
          csrfToken: () => entry.body.querySelector('[name="csrfmiddlewaretoken"]')?.value || '',
          conditionKindAllowed: (kind) => ['default', 'account', 'room'].includes(kind),
          conditionAllowed: (condition) => condition.kind !== 'default'
            || ['guest', 'account', 'self'].includes(condition.definition.code),
        });
      }
    };

    const openBoard = (board) => openBoardPane(trail, room, board, entry, () => loadList().catch((error) => showError(entry, error)));

    entry.body.addEventListener('focusin', (event) => {
      const input = event.target;
      if (!input.matches('input:not([type="hidden"]), textarea, select')
        || !input.closest('[data-board-action-kind="create"]')) return;
      requestAnimationFrame(() => {
        if (entry.pane.isConnected && document.activeElement === input) trail.align(entry);
      });
    });
    entry.body.addEventListener('click', (event) => {
      const tab = event.target.closest('[data-ui-tab]');
      if (tab) {
        const url = childUrl(pageUrl, {...listParams, collection: tab.dataset.collectionId || null, tab: tab.dataset.collectionId ? null : tab.dataset.uiTab});
        entry.url = url.href;
        history.replaceState(history.state, '', url);
      }
      const board = event.target.closest('[data-open-board]');
      if (board) openBoard(board);
    });
    entry.body.addEventListener('submit', async (event) => {
      const form = event.target.closest('[data-board-action], [data-collection-action]');
      if (!form) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const result = await submitJsonForm(form, event.submitter);
      if (!result || !entry.pane.isConnected || !form.isConnected) return;
      try {
        const resultUrl = new URL(result.redirect_url, location.origin);
        await loadList(result.collection_id && form.dataset.collectionActionKind !== 'delete' ? result.collection_id : resultUrl.searchParams.get('collection'));
        if (result.board_id) {
          const board = entry.body.querySelector(`[data-open-board="${result.board_id}"]`);
          if (board) openBoard(board);
        }
      } catch (error) { showError(entry, error); }
    }, true);
    return loadList().then(async () => {
      const tab = initial.get('tab');
      if (tab) entry.body.querySelector(`[data-ui-tab="${CSS.escape(tab)}"]`)?.click();
      const boardId = initial.get('board');
      const threadId = initial.get('thread');
      const board = boardId && entry.body.querySelector(`[data-open-board="${boardId}"]`);
      if (board) {
        const boardEntry = await openBoard(board);
        if (threadId && boardEntry) openThreadDetail(trail, threadSource, threadId, null, boardEntry);
      }
    }).catch((error) => showError(entry, error));
  }

  function bindRoom(trail, entry, room) {
    room.querySelector('[data-open-room-members]')?.addEventListener('click', () => openRoomList(trail, room, 'members', entry));
    room.querySelector('[data-open-room-boards]')?.addEventListener('click', () => openRoomList(trail, room, 'boards', entry));
    room.addEventListener('submit', async (event) => {
      const form = event.target.closest('[data-room-action]');
      if (!form) return;
      event.preventDefault();
      event.stopPropagation();
      const pending = NiixyUI.beginPendingAction(event.submitter || form.querySelector('[type="submit"]'));
      if (!pending) return;
      try {
        const response = await fetch(form.action, {method: 'POST', body: new FormData(form)});
        if (!response.ok) throw new Error('処理に失敗しました。');
        const fresh = await NiixyUI.fetchFragment(`${room.dataset.roomPageUrl}pane/`);
        if (!entry.pane.isConnected || !room.isConnected) return;
        room.replaceWith(fresh);
        bindRoom(trail, entry, fresh);
      } catch (error) {
        pending.restore();
      }
    });
  }

  async function openEntity(trail, entity, origin) {
    if (entity.kind === 'content-reference') return window.NiixyContentReferences.open(entity.pageUrl, origin);
    if (entity.kind === 'account-list') return window.NiixyAccountLists.openDetail(entity.pageUrl, origin);
    if (entity.kind === 'board') return openMapBoard(entity.id, origin, entity.pageUrl.searchParams.get('thread'));
    const entry = trail.push({title: '読み込み中...', width: 'full', url: entity.pageUrl, after: origin});
    try {
      const selector = entity.kind === 'account' ? '[data-account-fragment]' : '[data-room-fragment]';
      const fragment = await fetchInto(entry, entity.paneUrl, selector);
      entry.heading.textContent = entity.kind === 'account' ? fragment.dataset.accountTitle : fragment.dataset.roomTitle;
      if (fragment.dataset.createdAt) {
        const date = document.createElement('time');
        date.className = 'ui-identity-created'; date.dateTime = fragment.dataset.createdAt;
        date.textContent = `作成 ${fragment.dataset.createdLabel}`;
        entry.header.insertBefore(date, entry.close);
      }
      if (entity.kind === 'account') bindAccount(trail, entry, fragment);
      else bindRoom(trail, entry, fragment);
    } catch (error) {
      showError(entry, error);
    }
  }

  async function openMapBoard(boardId, origin = null, threadId = null) {
    const source = document.createElement('div');
    const root = host.root;
    source.dataset.mapBoard = 'true';
    source.dataset.roomPageUrl = '/';
    source.dataset.threadDetailTemplate = `/boards/${boardId}/threads/0/`;
    Object.entries(root.dataset).forEach(([key, value]) => { if (!(key in source.dataset)) source.dataset[key] = value; });
    source.dataset.currentAccount = root.dataset.currentAccount || root.dataset.currentActor || '';
    for (const id of ['thread-field-catalog-data', 'thread-interface-catalog-data', 'board-pane-field-catalog', 'room-pane-field-catalog', 'board-pane-interface-catalog', 'room-pane-interface-catalog']) {
      const catalog = document.getElementById(id); if (catalog) source.append(catalog.cloneNode(true));
    }
    root.dispatchEvent(new CustomEvent('niimap-board-select', {detail: String(boardId)}));
    const summary = root.querySelector(`.board-item[data-board-id="${boardId}"]`);
    const board = {dataset: {openBoard: String(boardId), boardTitle: summary?.dataset.boardTitle || 'Board', boardUrl: `/boards/${boardId}/pane/`}};
    const entry = await openBoardPane(trail, source, board, origin);
    if (threadId && entry) openThreadDetail(trail, source, threadId, null, entry);
    return entry;
  }

  function openReferenceBoard(boardId, origin, threadId = null, postNumber = null) {
    const source = document.createElement('div');
    source.dataset.mapBoard = 'true'; source.dataset.roomPageUrl = '/';
    source.dataset.threadDetailTemplate = `/boards/${boardId}/references/threads/0/`;
    const root = host.root;
    for (const key of ['currentAccount','authenticated','accountConditionListUrl','accountConditionSaveUrl','accountConditionDeleteUrl','accountSearchUrl','accountConditionRoomSearchUrl']) source.dataset[key] = root.dataset[key] || '';
    for (const id of ['thread-field-catalog-data','thread-interface-catalog-data','board-pane-field-catalog','room-pane-field-catalog','board-pane-interface-catalog','room-pane-interface-catalog']) {
      const catalog = document.getElementById(id); if (catalog) source.append(catalog.cloneNode(true));
    }
    const board = {dataset:{openBoard:String(boardId), boardTitle:'Board', boardUrl:`/boards/${boardId}/reference/`, boardPageUrl:`/boards/${boardId}/`}};
    return openBoardPane(trail, source, board, origin).then(entry => {
      if (entry && /^\d+$/.test(threadId || '')) openThreadDetail(trail, source, threadId, postNumber, entry);
      return entry;
    });
  }
  const host = workspaceHost();
  if (!host) return {clear() {}, open() {}, prepare() {}};
  const trail = create(host);
  const initialPath = location.pathname;
  window.addEventListener('popstate', (event) => {
    const url = location.href;
    trail.discardAfter();
    history.replaceState(history.state, '', url);
    if (location.pathname !== initialPath) {
      event.stopImmediatePropagation();
      location.reload();
    }
  }, true);
  document.addEventListener('click', (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const anchor = event.target.closest('a[href]');
    if (anchor?.hasAttribute('data-detail-url')) return;
    const entity = entityLink(anchor);
    if (!entity) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openEntity(trail, entity, anchor);
  }, true);
  function openReviewEditor(source) {
    const entry = trail.push({title: 'Review', width: 'remaining', after: source});
    // Focusing/typing in a retained offscreen form can make the browser scroll
    // the overflow-hidden viewport in addition to our track transform.
    const align = () => requestAnimationFrame(() => trail.align(entry, true));
    entry.body.addEventListener('focusin', align);
    entry.body.addEventListener('input', align);
    return entry;
  }

  function openContentPane({title, width = 'fixed', url = location.href, source}) {
    const entry = trail.push({title, width, url, after: source});
    const align = () => requestAnimationFrame(() => { if (entry.pane.isConnected && trail.entries.at(-1) === entry) trail.align(entry, true); });
    entry.body.addEventListener('focusin', align);
    entry.body.addEventListener('input', align);
    return entry;
  }

  return {openReferenceBoard, openContentPane, openReviewEditor, openMapBoard, openBoards: (source, restore = false) => openRoomList(trail, source, 'boards', null, restore ? new URLSearchParams(location.search) : null), prepare: (source) => trail.prepare(source), clear: ({preserveUrl = false} = {}) => {
    const url = location.href;
    trail.discardAfter();
    if (preserveUrl) history.replaceState(history.state, '', url);
  }, open: (url, source) => {
    const anchor = document.createElement('a');
    anchor.href = url;
    const entity = entityLink(anchor);
    if (entity) openEntity(trail, entity, source);
  }};
})();
