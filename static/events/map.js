const markers = JSON.parse(document.getElementById('thread-markers').textContent);
const interfaceCatalog = JSON.parse(document.getElementById('thread-interface-catalog-data').textContent);
const fieldCatalog = JSON.parse(document.getElementById('thread-field-catalog-data').textContent);
let accountConditionCatalog = JSON.parse(document.getElementById('account-condition-catalog-data').textContent);
const availableAccountConditionCatalog = JSON.parse(document.getElementById('available-account-condition-catalog-data').textContent);
const savedSearchState = JSON.parse(document.getElementById('niimap-search-state-data').textContent);
const workspace = document.querySelector('.thread-workspace');
const threadStack = NiixyUI.createPaneStack(workspace, {
  list: null,
  detail: 'is-detail-open',
  'interface-list': 'is-interface-list-open',
  'interface-detail': 'is-interface-detail-open',
  'field-list': 'is-field-list-open',
  'field-detail': 'is-field-detail-open',
  'account-conditions': 'is-account-conditions-open',
  'account-selector': 'is-account-selector-open',
  'account-condition-detail': 'is-account-condition-detail-open',
  'account-condition-history-edit': 'is-account-condition-history-edit-open',
});
const threadMotion = NiixyUI.createWorkspace(workspace, {
  list: {root: true},
  detail: {target: '.thread-detail-pane'},
  'interface-list': {target: '.thread-interface-list-pane:not(.thread-field-list-pane)'},
  'interface-detail': {target: '.thread-interface-detail-pane:not(.thread-field-detail-pane)'},
  'field-list': {target: '.thread-field-list-pane'},
  'field-detail': {target: '.thread-field-detail-pane'},
  'account-conditions': {target: '.account-condition-pane'},
  'account-selector': {target: '.account-selector-pane'},
  'account-condition-detail': {target: '.account-condition-detail-pane'},
  'account-condition-history-edit': {target: '.account-condition-detail-pane'},
}, {track: document.querySelector('.thread-track')});
const list = document.getElementById('thread-list');
const createForm = document.getElementById('thread-create-form');
const searchControls = document.getElementById('niimap-search-controls');
const searchForm = document.getElementById('niimap-search-form');
const createControls = document.getElementById('niimap-create-controls');
const openThreadCreate = document.getElementById('open-thread-create');
const ruleDialog = document.getElementById('thread-rule-dialog');
const map = new geolonia.Map('#map');
function setThreadStage(stage) {
  threadStack.set(stage);
  threadMotion.set(stage);
  window.setTimeout(() => map.resize(), 260);
}
const markerById = new Map();
const resumeStorageKey = 'niixy:resume:niimap';
let draftMarker;
let creating = false;
let activeRuleCapability;
const selectedInterfaceIds = new Set();
const selectedDirectFieldIds = new Set();
const interfaceValueStore = new Map();
let previewInterfaceId = null;
let previewRequestId = 0;
let previewFieldId = null;
let previewFieldRequestId = 0;
let selectorPurpose = 'create';
let selectorReturnStage = 'detail';
let searchSelectionTarget = null;
let appliedSearchIds = null;
let appliedSearchOrder = null;
let selectedSortField = null;
let activeAccountConditionTarget = null;
let accountConditionGroupMode = false;
const selectedAccountConditionIds = new Set();
const accountConditionGroups = new Map();
let accountConditionBrowserKind = 'default';
let accountConditionDetailReturnStage = 'account-selector';

function stableConditionValue(value) {
  if (Array.isArray(value)) return value.map(stableConditionValue);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stableConditionValue(value[key])]));
  }
  return value;
}
function accountConditionKey(condition) {
  return JSON.stringify({kind: condition.kind, definition: stableConditionValue(condition.definition)});
}
function accountGroupKey(group) {
  return group.map(accountConditionKey).sort().join('|');
}
function accountGroupLabel(group) {
  return group.length === 1 ? group[0].label : group.map((condition) => condition.label).join(' AND ');
}
function copyAccountGroups(groups = []) {
  return groups.map((group) => group.map((condition) => ({
    id: condition.id,
    kind: condition.kind,
    definition: {...condition.definition},
    label: condition.label,
  })));
}

function ensureInterfaceSelectorPanes() {
  if (document.getElementById('thread-interface-selector')) return;
  previewFieldRequestId += 1;
  previewFieldId = null;
  document.getElementById('thread-field-selector')?.remove();
  document.querySelector('.thread-field-detail-pane')?.remove();
  document.querySelector('.thread-track').append(document.getElementById('thread-interface-selector-template').content.cloneNode(true));
  NiixyUI.bindTabs(document.querySelector('.thread-interface-catalog'));
  document.getElementById('close-thread-interface-selector').addEventListener('click', closeInterfaceSelector);
  document.getElementById('back-thread-interface-selector').addEventListener('click', () => {
    setThreadStage('interface-list');
    synchronizeThreadFieldControls();
  });
  document.querySelectorAll('[data-select-thread-interface]').forEach((button) => button.addEventListener('click', () => renderInterfacePreview(Number(button.dataset.selectThreadInterface))));
}

function ensureFieldSelectorPanes() {
  if (document.getElementById('thread-field-selector')) return;
  previewRequestId += 1;
  previewInterfaceId = null;
  document.getElementById('thread-interface-selector')?.remove();
  document.querySelector('.thread-interface-detail-pane:not(.thread-field-detail-pane)')?.remove();
  document.querySelector('.thread-track').append(document.getElementById('thread-field-selector-template').content.cloneNode(true));
  const catalog = document.querySelector('#thread-field-selector .thread-interface-catalog');
  NiixyUI.bindTabs(catalog);
  document.getElementById('close-thread-field-selector').addEventListener('click', closeFieldSelector);
  document.getElementById('back-thread-field-selector').addEventListener('click', () => {
    setThreadStage('field-list');
    synchronizeThreadFieldControls();
  });
  document.querySelectorAll('[data-select-thread-field]').forEach((button) => button.addEventListener('click', () => renderFieldPreview(Number(button.dataset.selectThreadField))));
  document.getElementById('thread-field-search-form').addEventListener('submit', (event) => {
    event.preventDefault();
    renderFieldSearchResults(new FormData(event.currentTarget));
    const details = event.currentTarget.closest('details');
    if (details?.open) details.querySelector(':scope > summary')?.click();
  });
  renderFieldSearchResults(new FormData(document.getElementById('thread-field-search-form')));
}

function consumeResumeState() {
  const stored = sessionStorage.getItem(resumeStorageKey);
  sessionStorage.removeItem(resumeStorageKey);
  sessionStorage.removeItem('niimap:open-thread');
  sessionStorage.removeItem('niimap:animate-thread');
  sessionStorage.removeItem('niimap:map-view');
  if (!stored) return null;
  try { return JSON.parse(stored); } catch { return null; }
}
function threadIdFromUrl() {
  const value = new URLSearchParams(location.search).get('thread');
  return /^\d+$/.test(value || '') ? value : null;
}
const resumeState = consumeResumeState();
const initialThreadId = threadIdFromUrl();
const activeResumeState = initialThreadId && String(resumeState?.threadId) === initialThreadId ? resumeState : null;
const animateInitialThread = Boolean(activeResumeState?.animate);
const initialThreadPane = initialThreadId && document.querySelector(`[data-thread-detail-pane="${initialThreadId}"]`);
const detailTitle = document.getElementById('thread-detail-title');
if (initialThreadPane) {
  if (!animateInitialThread) {
    setThreadStage('detail');
    workspace.classList.add('is-restoring-detail');
  }
  initialThreadPane.hidden = false;
  detailTitle.textContent = `${initialThreadPane.dataset.threadTitle} (${initialThreadPane.dataset.threadPostCount})`;
} else {
  const url = new URL(location.href);
  url.searchParams.delete('thread');
  history.replaceState({}, '', url);
}
document.documentElement.classList.remove('has-restored-thread-detail');
if (initialThreadPane) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (animateInitialThread) setThreadStage('detail');
    else workspace.classList.remove('is-restoring-detail');
  }));
}

document.getElementById('niimap-home-link')?.addEventListener('click', () => {
  sessionStorage.removeItem(resumeStorageKey);
});

function csrf(form) { return new FormData(form); }
function saveResumeState(threadId, animate = false) {
  const center = map.getCenter();
  sessionStorage.setItem(resumeStorageKey, JSON.stringify({
    threadId: String(threadId),
    animate,
    mapView: {latitude: center.lat, longitude: center.lng, zoom: map.getZoom()},
  }));
}
function restoreMapView() {
  const view = activeResumeState?.mapView;
  if (!view || ![view.latitude, view.longitude, view.zoom].every(Number.isFinite)) return false;
  map.jumpTo({center: [view.longitude, view.latitude], zoom: view.zoom});
  return true;
}
function mapViewFromUrl() {
  const params = new URLSearchParams(location.search);
  if (!params.has('latitude') || !params.has('longitude')) return null;
  const latitude = Number(params.get('latitude'));
  const longitude = Number(params.get('longitude'));
  const requestedZoom = Number(params.get('zoom'));
  if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) return null;
  if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) return null;
  const zoom = Number.isFinite(requestedZoom) && requestedZoom >= 0 && requestedZoom <= 22 ? requestedZoom : 15;
  return {latitude, longitude, zoom};
}
function focusMapFromUrl(animate = false) {
  const view = mapViewFromUrl();
  if (!view) return false;
  const options = {center: [view.longitude, view.latitude], zoom: view.zoom};
  if (animate) map.easeTo({...options, duration: 700, essential: true});
  else map.jumpTo(options);
  return true;
}
function addRule(capability, audience) {
  const list = document.querySelector(`.thread-rule[data-capability="${capability}"] .thread-rule-list`);
  if (list.querySelector(`[data-audience="${audience}"]`)) return;
  const item = document.createElement('span');
  item.className = 'thread-rule-item';
  item.dataset.audience = audience;
  item.textContent = audience === 'guest' ? 'Guest' : 'NiixyAccount';
  const remove = document.createElement('button');
  remove.type = 'button'; remove.textContent = '×'; remove.setAttribute('aria-label', `${item.textContent}を削除`);
  remove.addEventListener('click', () => item.remove());
  item.append(remove); list.append(item);
}
document.querySelectorAll('.thread-rule').forEach((rule) => {
  const capability = rule.dataset.capability;
  addRule(capability, 'guest'); addRule(capability, 'account');
  rule.querySelector('.thread-rule-add').addEventListener('click', () => { activeRuleCapability = capability; ruleDialog.showModal(); });
});
ruleDialog.querySelectorAll('[data-audience]').forEach((button) => button.addEventListener('click', () => {
  addRule(activeRuleCapability, button.dataset.audience); ruleDialog.close();
}));
function createFormData() {
  const data = csrf(createForm);
  document.querySelectorAll('.thread-rule').forEach((rule) => {
    rule.querySelectorAll('.thread-rule-item').forEach((item) => data.append(`${rule.dataset.capability}_${item.dataset.audience}`, 'true'));
  });
  return data;
}

function interfaceValueKey(interfaceId, fieldKey) { return `${interfaceId}:${fieldKey}`; }
function inputName(interfaceId, fieldKey) { return `interface_value_${interfaceId}_${fieldKey}`; }
function directValueKey(fieldKey) { return `direct:${fieldKey}`; }
function directInputName(fieldKey) { return `direct_field_value_${fieldKey}`; }
function makeFieldControl(implementation, field, {direct = false} = {}) {
  const required = direct || field.required;
  const key = direct ? directValueKey(field.key) : interfaceValueKey(implementation.id, field.key);
  const saved = interfaceValueStore.get(key) || [];
  const wrapper = document.createElement('div');
  wrapper.className = 'field thread-interface-field thread-field-control';
  wrapper.dataset.valueKey = key;
  wrapper.dataset.definitionId = String(field.definition_id);
  wrapper.dataset.synonymTargets = JSON.stringify(field.synonym_target_ids || []);
  const label = document.createElement('label');
  label.textContent = `${field.label || field.name}${required ? '（必須）' : ''}`;
  wrapper.append(label);
  const name = direct ? directInputName(field.key) : inputName(implementation.id, field.key);
  if (field.type === 'long_text') {
    const input = document.createElement('textarea'); input.name = name; input.rows = 4; input.value = saved[0] || ''; input.required = required; wrapper.append(input);
  } else if (field.type === 'boolean') {
    const input = document.createElement('select'); input.name = name; input.required = required;
    [['', '選択してください'], ['true', 'はい'], ['false', 'いいえ']].forEach(([value, text]) => { const option = document.createElement('option'); option.value = value; option.textContent = text; option.selected = saved[0] === value; input.append(option); }); wrapper.append(input);
  } else if (field.type === 'single_choice') {
    const input = document.createElement('select'); input.name = name; input.required = required;
    const empty = document.createElement('option'); empty.value = ''; empty.textContent = '選択してください'; input.append(empty);
    field.settings.options.forEach((value) => { const option = document.createElement('option'); option.value = value; option.textContent = value; option.selected = saved[0] === value; input.append(option); }); wrapper.append(input);
  } else if (field.type === 'multiple_choice') {
    const choices = document.createElement('div'); choices.className = 'thread-interface-choices';
    field.settings.options.forEach((value) => { const choice = document.createElement('label'); const input = document.createElement('input'); input.type = 'checkbox'; input.name = name; input.value = value; input.checked = saved.includes(value); choice.append(input, document.createTextNode(value)); choices.append(choice); }); wrapper.append(choices);
  } else {
    const input = document.createElement('input'); input.name = name; input.required = required; input.value = saved[0] || '';
    input.type = {integer: 'number', decimal: 'number', date: 'date', datetime: 'datetime-local'}[field.type] || 'text';
    if (field.type === 'decimal') input.step = 'any'; wrapper.append(input);
  }
  wrapper.addEventListener('input', () => {
    synchronizeThreadFieldControls(wrapper);
  });
  return wrapper;
}
function readThreadFieldValues(wrapper) {
  return Array.from(wrapper.querySelectorAll('input, select, textarea'))
    .filter((control) => control.type !== 'checkbox' || control.checked)
    .map((control) => control.value)
    .filter((value) => value !== '');
}
function writeThreadFieldValues(wrapper, values) {
  wrapper.querySelectorAll('input, select, textarea').forEach((control) => {
    if (control.type === 'checkbox') control.checked = values.includes(control.value);
    else control.value = values[0] || '';
  });
  interfaceValueStore.set(wrapper.dataset.valueKey, values);
}
function synchronizeThreadFieldControls(source = null) {
  const selectedWrappers = Array.from(
    document.querySelectorAll('#selected-direct-fields .thread-field-control, #selected-thread-interfaces .thread-field-control'),
  );
  const previewSelector = threadStack.is('interface-detail')
    ? '#thread-interface-selector-detail .thread-field-control'
    : threadStack.is('field-detail') ? '#thread-field-selector-detail .thread-field-control' : null;
  const previewWrappers = previewSelector ? Array.from(document.querySelectorAll(previewSelector)) : [];
  const wrappers = [...selectedWrappers, ...previewWrappers];
  const definitions = new Set(wrappers.map((wrapper) => wrapper.dataset.definitionId));
  const graph = new Map(Array.from(definitions, (id) => [id, new Set()]));
  wrappers.forEach((wrapper) => {
    const sourceId = wrapper.dataset.definitionId;
    JSON.parse(wrapper.dataset.synonymTargets).map(String).forEach((targetId) => {
      if (!definitions.has(targetId)) return;
      graph.get(sourceId).add(targetId);
      graph.get(targetId).add(sourceId);
    });
  });
  const visited = new Set();
  wrappers.forEach((wrapper) => {
    const rootId = wrapper.dataset.definitionId;
    if (visited.has(rootId)) return;
    const component = new Set();
    const pending = [rootId];
    while (pending.length) {
      const definitionId = pending.pop();
      if (component.has(definitionId)) continue;
      component.add(definitionId);
      graph.get(definitionId).forEach((targetId) => pending.push(targetId));
    }
    component.forEach((definitionId) => visited.add(definitionId));
    const componentWrappers = wrappers.filter((item) => component.has(item.dataset.definitionId));
    const valueGroup = Array.from(component).sort((first, second) => Number(first) - Number(second))[0];
    componentWrappers.forEach((item) => { item.dataset.threadValueGroup = valueGroup; });
    const sourceInComponent = source && component.has(source.dataset.definitionId) ? source : null;
    const values = sourceInComponent
      ? readThreadFieldValues(sourceInComponent)
      : (componentWrappers.map(readThreadFieldValues).find((items) => items.length) || []);
    componentWrappers.forEach((item) => writeThreadFieldValues(item, values));
  });
}
function linkedValueNodes(source) {
  const attribute = source.dataset.threadValue ? 'threadValue' : 'threadValueGroup';
  const value = source.dataset[attribute];
  if (!value) return [];
  return Array.from(document.querySelectorAll(`[data-${attribute === 'threadValue' ? 'thread-value' : 'thread-value-group'}]`))
    .filter((item) => item.dataset[attribute] === value);
}
function setLinkedValueHighlight(source, active) {
  document.querySelectorAll('.is-linked-value').forEach((item) => item.classList.remove('is-linked-value'));
  document.querySelectorAll('.has-linked-thread-value').forEach((item) => item.classList.remove('has-linked-thread-value'));
  if (!active) return;
  linkedValueNodes(source).forEach((item) => {
    item.classList.add('is-linked-value');
    let parent = item.closest('details');
    while (parent) {
      if (!parent.open) parent.classList.add('has-linked-thread-value');
      parent = parent.parentElement?.closest('details');
    }
  });
}
document.addEventListener('pointerover', (event) => {
  const field = event.target.closest('[data-thread-value], [data-thread-value-group]');
  if (field) setLinkedValueHighlight(field, true);
});
document.addEventListener('pointerout', (event) => {
  const field = event.target.closest('[data-thread-value], [data-thread-value-group]');
  if (field && !field.contains(event.relatedTarget)) setLinkedValueHighlight(field, false);
});
document.addEventListener('focusin', (event) => {
  const field = event.target.closest('[data-thread-value], [data-thread-value-group]');
  if (field) setLinkedValueHighlight(field, true);
});
document.addEventListener('focusout', (event) => {
  const field = event.target.closest('[data-thread-value], [data-thread-value-group]');
  if (field && !field.contains(event.relatedTarget)) setLinkedValueHighlight(field, false);
});
function appendImplementation(container, implementation, isSelectedRoot = false) {
  const section = document.createElement('details'); section.className = 'thread-interface-implementation'; section.open = true;
  const summary = document.createElement('summary');
  const name = document.createElement('span');
  name.textContent = `${implementation.name}@${implementation.creator} v${implementation.version}`;
  summary.append(name);
  if (isSelectedRoot) {
    const remove = document.createElement('span'); remove.className = 'remove-thread-interface'; remove.textContent = '×'; remove.setAttribute('role', 'button'); remove.setAttribute('tabindex', '0'); remove.setAttribute('aria-label', `${implementation.name}を外す`);
    const removeInterface = (event) => { event.preventDefault(); event.stopPropagation(); selectedInterfaceIds.delete(implementation.id); renderSelectedInterfaces(); };
    remove.addEventListener('click', removeInterface);
    remove.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') removeInterface(event); });
    summary.append(remove);
  }
  const fields = document.createElement('div'); fields.className = 'thread-interface-implementation-fields';
  implementation.fields.forEach((field) => fields.append(makeFieldControl(implementation, field)));
  if (!implementation.fields.length) { const empty = document.createElement('p'); empty.className = 'empty'; empty.textContent = '入力するFieldはありません。'; fields.append(empty); }
  section.append(summary, fields); container.append(section);
}
function appendDirectField(container, field, isSelected = false) {
  const section = document.createElement('details'); section.className = 'thread-interface-implementation thread-direct-field'; section.open = true;
  const summary = document.createElement('summary');
  const name = document.createElement('span'); name.textContent = `${field.name}@${field.creator} v${field.version}/Field`; summary.append(name);
  if (isSelected) {
    const remove = document.createElement('span'); remove.className = 'remove-thread-interface'; remove.textContent = '×'; remove.setAttribute('role', 'button'); remove.setAttribute('tabindex', '0'); remove.setAttribute('aria-label', `${field.name}を外す`);
    const removeField = (event) => { event.preventDefault(); event.stopPropagation(); selectedDirectFieldIds.delete(field.id); renderSelectedDirectFields(); };
    remove.addEventListener('click', removeField);
    remove.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') removeField(event); });
    summary.append(remove);
  }
  const fields = document.createElement('div'); fields.className = 'thread-interface-implementation-fields';
  fields.append(makeFieldControl(null, {...field, label: field.name, required: true}, {direct: true}));
  section.append(summary, fields); container.append(section);
}
function renderSelectedDirectFields() {
  const container = document.getElementById('selected-direct-fields'); container.replaceChildren();
  selectedDirectFieldIds.forEach((id) => {
    const field = fieldCatalog.find((candidate) => candidate.id === id);
    if (!field) return;
    const input = document.createElement('input'); input.type = 'hidden'; input.name = 'direct_field_ids'; input.value = id; container.append(input);
    appendDirectField(container, field, true);
  });
  synchronizeThreadFieldControls();
}
function fieldCandidateButton(field) {
  const button = document.createElement('button'); button.className = 'ui-summary-item'; button.type = 'button';
  const context = document.createElement('span'); context.className = 'ui-summary-item-context'; context.setAttribute('aria-hidden', 'true');
  const title = document.createElement('strong'); title.className = 'ui-summary-item-title'; title.textContent = `${field.name}@${field.creator} v${field.version}/Field`;
  const updated = document.createElement('small'); updated.className = 'ui-summary-item-updated'; updated.textContent = `最終更新 ${new Date(field.updated_at).toLocaleString('ja-JP', {year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'})}`;
  button.append(context, title, updated);
  button.addEventListener('click', () => renderFieldPreview(field.id));
  return button;
}
function renderFieldSearchResults(formData) {
  const results = document.getElementById('thread-field-search-results');
  const name = String(formData.get('name') || '').trim().toLocaleLowerCase();
  const description = String(formData.get('description') || '').trim().toLocaleLowerCase();
  const fieldType = String(formData.get('field_type') || '');
  const matches = fieldCatalog.filter((field) => (
    (!name || `${field.name}@${field.creator}`.toLocaleLowerCase().includes(name))
    && (!description || field.description.toLocaleLowerCase().includes(description))
    && (!fieldType || field.type === fieldType)
  )).slice(0, 10);
  results.replaceChildren();
  matches.forEach((field) => results.append(fieldCandidateButton(field)));
  if (!matches.length) { const empty = document.createElement('p'); empty.className = 'empty'; empty.textContent = '条件に一致するFieldはありません。'; results.append(empty); }
}
async function renderFieldPreview(id) {
  previewFieldId = id;
  const requestId = ++previewFieldRequestId;
  const field = fieldCatalog.find((candidate) => candidate.id === id);
  document.getElementById('thread-field-detail-title').textContent = `${field.name}@${field.creator} v${field.version}/Field`;
  const detail = document.getElementById('thread-field-selector-detail');
  const loading = document.createElement('p'); loading.className = 'ui-pane-loading'; loading.textContent = '読み込み中...'; detail.replaceChildren(loading);
  setThreadStage('field-detail');
  try {
    const fragment = await NiixyUI.fetchFragment(field.detail_url);
    if (requestId !== previewFieldRequestId || previewFieldId !== id) return;
    detail.replaceChildren(fragment.querySelector('.field-definition-detail') || fragment);
  } catch {
    if (requestId !== previewFieldRequestId || previewFieldId !== id) return;
    const message = document.createElement('p'); message.className = 'ui-pane-error'; message.textContent = 'Fieldの詳細を読み込めませんでした。'; detail.replaceChildren(message); return;
  }
  const actions = document.createElement('div'); actions.className = 'interface-detail-actions';
  const use = document.createElement('button'); use.className = 'button primary'; use.type = 'button';
  if (selectorPurpose === 'search') {
    use.textContent = 'このFieldを検索条件に使う';
    use.addEventListener('click', () => completeSearchFieldSelection(field));
  } else {
    const editor = document.createElement('section'); editor.className = 'interface-implementation-editor';
    const editorTitle = document.createElement('h3'); editorTitle.textContent = '入力内容'; editor.append(editorTitle);
    appendDirectField(editor, field);
    detail.append(editor);
    synchronizeThreadFieldControls();
    use.textContent = selectedDirectFieldIds.has(id) ? '入力内容を反映' : 'このFieldを追加する';
    use.addEventListener('click', () => { detail.querySelectorAll('.thread-field-control').forEach((item) => item.dispatchEvent(new Event('input'))); selectedDirectFieldIds.add(id); renderSelectedDirectFields(); closeFieldSelector(); });
  }
  actions.append(use); detail.append(actions);
}
function openFieldSelector(id = null, purpose = 'create') {
  selectorPurpose = purpose;
  selectorReturnStage = purpose === 'search' ? 'list' : 'detail';
  ensureFieldSelectorPanes();
  if (id) renderFieldPreview(id);
  else setThreadStage('field-list');
}
function closeFieldSelector() {
  previewFieldRequestId += 1;
  previewFieldId = null;
  setThreadStage(selectorReturnStage);
  synchronizeThreadFieldControls();
}
function selectedImplementations() {
  const byId = new Map();
  interfaceCatalog.filter((item) => selectedInterfaceIds.has(item.id)).forEach((item) => item.implementations.forEach((implementation) => byId.set(implementation.id, implementation)));
  return Array.from(byId.values());
}
function renderSelectedInterfaces() {
  const container = document.getElementById('selected-thread-interfaces'); container.replaceChildren();
  selectedInterfaceIds.forEach((id) => {
    const input = document.createElement('input'); input.type = 'hidden'; input.name = 'interface_ids'; input.value = id; container.append(input);
  });
  selectedImplementations().forEach((implementation) => appendImplementation(container, implementation, selectedInterfaceIds.has(implementation.id)));
  synchronizeThreadFieldControls();
}
async function renderInterfacePreview(id) {
  previewInterfaceId = id;
  const requestId = ++previewRequestId;
  const item = interfaceCatalog.find((candidate) => candidate.id === id);
  document.getElementById('thread-interface-detail-title').textContent = `${item.name}@${item.creator} v${item.version}/${item.kind}`;
  const detail = document.getElementById('thread-interface-selector-detail');
  const loading = document.createElement('p'); loading.className = 'ui-pane-loading'; loading.textContent = '読み込み中...';
  detail.replaceChildren(loading);
  setThreadStage('interface-detail');
  try {
    const fragment = await NiixyUI.fetchFragment(item.detail_url);
    if (requestId !== previewRequestId || previewInterfaceId !== id) return;
    detail.replaceChildren(fragment);
  } catch (error) {
    if (requestId !== previewRequestId || previewInterfaceId !== id) return;
    const message = document.createElement('p'); message.className = 'ui-pane-error'; message.textContent = 'ThreadIFの詳細を読み込めませんでした。';
    detail.replaceChildren(message);
    return;
  }
  const actions = document.createElement('div'); actions.className = 'interface-detail-actions';
  const use = document.createElement('button'); use.className = 'button primary'; use.type = 'button';
  if (selectorPurpose === 'search') {
    use.textContent = 'このThreadIFを検索条件に使う';
    use.addEventListener('click', () => completeSearchInterfaceSelection(item));
  } else {
    const editor = document.createElement('section'); editor.className = 'interface-implementation-editor';
    const editorTitle = document.createElement('h3'); editorTitle.textContent = '実装内容'; editor.append(editorTitle);
    item.implementations.forEach((implementation) => appendImplementation(editor, implementation));
    detail.append(editor);
    synchronizeThreadFieldControls();
    use.textContent = selectedInterfaceIds.has(id) ? '入力内容を反映' : 'このThreadIFを実装する';
    use.addEventListener('click', () => { detail.querySelectorAll('.thread-interface-field').forEach((field) => field.dispatchEvent(new Event('input'))); selectedInterfaceIds.add(id); renderSelectedInterfaces(); closeInterfaceSelector(); });
  }
  actions.append(use); detail.append(actions);
}
function openInterfaceSelector(id = null, purpose = 'create') {
  selectorPurpose = purpose;
  selectorReturnStage = purpose === 'search' ? 'list' : 'detail';
  ensureInterfaceSelectorPanes();
  if (purpose === 'search') populateInterfaceSearch();
  if (id) renderInterfacePreview(id);
  else setThreadStage('interface-list');
}
function closeInterfaceSelector() {
  previewRequestId += 1;
  previewInterfaceId = null;
  setThreadStage(selectorReturnStage);
  synchronizeThreadFieldControls();
}
document.getElementById('open-thread-interface-selector').addEventListener('click', () => openInterfaceSelector(null, 'create'));
document.getElementById('open-direct-field-selector').addEventListener('click', () => openFieldSelector(null, 'create'));
function applyFilters() {
  const bounds = map.getBounds();
  let visibleCount = 0;
  list.querySelectorAll('.thread-item').forEach((item) => {
    const thread = markers.find((candidate) => String(candidate.id) === item.dataset.threadId);
    const inSearch = appliedSearchIds === null || appliedSearchIds.has(item.dataset.threadId);
    const inBounds = thread && bounds.contains([thread.longitude, thread.latitude]);
    const visible = inSearch && inBounds;
    item.hidden = !visible;
    if (visible) visibleCount += 1;
    const marker = markerById.get(item.dataset.threadId);
    if (marker) marker.getElement().hidden = !visible;
  });
  document.getElementById('thread-search-empty').hidden = visibleCount !== 0;
  if (searchForm.elements.sort_kind.value === 'near') sortByDistance();
  else if (appliedSearchOrder) appliedSearchOrder.forEach((id) => { const item = list.querySelector(`[data-thread-id="${id}"]`); if (item) list.append(item); });
}
function sortByDistance() {
  const center = map.getCenter();
  const distance = (thread) => (thread.latitude - center.lat) ** 2 + (thread.longitude - center.lng) ** 2;
  const direction = searchForm.elements.sort_direction.value === 'desc' ? -1 : 1;
  Array.from(list.querySelectorAll('.thread-item')).sort((first, second) => {
    const firstThread = markers.find((thread) => String(thread.id) === first.dataset.threadId);
    const secondThread = markers.find((thread) => String(thread.id) === second.dataset.threadId);
    return (distance(firstThread) - distance(secondThread)) * direction;
  }).forEach((item) => list.append(item));
}

function renderAccountConditionTarget(target) {
  const container = document.querySelector(`[data-account-condition-target="${target}"]`);
  if (!container) return;
  container.replaceChildren();
  const groups = accountConditionGroups.get(target) || [];
  groups.forEach((group) => {
    const item = document.createElement('span');
    item.className = 'niimap-selected-account-condition';
    item.title = accountGroupLabel(group);
    const label = document.createElement('span');
    label.textContent = accountGroupLabel(group);
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = '×';
    remove.setAttribute('aria-label', `${accountGroupLabel(group)}を削除`);
    remove.addEventListener('click', () => {
      accountConditionGroups.set(target, groups.filter((candidate) => candidate !== group));
      renderAccountConditionTarget(target);
    });
    item.append(label, remove);
    container.append(item);
  });
}
function setAccountConditionGroups(target, groups) {
  accountConditionGroups.set(target, copyAccountGroups(groups));
  renderAccountConditionTarget(target);
}
function addAccountConditionGroup(target, group) {
  if (!target || !group.length) return;
  const groups = accountConditionGroups.get(target) || [];
  const key = accountGroupKey(group);
  if (!groups.some((candidate) => accountGroupKey(candidate) === key)) groups.push(copyAccountGroups([group])[0]);
  accountConditionGroups.set(target, groups);
  renderAccountConditionTarget(target);
}
function selectedAccountConditions() {
  return accountConditionCatalog.filter((condition) => selectedAccountConditionIds.has(accountConditionKey(condition)));
}
function updateAccountConditionGroupControls() {
  const toggle = document.getElementById('account-condition-group-toggle');
  const count = document.getElementById('account-condition-selection-count');
  const add = document.getElementById('add-account-condition-group');
  toggle.textContent = accountConditionGroupMode ? `キャンセル（${selectedAccountConditionIds.size}）` : 'ANDグループ';
  count.hidden = !accountConditionGroupMode;
  count.textContent = `${selectedAccountConditionIds.size}件選択中`;
  add.disabled = !accountConditionGroupMode || selectedAccountConditionIds.size === 0;
}
function resetAccountConditionGroupMode() {
  accountConditionGroupMode = false;
  selectedAccountConditionIds.clear();
  updateAccountConditionGroupControls();
}
function csrfToken() {
  return searchForm.querySelector('[name="csrfmiddlewaretoken"]').value;
}
async function saveAccountCondition(condition, existingCondition = null) {
  if (workspace.dataset.authenticated !== 'true') {
    const localCondition = {...condition, id: `local:${accountConditionKey(condition)}`, active: true};
    const key = accountConditionKey(localCondition);
    accountConditionCatalog = [localCondition, ...accountConditionCatalog.filter((item) => (
      accountConditionKey(item) !== key && item.id !== existingCondition?.id
    ))];
    return localCondition;
  }
  const data = new FormData();
  data.append('csrfmiddlewaretoken', csrfToken());
  data.append('kind', condition.kind);
  data.append('definition', JSON.stringify(condition.definition));
  if (existingCondition) data.append('condition_id', existingCondition.id);
  const response = await fetch(workspace.dataset.accountConditionSaveUrl, {
    method: 'POST',
    body: data,
    headers: {'X-Requested-With': 'XMLHttpRequest'},
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Account条件を保存できませんでした。');
  const key = accountConditionKey(result.condition);
  accountConditionCatalog = [result.condition, ...accountConditionCatalog.filter((item) => (
    accountConditionKey(item) !== key && item.id !== existingCondition?.id
  ))];
  return result.condition;
}
async function useAccountCondition(condition) {
  try {
    const saved = await saveAccountCondition(condition);
    if (accountConditionGroupMode) {
      const key = accountConditionKey(saved);
      if (selectedAccountConditionIds.has(key)) selectedAccountConditionIds.delete(key);
      else selectedAccountConditionIds.add(key);
      renderAccountConditionCatalog();
      return;
    }
    addAccountConditionGroup(activeAccountConditionTarget, [saved]);
    renderAccountConditionCatalog();
  } catch (error) {
    document.getElementById('account-condition-list').replaceChildren(Object.assign(document.createElement('p'), {className: 'event-form-error', textContent: error.message}));
  }
}
async function deleteAccountCondition(condition) {
  const key = accountConditionKey(condition);
  if (workspace.dataset.authenticated === 'true' && Number.isInteger(Number(condition.id))) {
    const data = new FormData();
    data.append('csrfmiddlewaretoken', csrfToken());
    const url = workspace.dataset.accountConditionDeleteUrl.replace('/0/', `/${condition.id}/`);
    const response = await fetch(url, {method: 'POST', body: data, headers: {'X-Requested-With': 'XMLHttpRequest'}});
    if (!response.ok) return;
  }
  accountConditionCatalog = accountConditionCatalog.filter((item) => accountConditionKey(item) !== key);
  selectedAccountConditionIds.delete(key);
  renderAccountConditionCatalog();
}
function renderAccountConditionCatalog() {
  const container = document.getElementById('account-condition-list');
  container.replaceChildren();
  const conditions = accountConditionCatalog;
  conditions.forEach((condition) => {
    const row = document.createElement('div');
    row.className = 'account-condition-summary';
    const choose = document.createElement('button');
    choose.className = 'ui-summary-item';
    choose.type = 'button';
    choose.innerHTML = '<span class="ui-summary-item-context"></span><strong class="ui-summary-item-title"></strong><small class="ui-summary-item-updated"></small>';
    const field = condition.kind === 'field'
      ? fieldCatalog.find((item) => item.id === Number(condition.definition.field_id))
      : null;
    choose.querySelector('.ui-summary-item-context').textContent = field ? fieldConditionContext(condition, field) : '';
    choose.querySelector('strong').textContent = field ? `${field.name}@${field.creator}` : condition.label;
    choose.querySelector('small').textContent = accountConditionKindLabel(condition);
    const key = accountConditionKey(condition);
    choose.classList.toggle('is-selected', selectedAccountConditionIds.has(key));
    choose.setAttribute('aria-pressed', selectedAccountConditionIds.has(key) ? 'true' : 'false');
    choose.addEventListener('click', () => useAccountCondition(condition));
    const remove = document.createElement('button');
    remove.className = 'account-condition-delete';
    remove.type = 'button';
    remove.textContent = '×';
    remove.setAttribute('aria-label', `${condition.label}を一覧から削除`);
    remove.addEventListener('click', () => deleteAccountCondition(condition));
    row.append(choose);
    if (condition.kind === 'field') {
      if (field) {
        const edit = document.createElement('button');
        edit.className = 'account-condition-edit';
        edit.type = 'button';
        edit.textContent = '編集';
        edit.setAttribute('aria-label', `${condition.label}を編集`);
        edit.addEventListener('click', () => {
          accountConditionDetailReturnStage = 'account-conditions';
          accountConditionDetailPane(field, 'edit', condition);
          setThreadStage('account-condition-history-edit');
        });
        row.append(edit);
      }
    }
    row.append(remove);
    container.append(row);
  });
  if (!conditions.length) {
    const empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = 'Account条件の履歴はありません。';
    container.append(empty);
  }
  updateAccountConditionGroupControls();
}
function openAccountConditions(target) {
  activeAccountConditionTarget = target;
  resetAccountConditionGroupMode();
  renderAccountConditionCatalog();
  setThreadStage('account-conditions');
}
function closeAccountConditions() {
  activeAccountConditionTarget = null;
  resetAccountConditionGroupMode();
  setThreadStage('list');
}
function ensureAccountSelectorPane() {
  if (document.getElementById('account-selector-pane')) return;
  document.querySelector('.thread-track').append(document.getElementById('account-selector-template').content.cloneNode(true));
  document.getElementById('close-account-selector').addEventListener('click', () => setThreadStage('account-conditions'));
  document.querySelectorAll('[data-account-condition-kind]').forEach((button) => {
    button.addEventListener('click', () => {
      accountConditionBrowserKind = button.dataset.accountConditionKind;
      renderAccountConditionBrowser();
    });
  });
}
function accountSelectorSummary(label, meta, onClick = null) {
  const button = document.createElement('button');
  button.className = 'ui-summary-item';
  button.type = 'button';
  button.innerHTML = '<span class="ui-summary-item-context"></span><strong class="ui-summary-item-title"></strong><small class="ui-summary-item-updated"></small>';
  button.querySelector('strong').textContent = label;
  button.querySelector('small').textContent = meta;
  if (onClick) button.addEventListener('click', onClick);
  return button;
}
function selectorEmpty(message) {
  const empty = document.createElement('p');
  empty.className = 'empty';
  empty.textContent = message;
  return empty;
}
function accountConditionKindLabel(condition) {
  return {default: 'Default', account: 'Account', account_interface: 'AccountIF', field: 'Field', room: 'Room'}[condition.kind] || condition.kind;
}
function fieldConditionContext(condition, field) {
  const value = condition.definition.value;
  if (!value) return '';
  const renderedValue = field.type === 'boolean' ? (value === 'true' ? 'はい' : 'いいえ') : value;
  const dateLike = ['date', 'datetime'].includes(field.type);
  const operator = {
    contains: '含む',
    not_contains: '含まない',
    equals: '一致',
    gte: dateLike ? '以降' : '以上',
    lte: dateLike ? '以前' : '以下',
  }[condition.definition.operator] || '';
  return [renderedValue, operator].filter(Boolean).join(' ');
}
function renderAccountSelectorResults(container, conditions, message = '') {
  container.replaceChildren();
  conditions.forEach((condition) => {
    container.append(accountSelectorSummary(condition.label, accountConditionKindLabel(condition), async () => {
      try {
        await saveAccountCondition(condition);
        renderAccountConditionCatalog();
        setThreadStage('account-conditions');
      } catch (error) {
        renderAccountSelectorResults(container, [], error.message);
      }
    }));
  });
  if (!conditions.length || message) {
    const empty = selectorEmpty(message || '該当する項目はありません。');
    if (message) empty.className = 'event-form-error';
    container.append(empty);
  }
}
function configureAccountSelector(tabs) {
  document.querySelector('.account-condition-detail-pane')?.remove();
  const pane = document.getElementById('account-selector-pane');
  const tabList = document.getElementById('account-selector-tabs');
  const content = document.getElementById('account-selector-content');
  tabList.replaceChildren();
  content.replaceChildren();
  tabList.hidden = tabs.length === 0;
  tabList.setAttribute('aria-label', `${accountConditionKindLabel({kind: accountConditionBrowserKind})}の分類`);
  tabs.forEach((tab, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.role = 'tab';
    button.dataset.uiTab = tab.key;
    button.textContent = tab.label;
    button.classList.toggle('is-active', index === 0);
    button.setAttribute('aria-selected', index === 0 ? 'true' : 'false');
    const panel = document.createElement('section');
    panel.className = `ui-tab-panel module-list-panel${index === 0 ? ' is-active' : ''}`;
    panel.dataset.uiTabPanel = tab.key;
    tab.render(panel);
    tabList.append(button);
    content.append(panel);
  });
  NiixyUI.bindTabs(pane);
}
function renderFieldSelectorItems(container, fields) {
  container.replaceChildren();
  fields.slice(0, 10).forEach((field) => {
    const updated = new Date(field.updated_at).toLocaleString('ja-JP');
    container.append(accountSelectorSummary(
      `${field.name}@${field.creator} v${field.version}/Field`,
      `最終更新 ${updated}`,
      () => openAccountFieldDetail(field),
    ));
  });
  if (!fields.length) container.append(selectorEmpty('該当するFieldはありません。'));
}
function accountConditionDetailPane(field, mode = 'detail', existingCondition = null) {
  document.querySelector('.account-condition-detail-pane')?.remove();
  const pane = document.createElement('aside');
  pane.className = 'ui-detail-pane account-condition-detail-pane';
  const header = document.createElement('header');
  header.className = 'ui-pane-header ui-detail-pane-header';
  const title = document.createElement('h2');
  title.textContent = `${field.name}@${field.creator} v${field.version}/Field`;
  const close = document.createElement('button');
  close.className = 'icon-button'; close.type = 'button'; close.textContent = '×'; close.setAttribute('aria-label', 'Field一覧に戻る');
  close.addEventListener('click', () => { pane.remove(); setThreadStage(accountConditionDetailReturnStage); });
  header.append(title, close);
  const body = document.createElement('div');
  body.className = 'account-condition-detail-body';
  pane.append(header, body);
  document.querySelector('.thread-track').append(pane);
  if (mode === 'edit') renderAccountFieldEditor(body, field, existingCondition);
  else renderAccountFieldDefinition(body, field);
  return pane;
}
function renderAccountFieldDefinition(body, field) {
  const summary = document.createElement('dl');
  summary.className = 'field-definition-summary';
  [['詳細', field.description || ''], ['型', field.type_label]].forEach(([term, value]) => {
    const row = document.createElement('div');
    const dt = document.createElement('dt'); dt.textContent = `${term}:`;
    const dd = document.createElement('dd'); dd.textContent = value;
    row.append(dt, dd); summary.append(row);
  });
  const actions = document.createElement('div');
  actions.className = 'interface-detail-actions';
  const edit = document.createElement('button');
  edit.className = 'button primary'; edit.type = 'button'; edit.textContent = 'Account条件を編集';
  edit.addEventListener('click', () => {
    accountConditionDetailReturnStage = 'account-selector';
    const pane = accountConditionDetailPane(field, 'edit');
    setThreadStage('account-condition-detail');
    pane.scrollTo({top: 0});
  });
  actions.append(edit);
  body.append(summary, actions);
}
function fieldConditionEditorControls(field, existingCondition = null) {
  const wrapper = document.createElement('div');
  wrapper.className = 'account-field-condition-controls';
  const operator = document.createElement('select');
  operator.name = 'operator';
  const value = document.createElement('input');
  value.name = 'value';
  let options;
  if (field.type === 'boolean') {
    options = [['', '値を指定しない'], ['true', 'はい'], ['false', 'いいえ']];
    value.type = 'hidden';
  } else if (['integer', 'decimal', 'date', 'datetime'].includes(field.type)) {
    options = [['equals', '一致'], ['gte', '以降'], ['lte', '以前']];
    value.type = {integer: 'number', decimal: 'number', date: 'date', datetime: 'datetime-local'}[field.type];
    if (field.type === 'decimal') value.step = 'any';
  } else {
    options = [['contains', '含む'], ['not_contains', '含まない'], ['equals', '一致']];
    value.type = 'text';
  }
  options.forEach(([key, label]) => { const option = document.createElement('option'); option.value = key; option.textContent = label; operator.append(option); });
  if (['single_choice', 'multiple_choice'].includes(field.type)) {
    const choice = document.createElement('select');
    choice.name = 'value';
    choice.innerHTML = '<option value="">値を指定しない</option>';
    (field.settings.options || []).forEach((item) => { const option = document.createElement('option'); option.value = item; option.textContent = item; choice.append(option); });
    value.replaceWith(choice);
    wrapper.append(operator, choice);
  } else {
    value.placeholder = '空欄なら実装有無だけを条件にします';
    wrapper.append(operator, value);
  }
  const definition = existingCondition?.definition || {};
  if (field.type === 'boolean') {
    operator.value = definition.value || definition.operator || '';
  } else {
    operator.value = definition.operator || operator.value;
    wrapper.querySelector('[name="value"]').value = definition.value || '';
  }
  return wrapper;
}
function renderAccountFieldEditor(body, field, existingCondition = null) {
  const form = document.createElement('form');
  form.className = 'account-field-condition-form';
  const heading = document.createElement('h3'); heading.textContent = 'Account条件';
  const controls = fieldConditionEditorControls(field, existingCondition);
  const actions = document.createElement('div'); actions.className = 'interface-detail-actions';
  const add = document.createElement('button'); add.className = 'button primary'; add.type = 'submit'; add.textContent = existingCondition ? '条件を更新する' : '条件一覧に追加する';
  const error = document.createElement('p'); error.className = 'event-form-error'; error.hidden = true;
  actions.append(add); form.append(heading, controls, actions, error);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    let operator = data.get('operator');
    const value = data.get('value') || (field.type === 'boolean' ? operator : '');
    if (!value) operator = '';
    try {
      await saveAccountCondition({kind: 'field', definition: {field_id: field.id, operator, value}, label: `${field.name}@${field.creator}`}, existingCondition);
      document.querySelector('.account-condition-detail-pane')?.remove();
      renderAccountConditionCatalog();
      setThreadStage('account-conditions');
    } catch (exception) {
      error.textContent = exception.message; error.hidden = false;
    }
  });
  body.append(form);
}
function openAccountFieldDetail(field) {
  accountConditionDetailReturnStage = 'account-selector';
  accountConditionDetailPane(field);
  setThreadStage('account-condition-detail');
}
function fieldSearchPanel(panel) {
  const details = document.createElement('details');
  details.className = 'field-search-controls';
  details.open = true;
  const summary = document.createElement('summary');
  summary.textContent = '検索条件';
  const form = document.createElement('form');
  form.className = 'field-search-form';
  form.innerHTML = '<div class="field-search-row"><label>名前</label><input type="search" name="name" placeholder="Field名@NiixyID"></div><div class="field-search-row"><label>詳細</label><input type="search" name="description"></div><div class="field-search-row"><label>型</label><select name="field_type"><option value="">すべて</option></select></div><div class="field-search-actions"><button class="button" type="submit">検索</button></div>';
  Array.from(new Map(fieldCatalog.map((field) => [field.type, field.type_label]))).forEach(([value, label]) => {
    const option = document.createElement('option'); option.value = value; option.textContent = label; form.elements.field_type.append(option);
  });
  const results = document.createElement('div');
  results.className = 'ui-summary-list';
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const nameTerms = data.get('name').trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const descriptionTerms = data.get('description').trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const type = data.get('field_type');
    const filtered = fieldCatalog.filter((field) => {
      const identity = `${field.name}@${field.creator}`.toLocaleLowerCase();
      const description = (field.description || '').toLocaleLowerCase();
      return nameTerms.every((term) => identity.includes(term))
        && descriptionTerms.every((term) => description.includes(term))
        && (!type || field.type === type);
    });
    renderFieldSelectorItems(results, filtered);
    if (details.open) summary.click();
  });
  details.append(summary, form);
  panel.append(details, results);
  renderFieldSelectorItems(results, fieldCatalog);
}
function accountSearchPanel(panel) {
  const form = document.createElement('form');
  form.className = 'account-selector-search';
  form.innerHTML = '<input name="q" type="search" placeholder="名前@NiixyID"><button class="button primary" type="submit">検索</button>';
  const results = document.createElement('div');
  results.className = 'ui-summary-list';
  results.append(selectorEmpty('名前またはNiixyIDで検索してください。'));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const query = new FormData(form).get('q');
    const response = await fetch(`${workspace.dataset.accountSearchUrl}?${new URLSearchParams({q: query})}`);
    const result = await response.json();
    renderAccountSelectorResults(results, result.accounts.map((account) => ({kind: 'account', definition: {account_id: account.id}, label: account.label})));
  });
  panel.append(form, results);
}
function placeholderSelectorPanel(panel, message) {
  panel.append(selectorEmpty(message));
}
function renderAccountConditionBrowser() {
  const kind = accountConditionBrowserKind;
  document.querySelectorAll('[data-account-condition-kind]').forEach((button) => {
    const active = button.dataset.accountConditionKind === kind;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  if (kind === 'default') {
    configureAccountSelector([]);
    const content = document.getElementById('account-selector-content');
    const results = document.createElement('div');
    results.className = 'ui-summary-list module-list-panel is-active';
    content.append(results);
    renderAccountSelectorResults(results, availableAccountConditionCatalog.filter((condition) => condition.kind === 'default'));
  } else if (kind === 'account') {
    configureAccountSelector([
      {key: 'search', label: '検索', render: accountSearchPanel},
      ...['Follow', 'Mute', 'Love', 'Hate'].map((label) => ({key: label.toLocaleLowerCase(), label, render: (panel) => placeholderSelectorPanel(panel, `${label}したAccountはありません。`)})),
    ]);
  } else if (kind === 'field') {
    configureAccountSelector([
      {key: 'search', label: '検索', render: fieldSearchPanel},
      {key: 'self', label: '自作', render: (panel) => {
        const results = document.createElement('div'); results.className = 'ui-summary-list'; panel.append(results);
        renderFieldSelectorItems(results, fieldCatalog.filter((field) => workspace.dataset.authenticated === 'true' && field.creator === workspace.dataset.currentActor));
      }},
      {key: 'saved', label: '保存', render: (panel) => placeholderSelectorPanel(panel, '保存したFieldはありません。')},
    ]);
  } else if (kind === 'account_interface') {
    configureAccountSelector([
      {key: 'search', label: '検索', render: (panel) => placeholderSelectorPanel(panel, 'AccountIF検索は今後実装予定です。')},
      {key: 'self', label: '自作', render: (panel) => placeholderSelectorPanel(panel, '自作のAccountIFはありません。')},
      {key: 'saved', label: '保存', render: (panel) => placeholderSelectorPanel(panel, '保存したAccountIFはありません。')},
    ]);
  } else {
    configureAccountSelector([
      {key: 'search', label: '検索', render: (panel) => placeholderSelectorPanel(panel, 'Room検索は今後実装予定です。')},
      {key: 'joined', label: '参加', render: (panel) => placeholderSelectorPanel(panel, '参加中のRoomはありません。')},
      {key: 'saved', label: '保存', render: (panel) => placeholderSelectorPanel(panel, '保存したRoomはありません。')},
    ]);
  }
}
function browseAccountConditions() {
  ensureAccountSelectorPane();
  renderAccountConditionBrowser();
  setThreadStage('account-selector');
}

function removeConditionButton(row) {
  const remove = document.createElement('button');
  remove.className = 'niimap-condition-remove'; remove.type = 'button'; remove.textContent = '×'; remove.setAttribute('aria-label', '条件を削除');
  remove.addEventListener('click', () => row.remove());
  return remove;
}
function optionSelect(name, options, value) {
  const select = document.createElement('select'); select.name = name;
  options.forEach(([key, label]) => { const option = document.createElement('option'); option.value = key; option.textContent = label; option.selected = key === value; select.append(option); });
  return select;
}
function fieldOperators(field) {
  if (field.type === 'boolean') return [['true', 'はい'], ['false', 'いいえ']];
  if (['integer', 'decimal', 'date', 'datetime'].includes(field.type)) return [['gte', '以降'], ['lte', '以前'], ['equals', '一致']];
  return [['contains', '含む'], ['not_contains', '含まない'], ['equals', '一致']];
}
function addFieldCondition(field, condition = {}) {
  const row = document.createElement('div'); row.className = 'niimap-condition-row niimap-module-condition'; row.dataset.conditionKind = 'field'; row.dataset.fieldId = field.id;
  const name = document.createElement('span'); name.textContent = `${field.name}@${field.creator}`;
  const operator = optionSelect('operator', fieldOperators(field), condition.operator);
  const value = document.createElement('input'); value.name = 'value'; value.type = ['date', 'datetime'].includes(field.type) ? (field.type === 'date' ? 'date' : 'datetime-local') : 'text'; value.value = condition.value || ''; value.placeholder = field.type_label;
  if (field.type === 'boolean') value.hidden = true;
  row.append(name, operator, value, removeConditionButton(row));
  document.getElementById('niimap-field-conditions').append(row);
}
function addInterfaceCondition(item, condition = {}) {
  const row = document.createElement('div'); row.className = 'niimap-condition-row niimap-module-condition'; row.dataset.conditionKind = 'interface'; row.dataset.interfaceId = item.id;
  const name = document.createElement('span'); name.textContent = `${item.name}@${item.creator}`;
  row.append(name, optionSelect('operator', [['include', '含む'], ['exclude', '含まない']], condition.operator), removeConditionButton(row));
  document.getElementById('niimap-interface-conditions').append(row);
}
function completeSearchFieldSelection(field) {
  if (searchSelectionTarget === 'sort-field') {
    selectedSortField = field;
    const button = searchForm.querySelector('[data-search-select="sort-field"]');
    button.textContent = `${field.name}@${field.creator}`;
  } else addFieldCondition(field);
  closeFieldSelector();
}
function completeSearchInterfaceSelection(item) {
  addInterfaceCondition(item);
  closeInterfaceSelector();
}
function populateInterfaceSearch() {
  const panel = document.querySelector('#thread-interface-selector [data-ui-tab-panel="search"]');
  if (!panel) return;
  panel.replaceChildren();
  const input = document.createElement('input'); input.className = 'niimap-picker-search'; input.type = 'search'; input.placeholder = 'ThreadIF名@NiixyID';
  const results = document.createElement('div'); results.className = 'ui-summary-list';
  const render = () => {
    const query = input.value.trim().toLocaleLowerCase(); results.replaceChildren();
    interfaceCatalog.filter((item) => !query || `${item.name}@${item.creator}`.toLocaleLowerCase().includes(query)).slice(0, 10).forEach((item) => {
      const button = document.createElement('button'); button.className = 'ui-summary-item'; button.type = 'button';
      button.innerHTML = `<span class="ui-summary-item-context"></span><strong class="ui-summary-item-title"></strong><small class="ui-summary-item-updated"></small>`;
      button.querySelector('strong').textContent = `${item.name}@${item.creator} v${item.version}/${item.kind}`;
      button.querySelector('small').textContent = `最終更新 ${new Date(item.updated_at).toLocaleString('ja-JP')}`;
      button.addEventListener('click', () => renderInterfacePreview(item.id)); results.append(button);
    });
  };
  input.addEventListener('input', render); panel.append(input, results); render();
}
function defaultAccountCondition(code) {
  return accountConditionCatalog.find((condition) => condition.kind === 'default' && condition.definition.code === code)
    || availableAccountConditionCatalog.find((condition) => condition.kind === 'default' && condition.definition.code === code)
    || null;
}
function searchConditions() {
  return {
    creator_include_groups: copyAccountGroups(accountConditionGroups.get('creator-include') || []),
    creator_exclude_groups: copyAccountGroups(accountConditionGroups.get('creator-exclude') || []),
    policy: Array.from(document.querySelectorAll('.niimap-policy-condition')).map((row) => ({
      capability: row.dataset.policyCapability,
      decision: row.dataset.policyDecision,
      account_groups: copyAccountGroups(accountConditionGroups.get(row.dataset.policyTarget) || []),
    })).filter((condition) => condition.account_groups.length),
    fields: Array.from(document.querySelectorAll('[data-condition-kind="field"]')).map((row) => ({field_id: Number(row.dataset.fieldId), operator: row.querySelector('[name="operator"]').value, value: row.querySelector('[name="value"]').value})),
    interfaces: Array.from(document.querySelectorAll('[data-condition-kind="interface"]')).map((row) => ({interface_id: Number(row.dataset.interfaceId), operator: row.querySelector('[name="operator"]').value})),
  };
}
function restoreSearchState(state) {
  searchForm.reset(); selectedSortField = null;
  accountConditionGroups.clear();
  document.querySelectorAll('#niimap-field-conditions, #niimap-interface-conditions').forEach((list) => list.replaceChildren());
  if (state) Object.entries(state).forEach(([name, value]) => { if (name !== 'conditions' && name !== 'sort_field_id' && searchForm.elements[name]) searchForm.elements[name].value = value; });
  setAccountConditionGroups('creator-include', state?.conditions?.creator_include_groups || []);
  setAccountConditionGroups('creator-exclude', state?.conditions?.creator_exclude_groups || []);
  document.querySelectorAll('.niimap-policy-condition').forEach((row) => {
    const condition = (state?.conditions?.policy || []).find((item) => (
      item.capability === row.dataset.policyCapability && item.decision === row.dataset.policyDecision
    ));
    const groups = condition?.account_groups || (condition?.actor ? [[defaultAccountCondition(condition.actor)]] : []);
    setAccountConditionGroups(row.dataset.policyTarget, groups.filter((group) => group.every(Boolean)));
  });
  (state?.conditions?.fields || []).forEach((condition) => { const field = fieldCatalog.find((item) => item.id === Number(condition.field_id)); if (field) addFieldCondition(field, condition); });
  (state?.conditions?.interfaces || []).forEach((condition) => { const item = interfaceCatalog.find((candidate) => candidate.id === Number(condition.interface_id)); if (item) addInterfaceCondition(item, condition); });
  if (state?.sort_field_id) {
    selectedSortField = fieldCatalog.find((field) => field.id === Number(state.sort_field_id)) || null;
  }
  const sortButton = searchForm.querySelector('[data-search-select="sort-field"]');
  sortButton.textContent = selectedSortField ? `${selectedSortField.name}@${selectedSortField.creator}` : 'Fieldを選択';
  sortButton.hidden = searchForm.elements.sort_kind.value !== 'field';
}
function emptySearchState() {
  return {sort_kind: 'updated', sort_direction: 'desc', target_type: 'all', updated_value: '', updated_operator: 'after', freeword_include: '', freeword_exclude: '', sort_field_id: '', conditions: {creator_include_groups: [], creator_exclude_groups: [], policy: [], fields: [], interfaces: []}};
}
function initialSearchState() {
  const empty = emptySearchState();
  if (!savedSearchState || !Object.keys(savedSearchState).length) return empty;
  return {
    ...empty,
    ...savedSearchState,
    conditions: {...empty.conditions, ...(savedSearchState.conditions || {})},
  };
}
function selectThread(id, scroll = false) {
  list.querySelectorAll('.thread-item').forEach((item) => {
    const selected = item.dataset.threadId === String(id);
    item.classList.toggle('is-open', selected);
  });
  markerById.forEach((marker, markerId) => marker.getElement().classList.toggle('is-highlighted', markerId === String(id)));
  showThreadMarker(id);
  const item = list.querySelector(`[data-thread-id="${id}"]`);
  if (scroll && item) item.scrollIntoView({block: 'nearest'});
}
function showThreadMarker(id) {
  const thread = markers.find((item) => String(item.id) === String(id));
  if (!thread) return;

  const coordinates = [thread.longitude, thread.latitude];
  if (map.getBounds().contains(coordinates)) return;

  const bounds = map.getBounds();
  bounds.extend(coordinates);
  map.fitBounds(bounds, {
    duration: 500,
    maxZoom: map.getZoom(),
    padding: 48,
  });
}
function updateThreadUrl(id, replace = false) {
  const url = new URL(location.href);
  const threadId = id ? String(id) : null;
  if (url.searchParams.get('thread') === threadId) return;
  if (threadId) url.searchParams.set('thread', threadId);
  else url.searchParams.delete('thread');
  history[replace ? 'replaceState' : 'pushState']({}, '', url);
}
function openDetail(id, shouldUpdateUrl = true) {
  const pane = document.querySelector(`[data-thread-detail-pane="${id}"]`);
  if (!pane) return false;
  if (createControls.open) NiixyUI.setAccordionExpanded(createControls, false);
  creating = false;
  createForm.hidden = true;
  setThreadStage('detail');
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => {
    const selected = pane.dataset.threadDetailPane === String(id);
    pane.hidden = !selected;
    if (selected) detailTitle.textContent = `${pane.dataset.threadTitle} (${pane.dataset.threadPostCount})`;
  });
  document.querySelector('.thread-detail-pane').scrollTo({top: 0});
  if (shouldUpdateUrl) updateThreadUrl(id);
  return true;
}
function closeDetail(shouldUpdateUrl = true) {
  setThreadStage('list');
  createForm.hidden = true;
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  markerById.forEach((marker) => marker.getElement().classList.remove('is-highlighted'));
  list.querySelectorAll('.thread-item').forEach((item) => item.classList.remove('is-open'));
  detailTitle.textContent = '';
  if (shouldUpdateUrl) updateThreadUrl(null);
}
function applyThreadStateFromUrl() {
  const url = new URL(location.href);
  const threadId = threadIdFromUrl();
  if (!threadId) {
    closeDetail(false);
    focusMapFromUrl(true);
    if (url.searchParams.has('thread')) updateThreadUrl(null, true);
    return;
  }
  if (!openDetail(threadId, false)) {
    closeDetail(false);
    updateThreadUrl(null, true);
    return;
  }
  selectThread(threadId, true);
}
searchControls.addEventListener('niixy:accordion-change', (event) => {
  if (!event.detail.expanded) return;
  if (createControls.open) NiixyUI.setAccordionExpanded(createControls, false);
  creating = false;
});
createControls.addEventListener('niixy:accordion-change', (event) => {
  creating = event.detail.expanded;
  if (event.detail.expanded && searchControls.open) NiixyUI.setAccordionExpanded(searchControls, false);
});
openThreadCreate.addEventListener('click', () => {
  if (openThreadCreate.disabled) return;
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  createForm.hidden = false; detailTitle.textContent = 'Threadを作成';
  document.getElementById('thread-location-status').textContent = '地点を選択しました。';
  setThreadStage('detail');
});
document.getElementById('close-thread-detail').addEventListener('click', () => {
  closeDetail();
  sessionStorage.removeItem(resumeStorageKey);
});
searchForm.elements.sort_kind.addEventListener('change', () => {
  searchForm.querySelector('[data-search-select="sort-field"]').hidden = searchForm.elements.sort_kind.value !== 'field';
});
document.querySelectorAll('[data-open-account-conditions]').forEach((button) => button.addEventListener('click', () => openAccountConditions(button.dataset.openAccountConditions)));
document.getElementById('close-account-condition-pane').addEventListener('click', closeAccountConditions);
document.getElementById('browse-account-conditions').addEventListener('click', browseAccountConditions);
document.getElementById('account-condition-group-toggle').addEventListener('click', () => {
  if (accountConditionGroupMode) resetAccountConditionGroupMode();
  else {
    accountConditionGroupMode = true;
    selectedAccountConditionIds.clear();
    renderAccountConditionCatalog();
  }
});
document.getElementById('add-account-condition-group').addEventListener('click', () => {
  addAccountConditionGroup(activeAccountConditionTarget, selectedAccountConditions());
  resetAccountConditionGroupMode();
  renderAccountConditionCatalog();
});
searchForm.querySelectorAll('[data-search-select]').forEach((button) => button.addEventListener('click', () => {
  searchSelectionTarget = button.dataset.searchSelect;
  if (searchSelectionTarget === 'interface') openInterfaceSelector(null, 'search');
  else openFieldSelector(null, 'search');
}));
document.getElementById('niimap-search-reset').addEventListener('click', () => restoreSearchState(emptySearchState()));
searchForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const pending = NiixyUI.beginPendingAction(event.submitter || searchForm.querySelector('[type="submit"]'));
  if (!pending) return;
  const error = document.getElementById('niimap-search-error'); error.hidden = true; error.textContent = '';
  const data = new FormData(searchForm); const conditions = searchConditions();
  data.append('creator_include_groups', JSON.stringify(conditions.creator_include_groups));
  data.append('creator_exclude_groups', JSON.stringify(conditions.creator_exclude_groups));
  data.append('policy_conditions', JSON.stringify(conditions.policy));
  data.append('field_conditions', JSON.stringify(conditions.fields));
  data.append('interface_conditions', JSON.stringify(conditions.interfaces));
  data.append('sort_field_id', selectedSortField?.id || '');
  try {
    const response = await fetch(workspace.dataset.searchUrl, {method: 'POST', body: data, headers: {'X-Requested-With': 'XMLHttpRequest'}});
    const result = await response.json();
    if (!response.ok) { error.textContent = Object.values(result.errors || {}).flat().join(' '); error.hidden = false; return; }
    appliedSearchOrder = result.thread_ids.map(String); appliedSearchIds = new Set(appliedSearchOrder);
    applyFilters();
    if (searchControls.open) NiixyUI.setAccordionExpanded(searchControls, false);
  } catch {
    error.textContent = '検索に失敗しました。'; error.hidden = false;
  } finally {
    pending.restore();
  }
});
restoreSearchState(initialSearchState());
list.addEventListener('click', (event) => {
  const summary = event.target.closest('.thread-summary');
  if (summary) {
    const id = summary.closest('.thread-item').dataset.threadId;
    selectThread(id);
    openDetail(id);
  }
});
workspace.addEventListener('click', (event) => {
  const link = event.target.closest('[data-thread-placement-link]');
  if (!link) return;
  const latitude = Number(link.dataset.latitude);
  const longitude = Number(link.dataset.longitude);
  const zoom = Number(link.dataset.zoom || 15);
  if (![latitude, longitude, zoom].every(Number.isFinite)) return;
  event.preventDefault();
  closeDetail(false);
  const url = new URL(link.href, location.href);
  history.pushState({}, '', `${url.pathname}${url.search}${url.hash}`);
  map.easeTo({center: [longitude, latitude], zoom, duration: 700, essential: true});
});
createForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const pending = NiixyUI.beginPendingAction(event.submitter || createForm.querySelector('[type="submit"]'));
  if (!pending) return;
  let created = false;
  try {
    const response = await fetch(createForm.action, {method: 'POST', body: createFormData(), headers: {'X-Requested-With': 'XMLHttpRequest'}});
    const data = await response.json();
    if (response.ok) {
      created = true;
      saveResumeState(data.thread_id, true);
      location.assign(data.redirect_url);
      return;
    }
    const error = document.getElementById('thread-form-error');
    error.textContent = Object.values(data.errors || {}).flat().join(' ');
    error.hidden = false;
  } finally {
    if (!created) pending.restore();
  }
});
document.querySelectorAll('.thread-reply-form').forEach((form) => form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const pending = NiixyUI.beginPendingAction(event.submitter || form.querySelector('[type="submit"]'));
  if (!pending) return;
  let sent = false;
  const data = csrf(form);
  form.dataset.submissionId ||= crypto.randomUUID();
  data.append('submission_id', form.dataset.submissionId);
  try {
    const response = await fetch(form.action, {method: 'POST', body: data});
    const result = await response.json();
    if (response.ok) {
      sent = true;
      const threadId = form.closest('[data-thread-detail-pane]')?.dataset.threadDetailPane;
      if (threadId) saveResumeState(threadId);
      location.assign(result.redirect_url);
      return;
    }
  } finally {
    if (!sent) pending.restore();
  }
}));
document.getElementById('current-location-trigger').addEventListener('click', () => {
  navigator.geolocation?.getCurrentPosition(
    (position) => map.jumpTo({center: [position.coords.longitude, position.coords.latitude], zoom: 13}),
    () => window.alert('現在地を取得できませんでした。端末またはブラウザの位置情報設定を確認して、もう一度お試しください。'),
    {timeout: 10000, enableHighAccuracy: false},
  );
});
document.getElementById('location-search-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const query = document.getElementById('location-search-input').value.trim();
  if (query.length < 2) return;
  const response = await fetch(`/api/locations/?q=${encodeURIComponent(query)}`);
  const {locations} = await response.json();
  const results = document.getElementById('location-search-results');
  results.replaceChildren();
  if (!locations.length) {
    const item = document.createElement('li'); item.textContent = '見つかりませんでした。'; results.append(item); return;
  }
  locations.forEach((place) => {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = `${place.name} / ${place.detail}`;
    button.addEventListener('click', () => { map.easeTo({center: [place.longitude, place.latitude], zoom: 15, duration: 700, essential: true}); results.replaceChildren(); });
    item.append(button); results.append(item);
  });
});
map.on('click', (event) => {
  if (!creating) return;
  const coordinates = [event.lngLat.lng, event.lngLat.lat]; draftMarker?.remove(); draftMarker = new geolonia.Marker({color: '#d05b32'}).setLngLat(coordinates).addTo(map);
  document.getElementById('thread-latitude').value = event.lngLat.lat.toFixed(6); document.getElementById('thread-longitude').value = event.lngLat.lng.toFixed(6); document.getElementById('thread-location-status').textContent = '地点を選択しました。';
  document.getElementById('niimap-create-location-status').textContent = '地点を選択しました。'; openThreadCreate.disabled = false;
});
map.on('load', () => {
  if (!focusMapFromUrl()) restoreMapView();
  markers.forEach((thread) => { const marker = new geolonia.Marker({color: '#0f766e'}).setLngLat([thread.longitude, thread.latitude]).addTo(map); marker.getElement().classList.add('event-map-marker'); marker.getElement().addEventListener('click', () => { selectThread(thread.id, true); openDetail(thread.id); }); markerById.set(String(thread.id), marker); });
  applyFilters();
  map.on('moveend', () => {
    applyFilters();
  });
  if (initialThreadPane) selectThread(initialThreadId);
});
window.addEventListener('popstate', applyThreadStateFromUrl);
