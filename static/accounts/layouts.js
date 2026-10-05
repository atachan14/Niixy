window.NiixyAccountLayouts = (() => {
  function mountSurfaces(root = document) {
    root.querySelectorAll('[data-account-layout-surface]').forEach(host => {
      if (host.shadowRoot) return;
      const template = host.querySelector('template');
      if (!template) return;
      // Only server-rebuilt, allowlisted markup is accepted by this surface.
      host.attachShadow({mode: 'open'}).append(template.content.cloneNode(true)); template.remove();
    });
  }
  mountSurfaces();
  new MutationObserver(() => mountSurfaces()).observe(document.body, {childList: true, subtree: true});
  function message(root, value, error = false) {
    const notice = root.querySelector('[data-layout-message]');
    if (!notice) return;
    notice.textContent = value; notice.className = error ? 'field-error' : 'field-help';
    notice.setAttribute('role', error ? 'alert' : 'status');
  }
  function display(value) { return value == null ? '未入力' : typeof value === 'boolean' ? value ? 'はい' : 'いいえ' : Array.isArray(value) ? value.join(' / ') : String(value); }
  function definition(field) {
    if (!field.label) return [field.name, field.description].filter(Boolean).join('：');
    const parts = [`${field.label} v${field.version}`, field.type_label, field.required ? '必須' : '任意'];
    if (field.settings?.options?.length) parts.push('選択肢: ' + field.settings.options.join(' / '));
    if (field.description) parts.push(field.description);
    return parts.join('・');
  }
  async function post(url, data, root) {
    const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json',
      'X-CSRFToken': root.querySelector('[name="csrfmiddlewaretoken"]')?.value || document.querySelector('[name="csrfmiddlewaretoken"]')?.value || ''}, body: JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '操作に失敗しました。');
    return result;
  }
  function openLayout(open, url) {
    const match = new URL(url, location.origin).pathname.match(/\/layouts\/(drafts\/)?(\d+)\//);
    const historyUrl = match ? `/mypage/?section=module&type=layout&subtype=account${match[1] ? '&collection=editing&layout_draft=' : '&layout='}${match[2]}` : null;
    return open(url, historyUrl);
  }
  function bindList(list, open, refresh) {
    list.querySelector('[data-layout-create-url]')?.addEventListener('click', async event => {
      const button = event.currentTarget; button.disabled = true;
      try { const result = await post(button.dataset.layoutCreateUrl, {}, document); if (list.isConnected) { await refresh?.(); await openLayout(open, result.url); } }
      catch { const p = document.createElement('p'); p.textContent = 'Draftを作成できませんでした。もう一度お試しください。'; p.className = 'field-error'; button.after(p); }
      finally { button.disabled = false; }
    });
    list.querySelector('[data-layout-search]')?.addEventListener('input', event => {
      const term = event.target.value.toLowerCase();
      event.target.closest('[data-layout-account-panel]').querySelectorAll('.module-summary-entry').forEach(entry => { entry.hidden = !entry.textContent.toLowerCase().includes(term); });
    });
  }
  function bindEditor(root, options) {
    const state = JSON.parse(root.querySelector('#layout-editor-data').textContent);
    const catalog = JSON.parse(root.querySelector('#layout-editor-catalog').textContent);
    const form = root.querySelector('[data-layout-form]');
    let token = null; let previewBody = null; let pending = false;
    const payload = () => ({name: form.elements.name.value, description: form.elements.description.value,
      html: form.elements.html.value, css: form.elements.css.value, requirements: state.requirements, items: state.items});
    const invalidate = () => { token = null; };
    form.addEventListener('input', invalidate); form.addEventListener('change', invalidate);
    form.addEventListener('submit', event => event.preventDefault());
    const candidates = () => {
      const byId = new Map();
      catalog.fields.filter(f => state.requirements.fields.includes(f.id)).forEach(f => byId.set(f.id, f));
      catalog.interfaces.filter(i => state.requirements.interfaces.includes(i.id)).forEach(i => i.fields.forEach(f => byId.set(f.id, f)));
      return Array.from(byId.values());
    };
    function renderItems() {
      const host = root.querySelector('[data-layout-items]'); host.replaceChildren();
      const available = candidates();
      state.items.forEach((item, index) => {
        const row = document.createElement('div'); row.className = 'layout-item-row';
        const select = document.createElement('select'); select.setAttribute('aria-label', 'ItemのField');
        if (!available.some(f => f.id === item.field_id)) { const option = new Option('Requireへ追加してください', String(item.field_id)); select.add(option); }
        available.forEach(f => select.add(new Option(`${f.name}@${f.creator} v${f.version}`, String(f.id)))); select.value = String(item.field_id);
        select.addEventListener('change', () => { item.field_id = Number(select.value); invalidate(); });
        const input = document.createElement('input'); input.value = item.alias; input.maxLength = 32; input.placeholder = '変数名（例 blood）'; input.setAttribute('aria-label', 'Item変数名');
        input.addEventListener('input', () => { item.alias = input.value; invalidate(); });
        const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'icon-button'; remove.textContent = '×'; remove.setAttribute('aria-label', 'Itemを取り外す');
        remove.addEventListener('click', () => { state.items.splice(index, 1); invalidate(); renderItems(); });
        row.append(select, input, remove); host.append(row);
      });
      root.querySelector('[data-layout-add-item]').disabled = available.length === 0 || state.items.length >= 32;
    }
    state.requirements.fields ||= []; state.requirements.interfaces ||= [];
    const picker = root.querySelector('[data-layout-require-picker]');
    ['fields', 'interfaces'].forEach(kind => {
      const heading = document.createElement('h4'); heading.textContent = kind === 'fields' ? 'RequireField' : 'RequireAccountIF'; picker.append(heading);
      catalog[kind].forEach(item => {
        const label = document.createElement('label'); label.className = 'layout-require-choice';
        const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = state.requirements[kind].includes(item.id); checkbox.dataset.requireKind = kind; checkbox.dataset.requireId = item.id;
        checkbox.disabled = item.usable === false && !checkbox.checked;
        checkbox.addEventListener('change', () => { state.requirements[kind] = Array.from(picker.querySelectorAll(`input[data-require-kind="${kind}"]:checked`), c => Number(c.dataset.requireId)); checkbox.disabled = item.usable === false && !checkbox.checked; invalidate(); renderItems(); });
        label.append(checkbox, document.createTextNode(`${item.name}@${item.creator} v${item.version}${item.usable === false ? '（最新版への対応が必要）' : ''}`)); picker.append(label);
      });
    });
    root.querySelector('[data-layout-require-search]').addEventListener('input', event => {
      const term = event.target.value.toLowerCase(); picker.querySelectorAll('.layout-require-choice').forEach(label => { label.hidden = !label.textContent.toLowerCase().includes(term) && !label.querySelector('input').checked; });
    });
    renderItems();
    root.querySelector('[data-layout-add-item]').addEventListener('click', () => {
      const first = candidates()[0]; if (!first || state.items.length >= 32) return;
      state.items.push({alias: 'field' + (state.items.length + 1), field_id: first.id}); invalidate(); renderItems();
    });
    function tab(name) {
      root.querySelectorAll('[data-layout-tab]').forEach(button => { const active = button.dataset.layoutTab === name; button.classList.toggle('is-active', active); button.setAttribute('aria-selected', String(active)); });
      root.querySelectorAll('[data-layout-panel]').forEach(panel => { panel.hidden = panel.dataset.layoutPanel !== name; });
    }
    async function action(operation) {
      if (pending) return;
      if (operation === 'publish' && (!token || previewBody !== JSON.stringify(payload()))) { tab('preview'); message(root, 'プレビューを更新し、内容を確認してから公開してください。', true); return; }
      pending = true; const buttons = Array.from(root.querySelectorAll('.layout-actions button, [data-layout-preview]')); buttons.forEach(b => b.disabled = true);
      const submitted = payload();
      try {
        const result = await post(root.dataset.saveUrl, {operation, layout: submitted, token}, root);
        if (!root.isConnected) return;
        if (operation === 'preview') {
          if (JSON.stringify(payload()) !== JSON.stringify(submitted)) { message(root, '入力が変わりました。プレビューを再更新してください。', true); return; }
          const surface = root.querySelector('[data-layout-preview-surface]'); surface.innerHTML = result.document; mountSurfaces(surface); token = result.token; previewBody = JSON.stringify(submitted);
          message(root, 'プレビューを更新しました。内容を確認して公開できます。');
        } else if (result.published) { await options.refresh(); await openLayout(options.open, result.url + '?manage=1'); }
        else message(root, 'Draftを保存しました。');
      } catch (error) { if (root.isConnected) message(root, error.message === 'Failed to fetch' ? '通信に失敗しました。入力内容を保持しています。' : error.message, true); }
      finally { pending = false; buttons.forEach(b => b.disabled = false); }
    }
    root.querySelectorAll('[data-layout-tab]').forEach(button => button.addEventListener('click', () => { tab(button.dataset.layoutTab); if (button.dataset.layoutTab === 'preview') action('preview'); }));
    root.querySelector('[data-layout-preview]').addEventListener('click', () => action('preview'));
    root.querySelector('[data-layout-save]').addEventListener('click', () => action('save'));
    root.querySelector('[data-layout-publish]').addEventListener('click', () => action('publish'));
    root.querySelector('[data-layout-discard]').addEventListener('click', async () => { try { await post(root.dataset.discardUrl, {}, root); if (root.isConnected) options.refresh(); } catch (error) { message(root, error.message, true); } });
  }
  async function openRequirement(root, button, options) {
    const host = options.inline ? root : root.parentElement;
    host.querySelector('[data-layout-requirement]')?.remove();
    try {
      const pane = await NiixyUI.fetchFragment(button.dataset.layoutRequireUrl + (root.dataset.applyUrl ? '?manage=1' : ''));
      if (!root.isConnected) return;
      pane.dataset.mypagePane = 'add-field-detail'; host.append(pane);
      if (!options.inline) options.stage?.('add-detail');
      pane.querySelector('[data-layout-require-close]').addEventListener('click', () => { pane.remove(); if (!options.inline) options.stage?.('detail'); });
      const data = JSON.parse(pane.querySelector('#layout-requirement-data').textContent);
      const form = pane.querySelector('[data-layout-require-form]');
      if (!form) return;
      if (!data.catalog) { form.querySelector('button[type="submit"]').disabled = true; message(form, 'この定義は最新版へ対応していません。現在は適用できません。', true); return; }
      const fields = data.kind === 'field' ? [data.catalog] : data.catalog.implementations.flatMap(i => i.fields);
      fields.forEach(field => {
        const control = NiixyRoomForms.fieldControl(field, `layout_require_${field.definition_id}`, field.required);
        control.dataset.layoutFieldKey = field.key;
        const existing = data.applied.fields.find(f => f.definition_id === field.definition_id);
        NiixyRoomForms.writeFieldValues(control, existing?.raw_values || []);
        form.querySelector('[data-layout-require-inputs]').append(control);
      });
      let pending = false;
      async function submit(confirmation = null) {
        if (pending) return; pending = true;
        const supplied = {}; form.querySelectorAll('[data-layout-field-key]').forEach(c => { supplied[c.dataset.layoutFieldKey] = NiixyRoomForms.fieldValues(c); });
        const existing = data.kind === 'field' ? data.applied.fields.find(f => f.definition_id === data.id) : data.applied.interfaces.find(i => i.definition_id === data.id);
        const payload = data.kind === 'field' && existing ? {operation: 'edit_value', id: existing.id, values: supplied[data.catalog.key]}
          : {operation: data.kind === 'field' ? 'add_field' : existing ? 'update_interface' : 'add_interface', id: existing?.id || data.id, values: supplied};
        if (confirmation) payload.confirmation = confirmation;
        const save = form.querySelector('[type="submit"]'); save.disabled = true;
        try {
          const result = await post(form.dataset.changeUrl, payload, form);
          if (!pane.isConnected) return;
          if (result.needs_confirmation) {
            form.querySelector('[data-layout-confirmation]')?.remove();
            const section = document.createElement('section'); section.dataset.layoutConfirmation = '';
            const notice = document.createElement('p'); notice.textContent = result.error; section.append(notice);
            result.changes.forEach(change => {
              const p = document.createElement('p');
              p.textContent = `${change.field}: ${['field_version', 'interface_version'].includes(change.kind) ? `v${change.before} → v${change.after}` : `${display(change.before)} → ${display(change.after)}`}`; section.append(p);
              if (change.before_definition) { const detail = document.createElement('p'); detail.textContent = `定義: ${definition(change.before_definition)} → ${definition(change.after_definition)}`; section.append(detail); }
              if (change.before_fields) { const detail = document.createElement('p'); detail.textContent = `Field構成: ${change.before_fields.map(definition).join(' / ') || 'なし'} → ${change.after_fields.map(definition).join(' / ') || 'なし'}`; section.append(detail); }
              if (Object.hasOwn(change, 'value')) { const detail = document.createElement('p'); detail.textContent = '現在値: ' + display(change.value); section.append(detail); }
            });
            const confirm = document.createElement('button'); confirm.type = 'button'; confirm.className = 'button'; confirm.textContent = '確認して保存'; confirm.addEventListener('click', () => submit(result.confirmation)); section.append(confirm); form.append(section);
          } else { await openLayout(options.open, `/mypage/interfaces/layouts/${root.dataset.layoutId}/?manage=1`); }
        } catch (error) { if (pane.isConnected) message(form, error.message, true); }
        finally { pending = false; save.disabled = false; }
      }
      form.addEventListener('submit', event => { event.preventDefault(); submit(); });
    } catch (error) { message(root, '定義を読み込めませんでした。もう一度お試しください。', true); }
  }
  function bind(root, options) {
    if (root.hasAttribute('data-layout-editor')) { bindEditor(root, options); return; }
    if (!root.hasAttribute('data-layout-detail')) return;
    root.querySelectorAll('[data-layout-require-url]').forEach(button => button.addEventListener('click', () => openRequirement(root, button, options)));
    root.querySelector('[data-layout-edit]')?.addEventListener('click', async () => { try { const result = await post(root.dataset.editUrl, {}, root); if (root.isConnected) openLayout(options.open, result.url); } catch (error) { message(root, error.message, true); } });
    ['apply', 'remove'].forEach(operation => root.querySelector(`[data-layout-${operation}]`)?.addEventListener('click', async event => {
      const button = event.currentTarget; button.disabled = true;
      try { await post(root.dataset.applyUrl, {operation, id: Number(root.dataset.layoutId), version: Number(root.dataset.layoutVersion)}, root); if (root.isConnected) { message(root, operation === 'apply' ? 'Profileに適用しました。' : 'Layoutを取り外しました。Field/AccountIFと値は保持しています。'); root.querySelector('[data-layout-remove]').disabled = operation === 'remove'; } }
      catch (error) { if (root.isConnected) message(root, error.message, true); }
      finally { if (operation === 'apply') button.disabled = false; }
    }));
  }
  return {bind, bindList};
})();
