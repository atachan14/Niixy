(() => {
  // Keep unfinished input in this Workspace, including after Close/Cancel.
  // Nothing is persisted to shared storage or the server before Save.
  const drafts = new Map();
  const mutations = new Map();
  let muteMutation = null;
  const listRequests = new WeakMap();
  const keyFor = section => `${section.dataset.reviewActor}:${section.dataset.reviewKind || 'account'}:${section.dataset.reviewTarget}`;
  const errorText = async response => {
    try {
      const data = await response.json();
      return data.error || Object.values(data.errors || {}).flat().join(' ') || '処理に失敗しました。';
    } catch { return '処理に失敗しました。'; }
  };
  function showError(root, message) {
    const error = root.querySelector('.review-error');
    if (error) { error.textContent = message; error.hidden = false; }
  }
  async function loadSection(section, changes = {}) {
    listRequests.get(section)?.abort();
    const request = new AbortController();
    listRequests.set(section, request);
    const url = new URL(section.dataset.reviewUrl, location.origin);
    const state = {review_filter: section.dataset.reviewFilter, review_expanded: section.dataset.reviewExpanded,
      review_page: section.dataset.reviewPage, ...changes};
    Object.entries(state).forEach(([name, value]) => url.searchParams.set(name, value));
    section.setAttribute('aria-busy', 'true');
    section.querySelector('.review-error').hidden = true;
    try {
      const response = await fetch(url, {cache: 'no-store', signal: request.signal});
      if (!response.ok) throw new Error(await errorText(response));
      const html = await response.text();
      if (!section.isConnected || request.signal.aborted || listRequests.get(section) !== request) return;
      const fresh = new DOMParser().parseFromString(html, 'text/html').querySelector('[data-review-section]');
      if (!fresh) throw new Error('Reviewを読み込めませんでした。');
      section.replaceWith(fresh);
    } catch (error) {
      if (error.name !== 'AbortError' && section.isConnected && listRequests.get(section) === request) showError(section, error.message);
    } finally {
      if (listRequests.get(section) === request) section.removeAttribute('aria-busy');
    }
  }
  async function refreshTarget(source) {
    await Promise.all([...document.querySelectorAll('[data-review-section]')]
      .filter(section => keyFor(section) === keyFor(source))
      .map(section => loadSection(section)));
  }
  async function openEditor(section, sentiment) {
    if (muteMutation) return;
    const entry = window.NiixyWorkspaceTrail?.openReviewEditor(section);
    if (!entry) return;
    const key = keyFor(section);
    const url = new URL(section.dataset.reviewEditorUrl, location.origin);
    url.searchParams.set('sentiment', sentiment);
    try {
      // A write can finish after Close. Reopened editors wait for that write
      // before reading its saved revision, while their own Close still works.
      if (mutations.has(key)) {
        entry.body.firstElementChild.textContent = '保存中...';
        await mutations.get(key);
      }
      if (!entry.pane.isConnected || entry.abort.signal.aborted) return;
      const response = await fetch(url, {cache: 'no-store', signal: entry.abort.signal});
      if (!response.ok) throw new Error(await errorText(response));
      const html = await response.text();
      // A previously requested editor must not enable new input during Mute.
      if (muteMutation) await muteMutation;
      if (!entry.pane.isConnected || entry.abort.signal.aborted) return;
      const form = new DOMParser().parseFromString(html, 'text/html').querySelector('[data-review-form]');
      if (!form) throw new Error('Reviewを読み込めませんでした。');
      entry.body.replaceChildren(form);
      const originalId = form.elements.review_id.value;
      const originalRevision = form.elements.revision.value;
      const originalBody = form.elements.body.value;
      const originalSentiment = section.querySelector('[data-review-edit][aria-pressed="true"]')?.dataset.reviewEdit;
      const previous = drafts.get(key);
      if (previous?.id === originalId && previous?.revision === originalRevision) form.elements.body.value = previous.body;
      const keepInput = () => drafts.set(key, {
        id: originalId, revision: originalRevision, body: form.elements.body.value,
        dirty: form.elements.body.value !== originalBody || (Boolean(originalId) && form.elements.sentiment.value !== originalSentiment),
      });
      keepInput();
      form.addEventListener('input', () => { keepInput(); form.querySelector('.review-error').hidden = true; });
      form.querySelector('[data-review-cancel]').addEventListener('click', () => entry.close.click());
      async function submit(operation, button) {
        if (muteMutation || mutations.has(key)) return;
        const body = form.elements.body;
        if (operation === 'save' && !body.value.trim()) {
          showError(form, '紹介文を入力してください。'); body.focus(); return;
        }
        const pending = NiixyUI.beginPendingAction(button);
        if (!pending) return;
        let resolveMutation;
        mutations.set(key, new Promise(resolve => { resolveMutation = resolve; }));
        keepInput();
        form.querySelector('.review-error').hidden = true;
        const data = new FormData(form);
        const controls = [...form.querySelectorAll('input, textarea, button[type=submit], [data-review-delete]')];
        const disabled = controls.map(control => control.disabled);
        controls.forEach(control => { control.disabled = true; });
        try {
          // Do not abort a write on Close: it may already have reached the server.
          const response = await fetch(operation === 'delete' ? form.dataset.reviewDeleteUrl : form.action,
            {method: 'POST', body: data});
          if (!response.ok) throw new Error(await errorText(response));
          drafts.delete(key);
          if (entry.pane.isConnected) entry.close.click();
          await refreshTarget(section);
          if (section.dataset.reviewKind === 'room') window.dispatchEvent(new CustomEvent('niixy:room-review-changed', {
            detail: {actor: section.dataset.reviewActor, target: section.dataset.reviewTarget},
          }));
        } catch (error) {
          if (form.isConnected) showError(form, error.message || '通信に失敗しました。もう一度お試しください。');
        } finally {
          mutations.delete(key);
          resolveMutation();
          controls.forEach((control, index) => { control.disabled = disabled[index]; });
          pending.restore();
        }
      }
      form.addEventListener('submit', event => { event.preventDefault(); submit('save', form.querySelector('[type=submit]')); });
      form.querySelector('[data-review-delete]')?.addEventListener('click', event => submit('delete', event.currentTarget));
      form.elements.body.focus({preventScroll: true});
    } catch (error) {
      if (entry.pane.isConnected && error.name !== 'AbortError') NiixyUI.showPaneError(entry.body, error.message);
    }
  }
  document.addEventListener('submit', async event => {
    const form = event.target.closest('[data-mute-form]');
    if (!form) return;
    event.preventDefault();
    const section = form.closest('[data-review-section]');
    const button = form.querySelector('[type=submit]');
    const key = keyFor(section);
    if (mutations.size || window.NiixyAccountLists?.isPending()) return;
    // Match the shared Pane's confirmation convention. A reload discards all
    // Workspace drafts, including a Review that was closed or belongs elsewhere.
    if (([...drafts.values()].some(draft => draft.dirty) || window.NiixyAccountLists?.hasDrafts()) &&
        !window.confirm('未保存のReview / AccountList入力があります。入力を破棄してMuteを変更しますか？')) return;
    const pending = NiixyUI.beginPendingAction(button);
    if (!pending) return;
    let resolveMutation;
    mutations.set(key, new Promise(resolve => { resolveMutation = resolve; }));
    muteMutation = mutations.get(key);
    window.NiixyAccountLists?.setLocked(true);
    // Prevent new Review edits after the confirmation and before the reload.
    const controls = [...document.querySelectorAll('[data-review-form] input, [data-review-form] textarea, [data-review-form] [type=submit], [data-review-form] [data-review-delete], [data-review-edit], [data-account-list-form] input, [data-account-list-form] button, [data-account-list-picker-url]')];
    const disabled = controls.map(control => control.disabled);
    controls.forEach(control => { control.disabled = true; });
    let reloadStarted = false;
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form)});
      if (!response.ok) throw new Error(await errorText(response));
      // Re-fetch the current URL so every retained list, Response, and map
      // marker agrees with the new viewer state, including an Unmute.
      location.reload();
      reloadStarted = true;
    } catch (error) {
      if (section.isConnected) showError(section, error.message || '通信に失敗しました。');
    } finally {
      // Success keeps editors locked until navigation actually replaces this
      // document; failure restores their exact state and retained draft.
      if (!reloadStarted) {
        controls.forEach((control, index) => { control.disabled = disabled[index]; });
        window.NiixyAccountLists?.setLocked(false);
        muteMutation = null; mutations.delete(key); resolveMutation(); pending.restore();
      }
    }
  });
  document.addEventListener('click', event => {
    const section = event.target.closest('[data-review-section]');
    if (!section) return;
    const edit = event.target.closest('[data-review-edit]');
    if (edit && !edit.disabled) { openEditor(section, edit.dataset.reviewEdit); return; }
    const tab = event.target.closest('[data-review-tab]');
    if (tab) { loadSection(section, {review_filter: tab.dataset.reviewTab, review_page: '1'}); return; }
    if (event.target.closest('[data-review-expand]')) loadSection(section, {review_expanded: '1', review_page: '1'});
    if (event.target.closest('[data-review-collapse]')) loadSection(section, {review_expanded: '0', review_page: '1'});
    const page = event.target.closest('[data-review-go-page]');
    if (page) loadSection(section, {review_page: page.dataset.reviewGoPage});
  });
})();
