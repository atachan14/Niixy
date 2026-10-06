window.NiixyAccountLists = (() => {
  const entries = new WeakMap();
  let locked = false;
  const lockedControls = new Map();
  function lockControls(root) {
    root.querySelectorAll('input,button').forEach(control => {
      if (!lockedControls.has(control)) lockedControls.set(control, control.disabled);
      control.disabled = true;
    });
  }
  function setLocked(value) {
    locked = value;
    if (value) document.querySelectorAll('.account-list-content').forEach(lockControls);
    else { lockedControls.forEach((disabled, control) => { control.disabled = disabled; }); lockedControls.clear(); }
  }
  const drafts = new Map();
  const mutations = new Map();
  const keyFor = form => `${form.action}:${form.dataset.listOperation}:${form.closest('.account-list-content').dataset.listFetchUrl}`;
  const message = async response => {
    try { const data = await response.json(); return data.error || Object.values(data.errors || {}).flat().join(' ') || '処理に失敗しました。'; }
    catch { return '処理に失敗しました。'; }
  };
  function error(form, text) {
    const target = form.querySelector('.account-list-error');
    if (target) { target.textContent = text; target.hidden = false; }
  }
  function remember(form) {
    const inputs = [...form.querySelectorAll('input:not([name=csrfmiddlewaretoken])')];
    drafts.set(keyFor(form), {values:Object.fromEntries(inputs.map(input => [input.name,input.value])),
      dirty:inputs.some(input => input.type !== 'hidden' && input.value !== input.defaultValue)});
  }
  function showSelectedTab(tab) {
    const list = tab?.closest('[role=tablist]');
    if (!list) return;
    const bounds = list.getBoundingClientRect();
    const selected = tab.getBoundingClientRect();
    // Scroll only the tab row; scrollIntoView can move the whole Workspace.
    if (selected.left < bounds.left) list.scrollLeft += selected.left - bounds.left;
    else if (selected.right > bounds.right) list.scrollLeft += selected.right - bounds.right;
  }
  function bind(root, entry) {
    entries.set(root, entry);
    NiixyUI.bindTabs(root);
    // Replacing a saved List must preserve the selected fixed/List tab without
    // reopening a child Pane as a side effect of refreshing this index.
    const selected = root.querySelector(`[data-ui-tab="${entry.selectedTab || ''}"]`);
    selected?.click();
    showSelectedTab(root.querySelector('[data-ui-tab][aria-selected=true]'));
    root.addEventListener('click', event => {
      const tab = event.target.closest('[data-ui-tab]');
      if (!tab) return;
      entry.selectedTab = tab.dataset.uiTab;
      showSelectedTab(tab);
      if (tab.dataset.listTabUrl) {
        const url = tab.dataset.listTabUrl;
        if (root.dataset.contentListKind === 'interface') window.NiixyContentReferences.open(url, root);
        else openDetail(url, root);
      } else NiixyWorkspaceTrail.prepare(root);
      // Prepare restores the retained parent's URL. Apply the selected People
      // tab afterward so Close/reload cannot revert to the previous child tab.
      if (root.hasAttribute('data-account-lists-index') && !root.dataset.contentListKind) {
        const url=new URL(root.dataset.listPageUrl,location.origin);url.searchParams.set('people_tab',entry.selectedTab);
        entry.url=url.href;history.replaceState(history.state,'',entry.url);
      }
    });
    if (locked) lockControls(root);
    root.querySelectorAll('[data-list-share-url]').forEach(input => { input.value = new URL(input.value, location.origin).href; });
    root.querySelectorAll('[data-account-list-form]').forEach(form => {
      const draft = drafts.get(keyFor(form));
      if (draft) Object.entries(draft.values).forEach(([key,value]) => { if (form.elements[key]) form.elements[key].value = value; });
      if (mutations.has(keyFor(form))) form.querySelectorAll('input,button').forEach(control => { control.disabled = true; });
    });
  }
  function patchSummaries(result) {
    if (!result.list_id) return;
    document.querySelectorAll('[data-account-lists-index]').forEach(root => {
      if ((root.dataset.contentListKind || 'account') !== (result.kind || 'account')) return;
      const tab = root.querySelector(`[data-list-tab-id="${result.list_id}"]`);
      if (!tab) return;
      if (result.deleted) {
        const active = tab.getAttribute('aria-selected') === 'true';
        root.querySelector(`[data-ui-tab-panel="${tab.dataset.uiTab}"]`)?.remove();
        tab.remove();
        if (active) root.querySelector('[data-ui-tab]')?.click();
      } else if (result.name) tab.textContent = result.name;
    });
    document.querySelectorAll(`[data-account-list-id="${result.list_id}"]`).forEach(item => {
      if ((item.dataset.contentListKind || 'account') !== (result.kind || 'account')) return;
      if (result.deleted) { item.remove(); return; }
      if (result.name && item.matches('.account-list-summary')) item.querySelector('span').textContent = result.name;
      const count = item.querySelector('[data-list-count]');
      if (count && result.reference_count !== undefined) count.textContent = result.reference_count;
      const button = item.querySelector('.account-list-pick');
      if (button) {
        if (result.name) button.dataset.listLabel = result.name;
        if (result.reference_count !== undefined) button.dataset.referenceCount = String(result.reference_count);
        button.textContent = `${button.dataset.listLabel} (${button.dataset.referenceCount}) に追加`;
      }
    });
    if (result.deleted) document.querySelectorAll('[data-account-lists-index] .ui-summary-list, [data-account-list-picker] .ui-summary-list').forEach(list => {
      if (!list.children.length) { const empty = document.createElement('p'); empty.className = 'empty'; empty.textContent = 'まだListはありません。'; list.append(empty); }
    });
  }
  async function load(entry, fetchUrl, {updateUrl = false} = {}) {
    entry.request?.abort();
    const request = new AbortController(); entry.request = request;
    const current = () => entry.pane.isConnected && !entry.abort.signal.aborted && !request.signal.aborted && entry.request === request;
    try {
      const response = await fetch(fetchUrl, {cache:'no-store', signal:request.signal});
      if (!current()) return;
      if (!response.ok) throw new Error(await message(response));
      const html = await response.text();
      if (!current()) return;
      const root = new DOMParser().parseFromString(html,'text/html').querySelector('.account-list-content');
      if (!root) throw new Error('Listを読み込めませんでした。');
      entry.body.replaceChildren(root); entry.heading.textContent = root.dataset.listTitle;
      bind(root, entry);
      entry.fetchUrl = String(fetchUrl);
      if (updateUrl && root.dataset.listPageUrl) {
        const pageUrl = new URL(root.dataset.listPageUrl, location.origin);
        const page = new URL(fetchUrl, location.origin).searchParams.get('page');
        if (page) pageUrl.searchParams.set('page', page);
        entry.url = pageUrl.href; history.replaceState(history.state, '', entry.url);
      }
    } catch (exception) {
      if (!current() || exception.name === 'AbortError') return;
      const retained = entry.body.querySelector('.account-list-content');
      if (!retained) return NiixyUI.showPaneError(entry.body, exception.message);
      let alert = retained.querySelector('.account-list-load-error');
      if (!alert) { alert = document.createElement('p'); alert.className = 'account-list-error account-list-load-error'; alert.setAttribute('role','alert'); retained.prepend(alert); }
      alert.textContent = exception.message;
    }
  }
  async function open(fetchUrl, pageUrl, source, title, width = 'fixed') {
    if (locked) return;
    const entry = NiixyWorkspaceTrail.openContentPane({title, width, url:pageUrl, source});
    if (!entry) return;
    // A closed write finishes independently. Reopened forms read its committed
    // result before restoring drafts or enabling new submissions.
    if (mutations.size) await Promise.all([...mutations.values()]);
    if (entry.pane.isConnected && !entry.abort.signal.aborted) await load(entry, fetchUrl);
    return entry;
  }
  function openIndex(account, restore = false) {
    const url = new URL(account.dataset.accountListsUrl, location.origin);
    const pageUrl = new URL(account.dataset.accountPageUrl, location.origin);
    pageUrl.searchParams.set('pane','people');
    if (restore) {
      const page = new URLSearchParams(location.search).get('page');
      if (page) { url.searchParams.set('page',page); pageUrl.searchParams.set('page',page); }
    }
    if (restore && account.closest('.account-page')) history.replaceState(history.state, '', account.dataset.accountPageUrl);
    return open(url,pageUrl,account.querySelector('.account-overview-pane') || account,'People一覧');
  }
  async function mountIndex(account, entry, params) {
    const url = new URL(account.dataset.accountListsUrl, location.origin);
    if (params.get('page')) url.searchParams.set('page',params.get('page'));
    entry.selectedTab = params.get('people_tab') || 'love';
    return load(entry,url);
  }
  document.addEventListener('niixy:content-list-changed', event => {
    if (event.detail.kind) return;
    document.querySelectorAll('[data-account-lists-index]').forEach(root => {
      const entry=entries.get(root);
      if (entry && !entry.abort.signal.aborted) load(entry,entry.fetchUrl);
    });
  });
  function openDetail(pageUrl, source) {
    const page = new URL(pageUrl, location.origin);
    const url = new URL(page); url.pathname += 'pane/';
    return open(url,page,source,'AccountList');
  }
  document.addEventListener('input', event => {
    const form = event.target.closest('[data-account-list-form]');
    if (form) { remember(form); form.querySelector('.account-list-error').hidden = true; }
  });
  document.addEventListener('click', async event => {
    const picker = event.target.closest('[data-account-list-picker-url]');
    if (picker) {
      event.preventDefault();
      return open(picker.dataset.accountListPickerUrl,location.href,picker,'追加先を選択');
    }
    const root = event.target.closest('.account-list-content');
    if (!root) return;
    const entry = entries.get(root);
    const pagination = event.target.closest('[data-summary-page]');
    if (pagination && entry) {
      event.preventDefault();
      root.querySelectorAll('[data-account-list-form]').forEach(remember);
      return load(entry,pagination.href,{updateUrl:true});
    }
    const copy = event.target.closest('[data-copy-list-url]');
    if (copy) {
      const details = copy.closest('.account-list-share');
      const input = details.querySelector('[data-list-share-url]');
      const status = details.querySelector('[data-list-share-status]');
      try { await navigator.clipboard.writeText(input.value); status.textContent = 'URLをコピーしました。'; }
      catch { input.select(); status.textContent = 'URLを選択しました。コピーしてください。'; }
      status.hidden = false;
    }
  });
  document.addEventListener('submit', async event => {
    const form = event.target.closest('[data-account-list-form]');
    if (!form) return;
    event.preventDefault();
    const root = form.closest('.account-list-content');
    const entry = entries.get(root);
    const key = keyFor(form);
    if (!entry || locked || mutations.has(key)) return;
    if (form.dataset.listOperation === 'delete' && !window.confirm(form.dataset.listConfirm || 'このListと参照を削除しますか？元のコンテンツは残ります。')) return;
    const pending = NiixyUI.beginPendingAction(event.submitter || form.querySelector('[type=submit]'));
    if (!pending) return;
    let finished;
    mutations.set(key,new Promise(resolve => { finished = resolve; }));
    remember(form);
    const data = new FormData(form);
    const controls = [...form.querySelectorAll('input,button')];
    const disabled = controls.map(control => control.disabled);
    controls.forEach(control => { control.disabled = true; });
    form.querySelector('.account-list-error').hidden = true;
    try {
      // Writes cannot be cancelled reliably once sent; Close only removes UI.
      const response = await fetch(form.action,{method:'POST',body:data});
      if (!response.ok) throw new Error(await message(response));
      const result = await response.json(); drafts.delete(key);
      mutations.delete(key); finished();
      patchSummaries(result);
      document.dispatchEvent(new CustomEvent('niixy:content-list-changed',{detail:result}));
      if (!entry.pane.isConnected || !form.isConnected) return;
      if (form.dataset.listOperation === 'create') {
        await load(entry,entry.fetchUrl);
        document.querySelectorAll('[data-account-lists-index]').forEach(index => {
          const parent = entries.get(index);
          if (parent && parent !== entry && index.dataset.listFetchUrl === result.index_url) load(parent,parent.fetchUrl);
        });
        if (entry.pane.isConnected && !entry.abort.signal.aborted) await (result.kind === 'interface' ? NiixyContentReferences.open(result.url, entry.pane) : result.kind === 'board' ? NiixyContentReferences.open(result.url, entry.pane) : openDetail(result.url, entry.pane));
      } else if (form.dataset.listOperation === 'delete') {
        entry.close.click();
      } else if (form.dataset.listOperation === 'pick') {
        const status = form.querySelector('[data-list-success]'); status.textContent = '追加しました。'; status.hidden = false;
      } else {
        // Preserve other editable drafts while updating the saved content.
        root.querySelectorAll('[data-account-list-form]').forEach(other => { if (other !== form) remember(other); });
        await load(entry,entry.fetchUrl);

      }
    } catch (exception) { if (form.isConnected) error(form,exception.message); }
    finally {
      mutations.delete(key); finished();
      controls.forEach((control,index) => { control.disabled = disabled[index]; }); pending.restore();
    }
  });
  return {open,openIndex,mountIndex,openDetail,setLocked,hasDrafts:() => [...drafts.values()].some(draft => draft.dirty), isPending:() => mutations.size > 0};
})();
