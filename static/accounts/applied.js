window.NiixyAccountApplied = (() => {
  function initialize(pane, options) {
    let revision = 0;
    let catalog = null;
    const data = JSON.parse(pane.querySelector('#account-applied-data').textContent);
    NiixyUI.bindTabs(pane);
    const current = () => pane.isConnected && !pane.hidden;
    const cleanup = () => options.track.querySelectorAll('[data-applied-editor], .thread-create-module-selector-pane').forEach((item) => {
      if (item.workspaceOwner === pane) item.remove();
    });
    function message(root, text) {
      let error = root.querySelector('[data-applied-error]');
      if (!error) { error = document.createElement('p'); error.dataset.appliedError = ''; error.className = 'room-form-error'; error.setAttribute('role', 'alert'); root.append(error); }
      error.textContent = text;
    }
    async function submit(payload, root) {
      if (root.dataset.appliedPending) return false;
      root.dataset.appliedPending = 'true';
      const generation = revision;
      const buttons = Array.from(root.querySelectorAll('button:not(:disabled)'));
      buttons.forEach(button => { button.disabled = true; });
      root.querySelector('[data-applied-error]')?.remove();
      try {
        const response = await fetch(pane.dataset.appliedChangeUrl, {method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': pane.querySelector('[name="csrfmiddlewaretoken"]').value},
          body: JSON.stringify(payload)});
        const result = await response.json();
        if (!current() || generation !== revision || !root.isConnected) return false;
        if (response.status === 409 && result.confirmation) {
          root.querySelector('[data-merge-preview]')?.remove();
          const preview = document.createElement('section'); preview.dataset.mergePreview = '';
          const heading = document.createElement('p'); heading.textContent = result.error; preview.append(heading);
          result.changes.forEach(change => { const line = document.createElement('p');
            line.textContent = `${change.field}: ${JSON.stringify(change.before)} → ${JSON.stringify(change.after)}`; preview.append(line); });
          const confirm = document.createElement('button'); confirm.type = 'button'; confirm.className = 'button primary';
          confirm.textContent = '確認して保存'; confirm.addEventListener('click', () => submit({...payload, confirmation: result.confirmation}, root));
          preview.append(confirm); root.append(preview);
          return false;
        }
        if (!response.ok) throw new Error(result.error || '操作に失敗しました。');
        cleanup();
        await options.refresh();
        return true;
      } catch (error) {
        if (current() && generation === revision && root.isConnected) message(root, error.message === 'Failed to fetch' ? '通信に失敗しました。入力内容を保持しています。' : error.message);
        return false;
      } finally { delete root.dataset.appliedPending; buttons.forEach(button => { button.disabled = false; }); }
    }
    async function openPicker(button) {
      const kind = button.dataset.addApplied;
      cleanup();
      const generation = ++revision;
      try {
        if (!catalog) {
          const response = await fetch(pane.dataset.appliedDataUrl, {cache: 'no-store'});
          if (!response.ok) throw new Error('一覧を読み込めませんでした。');
          catalog = (await response.json()).catalog;
        }
        if (!current() || generation !== revision) return;
        const applied = kind === 'field' ? data.direct_fields : data.interfaces;
        const items = (kind === 'field' ? catalog.fields : catalog.interfaces).filter(item => !applied.some(existing => existing.definition_id === item.id));
        NiixyRoomForms.moduleSelector(button.closest('form'), kind, items, {
          selectorHost: options.track, owner: pane, currentAccount: options.currentAccount,
          interfaceLabel: 'AccountIF', returnStage: 'applied', setStage: options.setStage,
          onSelect: async (selectedKind, item, editor, actions) => {
            const values = {};
            editor.querySelectorAll('[data-room-definition-id]').forEach(wrapper => {
              const field = selectedKind === 'field' ? item : item.implementations.flatMap(implementation => implementation.fields).find(field => String(field.definition_id) === wrapper.dataset.roomDefinitionId);
              values[field.key] = NiixyRoomForms.fieldValues(wrapper);
            });
            return submit({operation: selectedKind === 'field' ? 'add_field' : 'add_interface', id: item.id, values}, actions);
          },
        });
      } catch (error) { if (current() && generation === revision) message(pane, error.message); }
    }
    function openEditor(item, kind) {
      ++revision; cleanup(); window.NiixyWorkspaceTrail?.prepare(pane);
      const editor = document.createElement('section'); editor.className = 'ui-detail-pane applied-editor-pane';
      editor.dataset.appliedEditor = ''; editor.workspaceOwner = pane;
      const header = document.createElement('header'); header.className = 'ui-pane-header';
      const title = document.createElement('h2'); title.textContent = `${item.name}@${item.creator} v${item.version}/${kind === 'field' ? 'Field' : 'AccountIF'}`;
      const close = document.createElement('button'); close.type = 'button'; close.className = 'icon-button'; close.textContent = '×'; close.setAttribute('aria-label', 'Applied一覧に戻る');
      close.addEventListener('click', () => { ++revision; cleanup(); options.setStage('applied'); }); header.append(title, close);
      const form = document.createElement('form'); form.className = 'applied-editor-form';
      const values = kind === 'field' ? [{binding_id: item.id, value_id: item.value_id, field: item.field, raw_values: item.raw_values, shared_with: item.shared_with}] : item.values;
      values.forEach(value => {
        const control = NiixyRoomForms.fieldControl(value.field, `value_${value.binding_id}`, value.field.required);
        control.dataset.appliedBinding = value.binding_id;
        control.dataset.appliedValue = value.value_id;
        control.addEventListener('input', () => {
          const selected = NiixyRoomForms.fieldValues(control);
          form.querySelectorAll('[data-applied-value]').forEach(other => {
            if (other !== control && other.dataset.appliedValue === control.dataset.appliedValue) NiixyRoomForms.writeFieldValues(other, selected);
          });
        });
        control.dataset.roomSynonymTargets = '[]';
        NiixyRoomForms.writeFieldValues(control, value.raw_values);
        const references = (value.shared_with || []).filter(reference =>
          kind === 'interface' ? !(reference.kind === 'interface' && reference.id === item.id)
            : !(reference.kind === 'field' && reference.definition_id === item.definition_id));
        const names = references.map(reference => references.filter(other => other.name === reference.name).length > 1
          ? `${reference.name}@${reference.creator}/${reference.kind === 'field' ? 'Field' : 'AccountIF'}` : reference.name);
        if (names.length) {
          const hint = document.createElement('p'); hint.className = 'field-help';
          hint.textContent = `${names.join('、')}と共有されています。`; control.append(hint);
        }

        form.append(control);
      });
      form.addEventListener('focusin', event => {
        const input = event.target;
        if (!input.matches('input, textarea, select')) return;
        requestAnimationFrame(() => { if (editor.isConnected && document.activeElement === input) options.setStage('applied-edit'); });
      });
      const save = document.createElement('button'); save.type = 'submit'; save.className = 'button primary'; save.textContent = '保存';
      save.disabled = values.length === 0;
      form.append(save);
      form.addEventListener('submit', event => {
        event.preventDefault();
        const updates = Array.from(form.querySelectorAll('[data-applied-binding]'), wrapper => ({id: Number(wrapper.dataset.appliedBinding), values: NiixyRoomForms.fieldValues(wrapper)}));
        submit({operation: 'edit_values', updates}, form);
      });
      const removeId = kind === 'field' ? item.direct_id : item.id;
      if (removeId) {
        const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'button secondary'; remove.textContent = '取り外す';
        remove.addEventListener('click', () => submit({operation: kind === 'field' ? 'remove_field' : 'remove_interface', id: removeId}, form)); form.append(remove);
      }
      editor.append(header, form); options.track.append(editor); options.setStage('applied-edit');
    }
    const click = event => {
      const add = event.target.closest('[data-add-applied]');
      if (add) { event.preventDefault(); event.stopPropagation(); openPicker(add); }
      const field = event.target.closest('[data-edit-applied-field]');
      if (field) openEditor(data.fields.find(item => item.id === Number(field.dataset.editAppliedField)), 'field');
      const implementation = event.target.closest('[data-edit-applied-interface]');
      if (implementation) openEditor(data.interfaces.find(item => item.id === Number(implementation.dataset.editAppliedInterface)), 'interface');
    };
    pane.addEventListener('click', click);
    pane.addEventListener('focusin', event => {
      const tab = event.target;
      if (!tab.matches('[data-ui-tab]')) return;
      requestAnimationFrame(() => { if (current() && document.activeElement === tab) options.setStage('applied'); });
    });
    pane.querySelector('[data-close-applied]')?.addEventListener('click', options.onClose);
    return {destroy() { ++revision; cleanup(); pane.removeEventListener('click', click); }};
  }
  return {initialize};
})();
