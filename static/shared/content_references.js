window.NiixyContentReferences = (() => {
  const pending = new Map();
  function open(pageUrl, source) {
    const url = new URL(pageUrl, location.origin);
    const pane = new URL(url); pane.pathname += 'pane/';
    if (/\/(board|interface)-lists\//.test(url.pathname)) return NiixyAccountLists.open(pane, url, source, 'List');
    const board = url.pathname.match(/^\/boards\/(\d+)\/$/);
    if (board) return NiixyWorkspaceTrail.openReferenceBoard(board[1], source, url.searchParams.get('thread'), url.searchParams.get('post'));
    const entry = NiixyWorkspaceTrail.openContentPane({title:'読み込み中...', width:'fixed', url, source});
    if (!entry) return;
    fetch(pane, {cache:'no-store', signal:entry.abort.signal}).then(async response => {
      if (!response.ok) throw new Error('コンテンツを読み込めませんでした。');
      const html = await response.text();
      if (!entry.pane.isConnected || entry.abort.signal.aborted) return;
      entry.body.innerHTML = html;
      const summary = source?.querySelector?.('.ui-summary-item-title');
      entry.heading.textContent = entry.body.querySelector('[data-interface-name]')?.dataset.interfaceName || summary?.textContent || '公開Interface';
      NiixyUI.bindTabs(entry.body);
    }).catch(error => {if (entry.pane.isConnected && error.name !== 'AbortError') NiixyUI.showPaneError(entry.body,error.message);});
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
      const response = await fetch(key,{method:'POST',body:data}); const result = await response.json();
      if (!response.ok) throw new Error(result.error || Object.values(result.errors || {}).flat().join(' ') || '評価を保存できませんでした。');
      document.querySelectorAll(`[data-rating-url="${key}"]`).forEach(section => {
        section.dataset.contentSentiment=result.sentiment;
        section.querySelectorAll('[data-content-rate]').forEach(control => {control.setAttribute('aria-pressed',String(control.dataset.contentRate === result.sentiment));});
        ['fav','bad'].forEach(sentiment => {section.querySelector(`[data-content-count="${sentiment}"]`).textContent = `${sentiment} (${result[sentiment+'_count']})`;});
      });
    } catch (error) {if(form.isConnected){alert.textContent=error.message;alert.hidden=false;}}
    finally {pending.delete(key);controls.forEach(control => {control.disabled=false;});}
  });
  const direct = document.querySelector('[data-direct-list-url]');
  if (direct) open(direct.dataset.directListUrl,direct.querySelector('.reference-origin'));
  const board = document.querySelector('[data-direct-board-id]');
  if (board) open(location.href,board.querySelector('.reference-origin'));
  return {open};
})();
