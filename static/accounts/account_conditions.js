window.NiixyAccountConditions = (() => {
  function stableValue(value) {
    if (Array.isArray(value)) return value.map(stableValue);
    if (value && typeof value === 'object') {
      return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stableValue(value[key])]));
    }
    return value;
  }

  function conditionKey(condition) {
    return JSON.stringify({kind: condition.kind, definition: stableValue(condition.definition)});
  }

  function groupKey(group) {
    return group.map(conditionKey).sort().join('|');
  }

  function groupLabel(group) {
    return group.length === 1 ? group[0].label : group.map((condition) => condition.label).join(' AND ');
  }

  function copyGroups(groups = []) {
    return groups.map((group) => group.map((condition) => ({
      id: condition.id,
      kind: condition.kind,
      definition: {...condition.definition},
      label: condition.label,
    })));
  }

  function kindLabel(condition) {
    return {default: 'Default', account: 'Account', account_interface: 'AccountIF', field: 'Field', room: 'Room'}[condition.kind] || condition.kind;
  }

  function summaryButton(label, meta, onClick = null, summaryKind = '') {
    const button = document.createElement('button');
    button.className = 'ui-summary-item';
    button.type = 'button';
    if (summaryKind) button.dataset.summaryKind = summaryKind;
    button.innerHTML = '<span class="ui-summary-item-context"></span><strong class="ui-summary-item-title"></strong><small class="ui-summary-item-updated"></small>';
    button.querySelector('strong').textContent = label;
    button.querySelector('small').textContent = meta;
    if (onClick) button.addEventListener('click', onClick);
    return button;
  }

  function emptyMessage(message, error = false) {
    const empty = document.createElement('p');
    empty.className = error ? 'event-form-error' : 'empty';
    empty.textContent = message;
    return empty;
  }

  function fieldContext(condition, field) {
    const value = condition.definition.value;
    if (!value) return '';
    const renderedValue = field.type === 'boolean' ? (value === 'true' ? 'はい' : 'いいえ') : value;
    const dateLike = ['date', 'datetime'].includes(field.type);
    const operator = {
      contains: '含む', not_contains: '含まない', equals: '一致',
      gte: dateLike ? '以降' : '以上', lte: dateLike ? '以前' : '以下',
    }[condition.definition.operator] || '';
    return [renderedValue, operator].filter(Boolean).join(' ');
  }

  function create(options) {
    const root = options.root || document;
    const track = options.track;
    const historyTemplate = root.querySelector('[data-account-condition-pane-template]')
      || document.querySelector('[data-account-condition-pane-template]');
    const selectorTemplate = root.querySelector('[data-account-selector-pane-template]')
      || document.querySelector('[data-account-selector-pane-template]');
    let historyPane = null;
    let selectorPane = null;
    let historyList = null;
    let selectorTabs = null;
    let selectorContent = null;
    let catalog = [];
    let availableCatalog = [];
    const groupsByTarget = new Map();
    const selectedKeys = new Set();
    let activeTarget = null;
    let returnStage = options.defaultReturnStage || 'list';
    let browserKind = 'default';
    let detailReturnStage = options.selectorStage || 'account-selector';
    let catalogRequestId = 0;

    function clonePane(template) {
      const pane = template?.content.firstElementChild?.cloneNode(true);
      if (!pane) throw new Error('Account condition pane template was not found');
      track.append(pane);
      return pane;
    }

    function removeDetailPane() {
      Array.from(track.querySelectorAll('.account-condition-detail-pane')).at(-1)?.remove();
    }

    function removeSelectorPane() {
      removeDetailPane();
      selectorPane?.remove();
      selectorPane = null;
      selectorTabs = null;
      selectorContent = null;
    }

    function removeConditionPanes() {
      removeSelectorPane();
      historyPane?.remove();
      historyPane = null;
      historyList = null;
      delete track.dataset.accountConditionReturnStage;
    }

    function showHistory() {
      removeSelectorPane();
      if (!historyPane) return;
      renderHistory();
      options.setStage(options.historyStage);
    }

    function mountSelectorPane() {
      removeSelectorPane();
      selectorPane = clonePane(selectorTemplate);
      selectorTabs = selectorPane.querySelector('[data-account-selector-tabs]');
      selectorContent = selectorPane.querySelector('[data-account-selector-content]');
      selectorPane.querySelector('[data-close-account-selector]').addEventListener('click', showHistory);
      selectorPane.querySelectorAll('[data-account-condition-kind]').forEach((button) => button.addEventListener('click', () => {
        browserKind = button.dataset.accountConditionKind;
        renderBrowser();
      }));
    }

    function mountHistoryPane() {
      removeConditionPanes();
      historyPane = clonePane(historyTemplate);
      historyList = historyPane.querySelector('[data-account-condition-list]');
      historyPane.querySelector('[data-close-account-conditions]').addEventListener('click', () => {
        catalogRequestId += 1;
        activeTarget = null;
        resetSelection();
        removeConditionPanes();
        options.setStage(returnStage);
      });
      historyPane.querySelector('[data-browse-account-conditions]').addEventListener('click', () => {
        mountSelectorPane();
        renderBrowser();
        options.setStage(options.selectorStage);
      });
      historyPane.querySelector('[data-add-account-condition-group]').addEventListener('click', () => {
        addGroup(activeTarget, selectedConditions());
        resetSelection();
        renderHistory();
      });
    }

    const kindAllowed = (kind) => !options.conditionKindAllowed || options.conditionKindAllowed(kind, activeTarget);
    const allowed = (condition) => kindAllowed(condition.kind)
      && (!options.conditionAllowed || options.conditionAllowed(condition, activeTarget));
    const csrfToken = () => options.csrfToken();

    async function loadCatalog() {
      const response = await fetch(options.listUrl, {
        cache: 'no-store',
        headers: {'X-Requested-With': 'XMLHttpRequest'},
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Account条件を読み込めませんでした。');
      catalog = copyGroups([result.conditions || []])[0];
      availableCatalog = copyGroups([result.available_conditions || []])[0];
    }

    function builtInDefaultCondition(code) {
      const labels = {
        self: options.authenticated ? `@${options.currentAccount}` : 'Guest',
        guest: 'Guest',
        account: 'NiixyAccount',
        follow: 'Follow',
        follower: 'Follower',
        mute: 'Mute',
        muter: 'Muter',
        love: 'Love',
        lover: 'Lover',
        hate: 'Hate',
        hater: 'Hater',
      };
      if (!labels[code]) return null;
      return {id: `default:${code}`, kind: 'default', definition: {code}, label: labels[code], active: true};
    }

    function targetContainer(target) {
      return root.querySelector(`[data-account-condition-target="${target}"]`);
    }

    function targetInput(target) {
      return root.querySelector(`[data-account-condition-groups-input="${target}"]`);
    }

    function notifyChange(target) {
      const groups = copyGroups(groupsByTarget.get(target) || []);
      const input = targetInput(target);
      if (input) input.value = JSON.stringify(groups);
      options.onChange?.(target, groups);
    }

    function renderTarget(target) {
      const container = targetContainer(target);
      if (!container) return;
      container.replaceChildren();
      const groups = groupsByTarget.get(target) || [];
      groups.forEach((group) => {
        const item = document.createElement('span');
        item.className = 'niimap-selected-account-condition';
        item.title = groupLabel(group);
        const label = document.createElement('span'); label.textContent = groupLabel(group);
        const remove = document.createElement('button');
        remove.type = 'button'; remove.textContent = '×'; remove.setAttribute('aria-label', `${groupLabel(group)}を削除`);
        remove.addEventListener('click', () => {
          groupsByTarget.set(target, groups.filter((candidate) => candidate !== group));
          renderTarget(target); notifyChange(target);
        });
        item.append(label, remove); container.append(item);
      });
    }

    function setGroups(target, groups, notify = false) {
      groupsByTarget.set(target, copyGroups(groups));
      renderTarget(target);
      if (notify) notifyChange(target);
    }

    function initializeTarget(target) {
      const input = targetInput(target);
      if (!input) {
        if (!groupsByTarget.has(target)) setGroups(target, []);
        return;
      }
      try { setGroups(target, JSON.parse(input.value || '[]')); }
      catch { setGroups(target, []); }
    }

    function initializeTargets(scope = root) {
      scope.querySelectorAll?.('[data-account-condition-groups-input]').forEach((input) => {
        initializeTarget(input.dataset.accountConditionGroupsInput);
      });
    }

    function addGroup(target, group) {
      if (!target || !group.length) return;
      const groups = groupsByTarget.get(target) || [];
      const key = groupKey(group);
      if (!groups.some((candidate) => groupKey(candidate) === key)) groups.push(copyGroups([group])[0]);
      groupsByTarget.set(target, groups);
      renderTarget(target); notifyChange(target);
    }

    function selectedConditions() {
      return catalog.filter((condition) => selectedKeys.has(conditionKey(condition)));
    }

    function updateGroupControls() {
      if (!historyPane) return;
      const add = historyPane.querySelector('[data-add-account-condition-group]');
      add.textContent = `追加（${selectedKeys.size}）`;
      add.disabled = selectedKeys.size === 0;
    }

    function resetSelection() {
      selectedKeys.clear(); updateGroupControls();
    }

    async function saveCondition(condition, existing = null) {
      if (!options.authenticated) {
        const local = {...condition, id: `local:${conditionKey(condition)}`, active: true};
        const key = conditionKey(local);
        catalog = [local, ...catalog.filter((item) => conditionKey(item) !== key && item.id !== existing?.id)];
        availableCatalog = [local, ...availableCatalog.filter((item) => conditionKey(item) !== key && item.id !== existing?.id)];
        return local;
      }
      const data = new FormData();
      data.append('csrfmiddlewaretoken', csrfToken());
      data.append('kind', condition.kind);
      data.append('definition', JSON.stringify(condition.definition));
      if (existing) data.append('condition_id', existing.id);
      const response = await fetch(options.saveUrl, {method: 'POST', body: data, headers: {'X-Requested-With': 'XMLHttpRequest'}});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Account条件を保存できませんでした。');
      const key = conditionKey(result.condition);
      catalog = [result.condition, ...catalog.filter((item) => conditionKey(item) !== key && item.id !== existing?.id)];
      availableCatalog = [result.condition, ...availableCatalog.filter((item) => conditionKey(item) !== key && item.id !== existing?.id)];
      return result.condition;
    }

    async function useCondition(condition) {
      try {
        const saved = await saveCondition(condition);
        const key = conditionKey(saved);
        if (selectedKeys.has(key)) selectedKeys.delete(key); else selectedKeys.add(key);
        renderHistory();
      } catch (error) {
        historyList.replaceChildren(emptyMessage(error.message, true));
      }
    }

    async function deleteCondition(condition) {
      const key = conditionKey(condition);
      if (options.authenticated && Number.isInteger(Number(condition.id))) {
        const data = new FormData(); data.append('csrfmiddlewaretoken', csrfToken());
        const response = await fetch(options.deleteUrl.replace('/0/', `/${condition.id}/`), {method: 'POST', body: data, headers: {'X-Requested-With': 'XMLHttpRequest'}});
        if (!response.ok) return;
      }
      catalog = catalog.filter((item) => conditionKey(item) !== key);
      availableCatalog = availableCatalog.map((item) => conditionKey(item) === key ? {...item, active: false} : item);
      selectedKeys.delete(key); renderHistory();
    }

    function renderHistory() {
      if (!historyList || !historyPane) return;
      historyList.replaceChildren();
      const visible = catalog.filter(allowed);
      visible.forEach((condition) => {
        const row = document.createElement('div'); row.className = 'account-condition-summary';
        const field = condition.kind === 'field' ? options.fieldCatalog.find((item) => item.id === Number(condition.definition.field_id)) : null;
        const choose = summaryButton(field ? `${field.name}@${field.creator}` : condition.label, kindLabel(condition), () => useCondition(condition), 'account-condition');
        choose.querySelector('.ui-summary-item-context').textContent = field ? fieldContext(condition, field) : '';
        const key = conditionKey(condition);
        choose.classList.toggle('is-selected', selectedKeys.has(key));
        choose.setAttribute('aria-pressed', selectedKeys.has(key) ? 'true' : 'false');
        const remove = document.createElement('button');
        remove.className = 'account-condition-delete'; remove.type = 'button'; remove.textContent = '×'; remove.setAttribute('aria-label', `${condition.label}を一覧から削除`);
        remove.addEventListener('click', () => deleteCondition(condition));
        row.append(choose);
        if (field) {
          const edit = document.createElement('button'); edit.className = 'account-condition-edit'; edit.type = 'button'; edit.textContent = '編集';
          edit.addEventListener('click', () => { detailReturnStage = options.historyStage; openFieldDetail(field, 'edit', condition); options.setStage(options.historyEditStage); });
          row.append(edit);
        }
        row.append(remove); historyList.append(row);
      });
      if (!visible.length) historyList.append(emptyMessage('利用できるAccount条件の履歴はありません。'));
      updateGroupControls();
    }

    function renderResults(container, conditions, message = '') {
      container.replaceChildren();
      conditions.filter(allowed).forEach((condition) => {
        const summaryKind = {account: 'account', account_interface: 'interface', field: 'field', room: 'room'}[condition.kind] || 'account-condition';
        container.append(summaryButton(condition.label, kindLabel(condition), async () => {
          try { await saveCondition(condition); showHistory(); }
          catch (error) { renderResults(container, [], error.message); }
        }, summaryKind));
      });
      if (!container.children.length || message) container.append(emptyMessage(message || '該当する項目はありません。', Boolean(message)));
    }

    function configureTabs(tabs) {
      Array.from(track.querySelectorAll('.account-condition-detail-pane')).at(-1)?.remove();
      selectorTabs.replaceChildren(); selectorContent.replaceChildren(); selectorTabs.hidden = tabs.length === 0;
      selectorTabs.setAttribute('aria-label', `${kindLabel({kind: browserKind})}の分類`);
      tabs.forEach((tab, index) => {
        const button = document.createElement('button'); button.type = 'button'; button.role = 'tab'; button.dataset.uiTab = tab.key; button.textContent = tab.label;
        button.classList.toggle('is-active', index === 0); button.setAttribute('aria-selected', index === 0 ? 'true' : 'false');
        const panel = document.createElement('section'); panel.className = `ui-tab-panel module-list-panel${index === 0 ? ' is-active' : ''}`; panel.dataset.uiTabPanel = tab.key;
        tab.render(panel); selectorTabs.append(button); selectorContent.append(panel);
      });
      NiixyUI.bindTabs(selectorPane);
    }

    function renderFieldItems(container, fields) {
      container.replaceChildren();
      fields.slice(0, 20).forEach((field) => {
        const updated = new Date(field.updated_at).toLocaleString('ja-JP');
        container.append(summaryButton(`${field.name}@${field.creator} v${field.version}/Field`, `最終更新 ${updated}`, () => openFieldDetail(field), 'field'));
      });
      if (!fields.length) container.append(emptyMessage('該当するFieldはありません。'));
    }

    function fieldEditorControls(field, existing = null) {
      const wrapper = document.createElement('div'); wrapper.className = 'account-field-condition-controls';
      const operator = document.createElement('select'); operator.name = 'operator';
      const value = document.createElement('input'); value.name = 'value';
      let choices;
      if (field.type === 'boolean') { choices = [['', '値を指定しない'], ['true', 'はい'], ['false', 'いいえ']]; value.type = 'hidden'; }
      else if (['integer', 'decimal', 'date', 'datetime'].includes(field.type)) { choices = [['equals', '一致'], ['gte', '以降'], ['lte', '以前']]; value.type = {integer: 'number', decimal: 'number', date: 'date', datetime: 'datetime-local'}[field.type]; if (field.type === 'decimal') value.step = 'any'; }
      else { choices = [['contains', '含む'], ['not_contains', '含まない'], ['equals', '一致']]; value.type = 'text'; }
      choices.forEach(([key, label]) => { const option = document.createElement('option'); option.value = key; option.textContent = label; operator.append(option); });
      if (['single_choice', 'multiple_choice'].includes(field.type)) {
        const select = document.createElement('select'); select.name = 'value'; select.innerHTML = '<option value="">値を指定しない</option>';
        (field.settings.options || []).forEach((item) => { const option = document.createElement('option'); option.value = item; option.textContent = item; select.append(option); });
        wrapper.append(operator, select);
      } else { value.placeholder = '空欄なら実装有無だけを条件にします'; wrapper.append(operator, value); }
      const definition = existing?.definition || {};
      if (field.type === 'boolean') operator.value = definition.value || definition.operator || '';
      else { operator.value = definition.operator || operator.value; wrapper.querySelector('[name="value"]').value = definition.value || ''; }
      return wrapper;
    }

    function renderFieldEditor(body, field, existing = null) {
      const form = document.createElement('form'); form.className = 'account-field-condition-form';
      const heading = document.createElement('h3'); heading.textContent = 'Account条件';
      const controls = fieldEditorControls(field, existing);
      const actions = document.createElement('div'); actions.className = 'interface-detail-actions';
      const submit = document.createElement('button'); submit.className = 'button primary'; submit.type = 'submit'; submit.textContent = existing ? '条件を更新する' : '条件一覧に追加する';
      const error = emptyMessage('', true); error.hidden = true; actions.append(submit); form.append(heading, controls, actions, error);
      form.addEventListener('submit', async (event) => {
        event.preventDefault(); const data = new FormData(form); let operator = data.get('operator');
        const value = data.get('value') || (field.type === 'boolean' ? operator : ''); if (!value) operator = '';
        try { await saveCondition({kind: 'field', definition: {field_id: field.id, operator, value}, label: `${field.name}@${field.creator}`}, existing); showHistory(); }
        catch (exception) { error.textContent = exception.message; error.hidden = false; }
      });
      body.append(form);
    }

    function openFieldDetail(field, mode = 'detail', existing = null) {
      Array.from(track.querySelectorAll('.account-condition-detail-pane')).at(-1)?.remove();
      const pane = document.createElement('aside'); pane.className = 'ui-detail-pane account-condition-detail-pane';
      const header = document.createElement('header'); header.className = 'ui-pane-header ui-detail-pane-header';
      const title = document.createElement('h2'); title.textContent = `${field.name}@${field.creator} v${field.version}/Field`;
      const close = document.createElement('button'); close.className = 'icon-button'; close.type = 'button'; close.textContent = '×'; close.setAttribute('aria-label', 'Field一覧に戻る');
      close.addEventListener('click', () => { pane.remove(); options.setStage(detailReturnStage); }); header.append(title, close);
      const body = document.createElement('div'); body.className = 'account-condition-detail-body'; pane.append(header, body); track.append(pane);
      if (mode === 'edit') renderFieldEditor(body, field, existing);
      else {
        const summary = document.createElement('dl'); summary.className = 'field-definition-summary';
        [['詳細', field.description || ''], ['型', field.type_label]].forEach(([term, value]) => { const row = document.createElement('div'); const dt = document.createElement('dt'); dt.textContent = `${term}:`; const dd = document.createElement('dd'); dd.textContent = value; row.append(dt, dd); summary.append(row); });
        const actions = document.createElement('div'); actions.className = 'interface-detail-actions'; const edit = document.createElement('button'); edit.className = 'button primary'; edit.type = 'button'; edit.textContent = 'Account条件を編集';
        edit.addEventListener('click', () => { detailReturnStage = options.selectorStage; openFieldDetail(field, 'edit'); options.setStage(options.detailStage); }); actions.append(edit); body.append(summary, actions);
      }
      detailReturnStage = mode === 'edit' && existing ? options.historyStage : options.selectorStage;
      options.setStage(mode === 'edit' && existing ? options.historyEditStage : options.detailStage);
    }

    function fieldPanel(panel) {
      const details = document.createElement('details'); details.className = 'field-search-controls'; details.open = true;
      const summary = document.createElement('summary'); summary.textContent = '検索条件';
      const form = document.createElement('form'); form.className = 'field-search-form'; form.innerHTML = '<div class="field-search-row"><label>名前</label><input type="search" name="name" placeholder="Field名@NiixyID"></div><div class="field-search-row"><label>詳細</label><input type="search" name="description"></div><div class="field-search-row"><label>型</label><select name="field_type"><option value="">すべて</option></select></div><div class="field-search-actions"><button class="button" type="submit">検索</button></div>';
      Array.from(new Map(options.fieldCatalog.map((field) => [field.type, field.type_label]))).forEach(([value, label]) => { const option = document.createElement('option'); option.value = value; option.textContent = label; form.elements.field_type.append(option); });
      const results = document.createElement('div'); results.className = 'ui-summary-list';
      form.addEventListener('submit', (event) => { event.preventDefault(); const data = new FormData(form); const names = data.get('name').trim().toLocaleLowerCase().split(/\s+/).filter(Boolean); const descriptions = data.get('description').trim().toLocaleLowerCase().split(/\s+/).filter(Boolean); const type = data.get('field_type'); renderFieldItems(results, options.fieldCatalog.filter((field) => names.every((term) => `${field.name}@${field.creator}`.toLocaleLowerCase().includes(term)) && descriptions.every((term) => (field.description || '').toLocaleLowerCase().includes(term)) && (!type || field.type === type))); if (details.open) summary.click(); });
      details.append(summary, form); panel.append(details, results); renderFieldItems(results, options.fieldCatalog);
    }

    function accountPanel(panel) {
      const form = document.createElement('form'); form.className = 'account-selector-search'; form.innerHTML = '<input name="q" type="search" placeholder="名前@NiixyID"><button class="button primary" type="submit">検索</button>';
      const results = document.createElement('div'); results.className = 'ui-summary-list'; results.append(emptyMessage('名前またはNiixyIDで検索してください。'));
      form.addEventListener('submit', async (event) => { event.preventDefault(); const query = new FormData(form).get('q'); const response = await fetch(`${options.accountSearchUrl}?${new URLSearchParams({q: query})}`); const result = await response.json(); renderResults(results, result.accounts.map((account) => ({kind: 'account', definition: {account_id: account.id}, label: account.label}))); });
      panel.append(form, results);
    }

    function roomPanel(panel, joined = false) {
      const form = document.createElement('form'); form.className = 'account-selector-search'; form.innerHTML = '<input name="q" type="search" placeholder="Room名"><button class="button primary" type="submit">検索</button>';
      const results = document.createElement('div'); results.className = 'ui-summary-list';
      const search = async () => { const query = new FormData(form).get('q'); const response = await fetch(`${options.roomSearchUrl}?${new URLSearchParams({q: query, joined})}`); const result = await response.json(); renderResults(results, result.rooms.map((room) => ({kind: 'room', definition: {room_id: room.id, relation: 'member'}, label: room.label}))); };
      form.addEventListener('submit', (event) => { event.preventDefault(); search(); }); panel.append(form, results); search();
    }

    function placeholder(panel, message) { panel.append(emptyMessage(message)); }

    function renderBrowser() {
      if (!selectorPane) return;
      const kindButtons = Array.from(selectorPane.querySelectorAll('[data-account-condition-kind]'));
      kindButtons.forEach((button) => { button.hidden = !kindAllowed(button.dataset.accountConditionKind); });
      if (!kindAllowed(browserKind)) browserKind = kindButtons.find((button) => !button.hidden)?.dataset.accountConditionKind || 'default';
      kindButtons.forEach((button) => { const active = button.dataset.accountConditionKind === browserKind; button.classList.toggle('is-active', active); button.setAttribute('aria-selected', active ? 'true' : 'false'); });
      if (browserKind === 'default') { configureTabs([]); const results = document.createElement('div'); results.className = 'ui-summary-list module-list-panel is-active'; selectorContent.append(results); renderResults(results, availableCatalog.filter((condition) => condition.kind === 'default')); }
      else if (browserKind === 'account') configureTabs([{key: 'search', label: '検索', render: accountPanel}, ...['Follow', 'Mute', 'Love', 'Hate'].map((label) => ({key: label.toLowerCase(), label, render: (panel) => placeholder(panel, `${label}したAccountはありません。`)}))]);
      else if (browserKind === 'field') configureTabs([{key: 'search', label: '検索', render: fieldPanel}, {key: 'self', label: '自作', render: (panel) => { const results = document.createElement('div'); results.className = 'ui-summary-list'; panel.append(results); renderFieldItems(results, options.fieldCatalog.filter((field) => options.authenticated && field.creator === options.currentAccount)); }}, {key: 'saved', label: '保存', render: (panel) => placeholder(panel, '保存したFieldはありません。')}]);
      else if (browserKind === 'account_interface') configureTabs([{key: 'search', label: '検索', render: (panel) => placeholder(panel, 'AccountIF検索は今後実装予定です。')}, {key: 'self', label: '自作', render: (panel) => placeholder(panel, '自作のAccountIFはありません。')}, {key: 'saved', label: '保存', render: (panel) => placeholder(panel, '保存したAccountIFはありません。')}]);
      else configureTabs([{key: 'search', label: '検索', render: (panel) => roomPanel(panel)}, {key: 'joined', label: '参加', render: (panel) => roomPanel(panel, true)}, {key: 'saved', label: '保存', render: (panel) => placeholder(panel, '保存したRoomはありません。')}]);
    }

    async function open(target, stage = options.defaultReturnStage || 'list') {
      const currentRequest = ++catalogRequestId;
      activeTarget = target;
      returnStage = stage;
      initializeTarget(target);
      mountHistoryPane();
      track.dataset.accountConditionReturnStage = stage;
      resetSelection();
      historyList.replaceChildren(emptyMessage('読み込み中...'));
      options.setStage(options.historyStage);
      try {
        await loadCatalog();
        if (currentRequest !== catalogRequestId || !historyPane) return;
        renderHistory();
      } catch (error) {
        if (currentRequest !== catalogRequestId || !historyList) return;
        historyList.replaceChildren(emptyMessage(error.message, true));
      }
    }

    const handleRootClick = (event) => {
      const trigger = event.target.closest('[data-open-account-conditions]');
      if (trigger && root.contains(trigger)) {
        const stage = trigger.dataset.accountConditionReturnStage
          || options.getReturnStage?.(trigger)
          || options.defaultReturnStage;
        open(trigger.dataset.openAccountConditions, stage);
        return;
      }
    };
    const handleRootReset = (event) => {
      window.setTimeout(() => initializeTargets(event.target), 0);
    };
    root.addEventListener('click', handleRootClick);
    root.addEventListener('reset', handleRootReset);
    const observer = new MutationObserver((mutations) => mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
      if (node.nodeType !== Node.ELEMENT_NODE) return;
      if (node.matches?.('[data-account-condition-groups-input]')) {
        initializeTarget(node.dataset.accountConditionGroupsInput);
      }
      initializeTargets(node);
    })));
    observer.observe(root, {childList: true, subtree: true});
    initializeTargets();

    return {
      open,
      setGroups,
      initialize: initializeTargets,
      getGroups: (target) => copyGroups(groupsByTarget.get(target) || []),
      reset: () => groupsByTarget.clear(),
      defaultCondition: (code) => catalog.find((condition) => condition.kind === 'default' && condition.definition.code === code) || availableCatalog.find((condition) => condition.kind === 'default' && condition.definition.code === code) || builtInDefaultCondition(code),
      destroy() {
        catalogRequestId += 1;
        observer.disconnect();
        root.removeEventListener('click', handleRootClick);
        root.removeEventListener('reset', handleRootReset);
        removeConditionPanes();
      },
    };
  }

  return {create, copyGroups};
})();
