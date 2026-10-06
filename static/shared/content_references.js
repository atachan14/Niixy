window.NiixyContentReferences = (() => {
  const pending = new Map();
  function open(pageUrl, source) {
    const url = new URL(pageUrl, location.origin);
    const pane = new URL(url); pane.pathname += 'pane/';
    if (/\/(board|interface|thread|response)-lists\//.test(url.pathname)) return NiixyAccountLists.open(pane, url, source, 'List');
    const board = url.pathname.match(/^\/boards\/(\d+)\/$/);
    if (board) return NiixyWorkspaceTrail.openReferenceBoard(board[1], source, url.searchParams.get('thread'), url.searchParams.get('post'));
    const conversation = /^\/(threads|responses)\/\d+\/$/.test(url.pathname);
    const entry = NiixyWorkspaceTrail.openContentPane({title:'読み込み中...', width:conversation ? 'remaining' : 'fixed', url, source});
    if (!entry) return;
    fetch(pane, {cache:'no-store', signal:entry.abort.signal}).then(async response => {
      if (!response.ok) throw new Error('コンテンツを読み込めませんでした。');
      const html = await response.text();
      if (!entry.pane.isConnected || entry.abort.signal.aborted) return;
      entry.body.innerHTML = html;
      const summary = source?.querySelector?.('.ui-summary-item-title');
      entry.heading.textContent = entry.body.querySelector('[data-thread-title]')?.dataset.threadTitle || entry.body.querySelector('[data-interface-name]')?.dataset.interfaceName || summary?.textContent || entry.body.querySelector('h2')?.textContent || 'Module詳細';
      NiixyUI.bindTabs(entry.body);
      const targetPost = entry.body.querySelector('[data-target-post]')?.dataset.targetPost;
      if (targetPost) {
        const target = entry.body.querySelector(`[data-thread-post-number="${targetPost}"]`);
        if (target) { target.classList.add('is-response-target'); entry.body.scrollTop += target.getBoundingClientRect().top - entry.body.getBoundingClientRect().top - entry.body.clientHeight / 2; }
      }
      const layout = entry.body.querySelector('[data-layout-detail]');
      if (layout) window.NiixyAccountLayouts?.bind(layout, {inline:true});
    }).catch(error => {if (entry.pane.isConnected && error.name !== 'AbortError') NiixyUI.showPaneError(entry.body,error.message);});
    if (conversation) entry.body.addEventListener('submit', async event => {
      const form = event.target.closest('.thread-reply-form');
      if (!form) return;
      event.preventDefault();
      const result = await NiixyUI.submitThreadReply(form, event.submitter);
      if (!result || !entry.pane.isConnected || entry.abort.signal.aborted) return;
      try { const fragment = await NiixyUI.fetchFragment(pane); if (entry.pane.isConnected && !entry.abort.signal.aborted) entry.body.replaceChildren(fragment); }
      catch (error) { if (entry.pane.isConnected) NiixyUI.showPaneError(entry.body,error.message); }
    });
    return entry;
  }
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-reference-fetch]');
    if (trigger) {event.preventDefault();return NiixyAccountLists.open(trigger.dataset.referenceFetch, location.href, trigger, trigger.dataset.referenceTitle || 'List');}
  });
  document.addEventListener('submit', async event => {
    const form = event.target.closest('[data-content-rating-form]');
    if (!form) return;
    event.preventDefault();
    const root = form.closest('[data-content-feedback]'); const key = root.dataset.ratingUrl;
    if (pending.has(key)) return;
    const button = event.submitter;
    if (!button?.dataset.contentRate || button.disabled) return;
    const desired = root.dataset.contentSentiment === button.dataset.contentRate ? '' : button.dataset.contentRate;
    const data = new FormData(form); data.set('sentiment', desired);
    const controls = [...document.querySelectorAll(`[data-rating-url="${key}"] [data-content-rate]`)];
    controls.forEach(control => {control.disabled=true;}); pending.set(key,true);
    const alert = form.querySelector('.account-list-error'); alert.hidden=true;
    try {
      const response = await fetch(key,{method:'POST',body:data}); const result = await NiixyUI.readJsonResponse(response);
      if (!response.ok) throw new Error(result.error || Object.values(result.errors || {}).flat().join(' ') || '評価を保存できませんでした。');
      document.querySelectorAll(`[data-rating-url="${key}"]`).forEach(section => {
        section.dataset.contentSentiment=result.sentiment;
        section.querySelectorAll('[data-content-rate]').forEach(control => {control.setAttribute('aria-pressed',String(control.dataset.contentRate === result.sentiment));});
        ['fav','bad'].forEach(sentiment => {section.querySelector(`[data-content-count="${sentiment}"]`).textContent = `${sentiment} (${result[sentiment+'_count']})`;});
      });
      const kind = ['thread','response','board'].includes(result.kind) ? result.kind : 'interface';
      document.dispatchEvent(new CustomEvent('niixy:content-rating-changed',{detail:result}));
      refreshIntegrated(kind);
    } catch (error) {if(form.isConnected){alert.textContent=error.message;alert.hidden=false;}}
    finally {pending.delete(key);controls.forEach(control => {control.disabled=false;});}
  });
  function replaceIntegrated(root, fresh, kind) {
    root.dataset.integratedFetch = fresh.dataset.integratedFetch;
    if (kind === 'interface') {
      const state = {type:root.dataset.moduleSelectedType, subtype:root.dataset.moduleSelectedSubtype, collection:root.dataset.moduleSelectedCollection};
      root.querySelector('[data-module-collection-filter]').replaceWith(fresh.querySelector('[data-module-collection-filter]'));
      root.querySelector('.module-list-content').replaceWith(fresh.querySelector('.module-list-content'));
      NiixyUI.bindModuleFilters(root,state);
    } else if (['thread','response'].includes(kind)) {
      const selected = root.querySelector('[data-ui-tab][aria-selected=true]')?.dataset.uiTab || 'created';
      root.replaceChildren(...fresh.childNodes);
      root.dispatchEvent(new CustomEvent('niixy:conversations-refreshed',{bubbles:true}));
      NiixyUI.bindTabs(root, {selected});
    } else {
      const selected = root.querySelector('[data-ui-tab][aria-selected=true]')?.dataset.uiTab || 'self';
      root.querySelector('.room-collection-tabs').replaceWith(fresh.querySelector('.room-collection-tabs'));
      const panels = new Map(Array.from(root.querySelectorAll('[data-ui-tab-panel]'),p=>[p.dataset.uiTabPanel,p]));
      for (const next of fresh.querySelectorAll('[data-ui-tab-panel]')) {
        const old = panels.get(next.dataset.uiTabPanel); panels.delete(next.dataset.uiTabPanel);
        if (!old) { root.append(next); continue; }
        if (!old.dataset.collectionPanelId) { old.replaceWith(next); continue; }
        const refs = old.querySelector('[data-collection-references]');
        if (refs) refs.replaceWith(next.querySelector('[data-collection-references]'));
        const boards = old.querySelector('[data-collection-boards]');
        if (boards) boards.replaceWith(next.querySelector('[data-collection-boards]'));
        const oldName = old.querySelector('.room-collection-information dd'), newName = next.querySelector('.room-collection-information dd');
        if (oldName && newName) oldName.textContent = newName.textContent;
        const name = old.querySelector('.room-collection-edit input[name=name]');
        if (name && name.value === name.defaultValue) name.value = name.defaultValue = newName.textContent;
      }
      panels.forEach(p=>p.remove());
      NiixyUI.bindTabs(root, {selected});
      root.dispatchEvent(new CustomEvent('niixy:collections-refreshed',{bubbles:true}));
    }
  }
  async function refreshIntegrated(kind) {
    for (const root of document.querySelectorAll(`[data-integrated-kind="${kind}"]`)) {
      const generation = (root.integratedGeneration || 0) + 1; root.integratedGeneration = generation;
      try {
        const response = await fetch(root.dataset.integratedFetch, {cache:'no-store'});
        if (!response.ok) throw new Error('List一覧を更新できませんでした。');
        const fresh = new DOMParser().parseFromString(await response.text(),'text/html').querySelector('[data-integrated-kind]');
        if (!root.isConnected || root.integratedGeneration !== generation || !fresh) continue;
        replaceIntegrated(root, fresh, kind);
        root.querySelector('[data-integrated-error]')?.remove();
      } catch (error) {
        if (!root.isConnected) continue;
        let alert = root.querySelector('[data-integrated-error]');
        if (!alert) {alert=document.createElement('p');alert.dataset.integratedError='';alert.className='account-list-error';alert.setAttribute('role','alert');root.prepend(alert);}
        alert.textContent=error.message;
      }
    }
  }
  document.addEventListener('niixy:content-list-changed', event => refreshIntegrated(event.detail.kind));
  const direct = document.querySelector('[data-direct-list-url]');
  if (direct) open(direct.dataset.directListUrl,direct.querySelector('.reference-origin'));
  const conversation = document.querySelector('[data-direct-conversation-url]');
  if (conversation) open(conversation.dataset.directConversationUrl,conversation.querySelector('.reference-origin'));
  const board = document.querySelector('[data-direct-board-id]');
  if (board) open(location.href,board.querySelector('.reference-origin'));
  return {open, replaceIntegrated};
})();
