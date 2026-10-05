window.NiixyRoomForms = (() => {
  function fieldControl(field, name, required) {
    const label = document.createElement('label');
    label.className = 'field thread-interface-field thread-field-control';
    label.textContent = `${field.label || field.name}${required ? '（必須）' : ''}`;
    label.dataset.roomDefinitionId = field.definition_id;
    label.dataset.roomSynonymTargets = JSON.stringify(field.synonym_target_ids || []);
    let input;
    if (field.type === 'long_text') {
      input = document.createElement('textarea');
      input.rows = 3;
    } else if (field.type === 'boolean') {
      input = document.createElement('select');
      [['', '選択してください'], ['true', 'はい'], ['false', 'いいえ']].forEach(([value, text]) => input.add(new Option(text, value)));
    } else if (field.type === 'single_choice') {
      input = document.createElement('select');
      input.add(new Option('選択してください', ''));
      (field.settings.options || []).forEach((value) => input.add(new Option(value, value)));
    } else if (field.type === 'multiple_choice') {
      const choices = document.createElement('div');
      choices.className = 'thread-interface-choices';
      (field.settings.options || []).forEach((value) => {
        const choice = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.name = name;
        checkbox.value = value;
        choice.append(checkbox, document.createTextNode(value));
        choices.append(choice);
      });
      label.append(choices);
      label.addEventListener('input', () => synchronizeFields(label.closest('form'), label));
      return label;
    } else {
      input = document.createElement('input');
      input.type = {integer: 'number', decimal: 'number', date: 'date', datetime: 'datetime-local'}[field.type] || 'text';
      if (field.type === 'decimal') input.step = 'any';
    }
    input.name = name;
    input.required = required;
    label.append(input);
    label.addEventListener('input', () => synchronizeFields(label.closest('form'), label));
    return label;
  }

  function fieldValues(wrapper) {
    return Array.from(wrapper.querySelectorAll('input, select, textarea'))
      .filter((control) => control.type !== 'checkbox' || control.checked)
      .map((control) => control.value)
      .filter(Boolean);
  }

  function writeFieldValues(wrapper, values) {
    wrapper.querySelectorAll('input, select, textarea').forEach((control) => {
      if (control.type === 'checkbox') control.checked = values.includes(control.value);
      else control.value = values[0] || '';
    });
  }

  function synchronizeFields(form, source) {
    if (!form || !source) return;
    const wrappers = Array.from(form.querySelectorAll('[data-room-definition-id]'));
    const definitions = new Set(wrappers.map((wrapper) => wrapper.dataset.roomDefinitionId));
    const graph = new Map(Array.from(definitions, (id) => [id, new Set()]));
    wrappers.forEach((wrapper) => {
      const id = wrapper.dataset.roomDefinitionId;
      JSON.parse(wrapper.dataset.roomSynonymTargets).map(String).forEach((target) => {
        if (!definitions.has(target)) return;
        graph.get(id).add(target);
        graph.get(target).add(id);
      });
    });
    const connected = new Set();
    const pending = [source.dataset.roomDefinitionId];
    while (pending.length) {
      const id = pending.pop();
      if (connected.has(id)) continue;
      connected.add(id);
      graph.get(id)?.forEach((target) => pending.push(target));
    }
    const values = fieldValues(source);
    const valueGroup = Array.from(connected).sort((first, second) => Number(first) - Number(second))[0];
    wrappers.filter((wrapper) => connected.has(wrapper.dataset.roomDefinitionId)).forEach((wrapper) => {
      wrapper.dataset.threadValueGroup = valueGroup;
      if (wrapper !== source) writeFieldValues(wrapper, values);
    });
  }

  function removableSummary(title, removeRoot = null) {
    const summary = document.createElement('summary');
    const name = document.createElement('span');
    name.textContent = title;
    summary.append(name);
    if (removeRoot) {
      const remove = document.createElement('span');
      remove.className = 'remove-thread-interface';
      remove.textContent = '×';
      remove.setAttribute('role', 'button');
      remove.setAttribute('tabindex', '0');
      remove.setAttribute('aria-label', `${title}を外す`);
      const removeItem = (event) => {
        event.preventDefault();
        event.stopPropagation();
        removeRoot.remove();
      };
      remove.addEventListener('click', removeItem);
      remove.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') removeItem(event);
      });
      summary.append(remove);
    }
    return summary;
  }

  function directFieldSection(field, removeRoot = null) {
    const section = document.createElement('details');
    section.className = 'thread-interface-implementation thread-direct-field';
    section.open = true;
    section.append(removableSummary(`${field.name}@${field.creator} v${field.version}/Field`, removeRoot));
    const fields = document.createElement('div');
    fields.className = 'thread-interface-implementation-fields';
    fields.append(fieldControl(field, `direct_field_value_${field.key}`, true));
    section.append(fields);
    return section;
  }

  function interfaceSections(item, removeRoot = null) {
    const fragment = document.createDocumentFragment();
    item.implementations.forEach((implementation) => {
      const section = document.createElement('details');
      section.className = 'thread-interface-implementation';
      section.open = true;
      section.append(removableSummary(
        `${implementation.name}@${implementation.creator} v${implementation.version}`,
        implementation.id === item.id ? removeRoot : null,
      ));
      const fields = document.createElement('div');
      fields.className = 'thread-interface-implementation-fields';
      implementation.fields.forEach((field) => {
        fields.append(fieldControl(field, `interface_value_${implementation.id}_${field.key}`, field.required));
      });
      if (!implementation.fields.length) {
        const empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = '入力するFieldはありません。';
        fields.append(empty);
      }
      section.append(fields);
      fragment.append(section);
    });
    return fragment;
  }

  function copyControlValues(source, target) {
    target.querySelectorAll('input, select, textarea').forEach((control) => {
      if (!control.name) return;
      const sources = Array.from(source.querySelectorAll('input, select, textarea'))
        .filter((candidate) => candidate.name === control.name);
      if (control.type === 'checkbox') {
        control.checked = sources.some((candidate) => candidate.value === control.value && candidate.checked);
      } else if (sources[0]) {
        control.value = sources[0].value;
      }
    });
  }

  function addDirectField(form, field, source = null) {
    const container = form.querySelector('[data-thread-selected-direct-fields]');
    let root = container.querySelector(`[data-selected-direct-field="${field.id}"]`);
    if (!root) {
      root = document.createElement('div');
      root.dataset.selectedDirectField = field.id;
      const id = document.createElement('input');
      id.type = 'hidden';
      id.name = 'direct_field_ids';
      id.value = field.id;
      root.append(id, directFieldSection(field, root));
      container.append(root);
    }
    if (source) copyControlValues(source, root);
    root.querySelector('.thread-field-control')?.dispatchEvent(new Event('input'));
  }

  function addInterface(form, item, source = null) {
    const container = form.querySelector('[data-thread-selected-interfaces]');
    let root = container.querySelector(`[data-selected-thread-interface="${item.id}"]`);
    if (!root) {
      root = document.createElement('div');
      root.dataset.selectedThreadInterface = item.id;
      const id = document.createElement('input');
      id.type = 'hidden';
      id.name = 'interface_ids';
      id.value = item.id;
      root.append(id, interfaceSections(item, root));
      container.append(root);
    }
    if (source) copyControlValues(source, root);
    root.querySelector('.thread-field-control')?.dispatchEvent(new Event('input'));
  }

  function summaryItem(item, kind, onClick) {
    const button = document.createElement('button');
    button.className = 'ui-summary-item';
    button.type = 'button';
    const context = document.createElement('span');
    context.className = 'ui-summary-item-context';
    context.setAttribute('aria-hidden', 'true');
    const title = document.createElement('strong');
    title.className = 'ui-summary-item-title';
    title.textContent = `${item.name}@${item.creator} v${item.version}/${kind === 'field' ? 'Field' : item.kind}`;
    const updated = document.createElement('small');
    updated.className = 'ui-summary-item-updated';
    updated.textContent = `最終更新 ${new Date(item.updated_at).toLocaleString('ja-JP')}`;
    button.append(context, title, updated);
    button.addEventListener('click', onClick);
    return button;
  }

  function selectorHeader(title, closeLabel, close) {
    const header = document.createElement('header');
    header.className = 'ui-pane-header ui-list-pane-header';
    const heading = document.createElement('h2');
    heading.textContent = title;
    const button = document.createElement('button');
    button.className = 'icon-button';
    button.type = 'button';
    button.textContent = '×';
    button.setAttribute('aria-label', closeLabel);
    button.addEventListener('click', close);
    header.append(heading, button);
    return header;
  }

  function renderCatalog(panel, items, kind, openDetail) {
    panel.replaceChildren();
    if (!items.length) {
      const empty = document.createElement('p');
      empty.className = 'empty';
      empty.textContent = kind === 'field' ? 'Fieldはありません。' : 'ThreadIFはありません。';
      panel.append(empty);
      return;
    }
    items.forEach((item) => panel.append(summaryItem(item, kind, () => openDetail(item))));
  }

  function moduleSelector(form, kind, catalog, options) {
    const host = options.selectorHost;
    host.querySelectorAll('.thread-create-module-selector-pane').forEach((pane) => pane.remove());
    options.beforeSelectorOpen?.(kind);
    if (!options.beforeSelectorOpen) window.NiixyWorkspaceTrail?.prepare(form);

    const listPane = document.createElement('section');
    listPane.className = `ui-list-pane thread-interface-list-pane thread-create-module-list-pane thread-create-module-selector-pane${kind === 'field' ? ' thread-field-list-pane' : ''}`;
    const detailPane = document.createElement('section');
    detailPane.className = `ui-detail-pane thread-interface-detail-pane thread-create-module-detail-pane thread-create-module-selector-pane${kind === 'field' ? ' thread-field-detail-pane' : ''}`;
    listPane.workspaceOwner = detailPane.workspaceOwner = options.owner || form;
    let detailRequest = 0;
    const close = () => {
      listPane.remove();
      detailPane.remove();
      options.setStage(options.returnStage);
    };
    listPane.append(selectorHeader(`${kind === 'field' ? 'Field' : 'ThreadIF'}一覧`, 'Thread作成に戻る', close));

    const tabs = document.createElement('div');
    tabs.className = 'ui-tabs thread-interface-catalog-tabs';
    tabs.setAttribute('role', 'tablist');
    const body = document.createElement('div');
    body.className = 'thread-interface-catalog';
    const panels = {};
    [['search', '検索'], ['self', '自作'], ['saved', '保存']].forEach(([key, label], index) => {
      const tab = document.createElement('button');
      tab.type = 'button';
      tab.textContent = label;
      tab.dataset.uiTab = key;
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-selected', String(index === 0));
      if (index === 0) tab.classList.add('is-active');
      tabs.append(tab);
      const panel = document.createElement('div');
      panel.className = `ui-tab-panel thread-interface-catalog-list${index === 0 ? ' is-active' : ''}`;
      panel.dataset.uiTabPanel = key;
      panels[key] = panel;
      body.append(panel);
    });
    listPane.append(tabs, body);

    const detailContent = document.createElement('div');
    detailContent.className = 'thread-interface-selector-detail';
    const showList = () => {
      detailRequest += 1;
      options.setStage(`${kind}-list`);
    };
    detailPane.append(selectorHeader(`${kind === 'field' ? 'Field' : 'ThreadIF'}詳細`, '一覧に戻る', showList), detailContent);

    const openDetail = async (item) => {
      const revision = ++detailRequest;
      if (!detailPane.isConnected) host.append(detailPane);
      detailContent.innerHTML = '<p class="ui-pane-loading">読み込み中...</p>';
      options.setStage(`${kind}-detail`);
      try {
        const fragment = await NiixyUI.fetchFragment(item.detail_url);
        if (!detailPane.isConnected || revision !== detailRequest) return;
        detailContent.replaceChildren(fragment.querySelector('.field-definition-detail') || fragment);
      } catch {
        if (!detailPane.isConnected || revision !== detailRequest) return;
        detailContent.innerHTML = `<p class="ui-pane-error">${kind === 'field' ? 'Field' : 'ThreadIF'}の詳細を読み込めませんでした。</p>`;
        return;
      }
      const editor = document.createElement('section');
      editor.className = 'interface-implementation-editor';
      const heading = document.createElement('h3');
      heading.textContent = kind === 'field' ? '入力内容' : '実装内容';
      editor.append(heading);
      if (kind === 'field') editor.append(directFieldSection(item));
      else editor.append(interfaceSections(item));
      const selected = form.querySelector(kind === 'field'
        ? `[data-selected-direct-field="${item.id}"]`
        : `[data-selected-thread-interface="${item.id}"]`);
      if (selected) copyControlValues(selected, editor);
      const actions = document.createElement('div');
      actions.className = 'interface-detail-actions';
      const use = document.createElement('button');
      use.className = 'button primary';
      use.type = 'button';
      use.textContent = selected
        ? '入力内容を反映'
        : (kind === 'field' ? 'このFieldを追加する' : 'このThreadIFを実装する');
      use.addEventListener('click', () => {
        if (kind === 'field') addDirectField(form, item, editor);
        else addInterface(form, item, editor);
        close();
      });
      actions.append(use);
      detailContent.append(editor, actions);
    };

    if (kind === 'field') {
      const search = document.createElement('details');
      search.className = 'thread-field-search';
      search.open = true;
      const summary = document.createElement('summary');
      summary.textContent = '検索条件';
      const searchForm = document.createElement('form');
      searchForm.innerHTML = '<label>名前<input name="name" type="search" placeholder="Field名@NiixyID"></label><label>詳細<input name="description" type="search"></label><label>型<select name="field_type"><option value="">すべて</option></select></label><button class="button" type="submit">検索</button>';
      const type = searchForm.elements.field_type;
      new Map(catalog.map((item) => [item.type, item.type_label])).forEach((label, value) => type.add(new Option(label, value)));
      const results = document.createElement('div');
      results.className = 'ui-summary-list';
      const searchCatalog = () => {
        const name = searchForm.elements.name.value.trim().toLocaleLowerCase();
        const description = searchForm.elements.description.value.trim().toLocaleLowerCase();
        const fieldType = type.value;
        const matches = catalog.filter((item) => (
          (!name || `${item.name}@${item.creator}`.toLocaleLowerCase().includes(name))
          && (!description || item.description.toLocaleLowerCase().includes(description))
          && (!fieldType || item.type === fieldType)
        )).slice(0, 10);
        renderCatalog(results, matches, kind, openDetail);
        search.open = false;
      };
      searchForm.addEventListener('submit', (event) => { event.preventDefault(); searchCatalog(); });
      search.append(summary, searchForm);
      panels.search.append(search, results);
      renderCatalog(results, catalog.slice(0, 10), kind, openDetail);
    } else {
      const input = document.createElement('input');
      input.className = 'niimap-picker-search';
      input.type = 'search';
      input.placeholder = 'ThreadIF名@NiixyID';
      const results = document.createElement('div');
      results.className = 'ui-summary-list';
      const searchCatalog = () => renderCatalog(
        results,
        catalog.filter((item) => !input.value.trim() || `${item.name}@${item.creator}`.toLocaleLowerCase().includes(input.value.trim().toLocaleLowerCase())).slice(0, 10),
        kind,
        openDetail,
      );
      input.addEventListener('input', searchCatalog);
      panels.search.append(input, results);
      searchCatalog();
    }
    renderCatalog(panels.self, catalog.filter((item) => item.creator === options.currentAccount), kind, openDetail);
    panels.saved.innerHTML = `<p class="empty">保存した${kind === 'field' ? 'Field' : 'ThreadIF'}はありません。</p>`;

    host.append(listPane, detailPane);
    NiixyUI.bindTabs(listPane);
    showList();
  }

  function ensurePolicyDialog(dialog = null) {
    if (dialog) return dialog;
    const existing = document.getElementById('thread-create-policy-dialog');
    if (existing) return existing;
    const created = document.createElement('dialog');
    created.id = 'thread-create-policy-dialog';
    created.className = 'thread-rule-dialog';
    created.innerHTML = '<form method="dialog"><div class="thread-rule-dialog-header"><h2>条件を追加</h2><button class="icon-button" value="cancel" aria-label="閉じる">×</button></div><div class="thread-rule-candidates"><button type="button" data-audience="guest">Guest</button><button type="button" data-audience="account">NiixyAccount</button></div></form>';
    document.body.append(created);
    return created;
  }

  function addPolicyRule(rule, audience) {
    const list = rule.querySelector('.thread-rule-list');
    if (list.querySelector(`[data-audience="${audience}"]`)) return;
    const item = document.createElement('span');
    item.className = 'thread-rule-item';
    item.dataset.audience = audience;
    item.append(document.createTextNode(audience === 'guest' ? 'Guest' : 'NiixyAccount'));
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = `${rule.dataset.capability}_${audience}`;
    input.value = 'true';
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = '×';
    remove.setAttribute('aria-label', `${item.textContent}を削除`);
    remove.addEventListener('click', () => item.remove());
    item.append(input, remove);
    list.append(item);
  }

  function initializePolicy(form, suppliedDialog = null) {
    if (form.querySelector('[data-thread-policy-editor]')) return;
    if (form.dataset.threadPolicyReady === 'true') return;
    form.dataset.threadPolicyReady = 'true';
    const dialog = ensurePolicyDialog(suppliedDialog);
    if (dialog.dataset.threadPolicyReady !== 'true') {
      dialog.dataset.threadPolicyReady = 'true';
      dialog.querySelectorAll('[data-audience]').forEach((button) => button.addEventListener('click', () => {
        if (dialog.activeRule) addPolicyRule(dialog.activeRule, button.dataset.audience);
        dialog.close();
      }));
    }
    form.querySelectorAll('.thread-rule').forEach((rule) => {
      rule.dataset.defaultAudiences.split(' ').filter(Boolean).forEach((audience) => addPolicyRule(rule, audience));
      rule.querySelector('.thread-rule-add').addEventListener('click', () => {
        dialog.activeRule = rule;
        dialog.showModal();
      });
    });
  }

  function initializeBoardInformation(root) {
    root.querySelectorAll('.room-board-thread-list:not([data-board-information-ready])').forEach((board) => {
      board.dataset.boardInformationReady = 'true';
      const informationToggle = board.querySelector('[data-board-information-toggle]');
      const createToggle = board.querySelector('[data-board-create-toggle]:not(:disabled)');
      const editToggle = board.querySelector('[data-board-edit-toggle]');
      const informationWindow = board.querySelector('[data-board-information-window]');
      const createWindow = board.querySelector('[data-board-create-window]');
      const informationView = board.querySelector('[data-board-information-view]');
      const editor = board.querySelector('[data-board-editor]');
      const editForm = editor?.querySelector('.room-board-edit');

      const showInformationView = () => {
        if (!editor || !editToggle) return;
        editor.hidden = true;
        informationView.hidden = false;
        editToggle.textContent = '編集';
        editToggle.setAttribute('aria-expanded', 'false');
        editForm?.reset();
      };

      NiixyUI.createExclusivePanels(board, {
        information: {
          toggle: informationToggle,
          panel: informationWindow,
          label: '詳細情報',
          onClose: showInformationView,
        },
        create: {
          toggle: createToggle,
          panel: createWindow,
          label: 'Thread作成',
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

  function initialize(root, fieldCatalog, interfaceCatalog, options = {}) {
    initializeBoardInformation(root);
    root.querySelectorAll('[data-thread-create-form]:not([data-room-form-ready])').forEach((form) => {
      form.dataset.roomFormReady = 'true';
      initializePolicy(form, options.policyDialog);
      form.querySelector('[data-open-thread-field-selector]').addEventListener('click', () => moduleSelector(form, 'field', fieldCatalog, options));
      form.querySelector('[data-open-thread-interface-selector]').addEventListener('click', () => moduleSelector(form, 'interface', interfaceCatalog, options));
    });
  }

  return {initialize, initializePolicy};
})();
