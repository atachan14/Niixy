const markers = JSON.parse(document.getElementById('thread-markers').textContent);
const boardMarkers = JSON.parse(document.getElementById('board-markers').textContent);
const roomMarkers = JSON.parse(document.getElementById('room-markers').textContent);
const interfaceCatalog = JSON.parse(document.getElementById('thread-interface-catalog-data').textContent);
const fieldCatalog = JSON.parse(document.getElementById('thread-field-catalog-data').textContent);
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
  room: 'is-room-open',
  'room-list': 'is-room-list-open',
  'room-board': 'is-room-board-open',
  'room-thread': 'is-room-thread-open',
});
const threadMotion = NiixyUI.createWorkspace(workspace, {
  list: {root: true},
  detail: {target: '.thread-detail-pane', width: 'remaining'},
  'interface-list': {target: '.thread-interface-list-pane:not(.thread-field-list-pane)', width: 'fixed'},
  'interface-detail': {target: '.thread-interface-detail-pane:not(.thread-field-detail-pane)', width: 'remaining'},
  'field-list': {target: '.thread-field-list-pane', width: 'fixed'},
  'field-detail': {target: '.thread-field-detail-pane', width: 'remaining'},
  'account-conditions': {target: '.account-condition-pane', width: 'fixed'},
  'account-selector': {target: '.account-selector-pane', width: 'fixed'},
  'account-condition-detail': {target: '.account-condition-detail-pane', width: 'remaining'},
  'account-condition-history-edit': {target: '.account-condition-detail-pane', width: 'remaining'},
  room: {target: '.thread-detail-pane', width: 'full'},
  'room-list': {target: '.niimap-room-list-pane', width: 'fixed'},
  'room-board': {target: '.niimap-room-thread-list-pane', width: 'fixed'},
  'room-thread': {target: '.niimap-room-thread-detail-pane', width: 'remaining'},
}, {track: document.querySelector('.thread-track')});
const list = document.getElementById('thread-list');
const createForm = document.getElementById('thread-create-form');
const boardCreateForm = document.getElementById('board-create-form');
const roomCreateForm = document.getElementById('room-create-form');
const searchControls = document.getElementById('niimap-search-controls');
const searchForm = document.getElementById('niimap-search-form');
const createControls = document.getElementById('niimap-create-controls');
const openThreadCreate = document.getElementById('open-thread-create');
const openBoardCreate = document.getElementById('open-board-create');
const openRoomCreate = document.getElementById('open-room-create');
const ruleDialog = document.getElementById('thread-rule-dialog');
const map = new geolonia.Map('#map');
const rootStyles = getComputedStyle(document.documentElement);
const threadMarkerColor = rootStyles.getPropertyValue('--spot-thread-color').trim() || '#0f766e';
const boardMarkerColor = rootStyles.getPropertyValue('--spot-board-color').trim() || '#2563eb';
const roomMarkerColor = rootStyles.getPropertyValue('--spot-room-color').trim() || '#a33b50';
function setThreadStage(stage) {
  threadStack.set(stage);
  threadMotion.set(stage);
  window.setTimeout(() => map.resize(), 260);
}
const markerById = new Map();
const resumeStorageKey = 'niixy:resume:niimap';
let draftMarker;
let creating = false;
let spotControlWindows;
const draftPlacementLinks = new Map(['thread', 'room', 'board'].map((kind) => {
  const link = document.getElementById(`${kind}-create-placement-link`);
  return [kind, {link, href: link.href}];
}));
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
let appliedRoomSearchIds = null;
let appliedBoardSearchIds = null;
let mapReady = false;
let mapFailed = false;
let searchReady = false;
let searchRequestId = 0;
let appliedSortKind = 'near';
let appliedSpotOrder = null;
let selectedSortField = null;
let activeRoomId = null;
let activeRoomBoard = null;
let roomRequestId = 0;
const accountConditions = NiixyAccountConditions.create({
  root: workspace,
  track: document.querySelector('.thread-track'),
  setStage: setThreadStage,
  historyStage: 'account-conditions',
  selectorStage: 'account-selector',
  detailStage: 'account-condition-detail',
  historyEditStage: 'account-condition-history-edit',
  defaultReturnStage: 'list',
  getReturnStage: () => threadStack.stage,
  fieldCatalog,
  authenticated: workspace.dataset.authenticated === 'true',
  currentAccount: workspace.dataset.currentActor,
  listUrl: workspace.dataset.accountConditionListUrl,
  saveUrl: workspace.dataset.accountConditionSaveUrl,
  deleteUrl: workspace.dataset.accountConditionDeleteUrl,
  accountSearchUrl: workspace.dataset.accountSearchUrl,
  roomSearchUrl: workspace.dataset.accountConditionRoomSearchUrl,
  csrfToken: () => searchForm.querySelector('[name="csrfmiddlewaretoken"]').value,
  extraDefaultCodes: (target) => target?.startsWith('board-policy-') ? ['guest', 'account'] : [],
  conditionKindAllowed: (kind, target) => !(target?.startsWith('board-policy-') || target?.startsWith('thread-policy-'))
    || ['default', 'account', 'room'].includes(kind),
  conditionAllowed: (condition, target) => !(target?.startsWith('board-policy-') || target?.startsWith('thread-policy-'))
    || condition.kind !== 'default'
    || ['guest', 'account', 'self'].includes(condition.definition.code),
});
threadMotion.onRetain = (stage) => {
  accountConditions.close();
  if (stage === 'list') {
    closeDetail(false);
    updateRoomUrl(null, {}, true);
  } else {
    roomRequestId += 1;
    const panes = ['.niimap-room-list-pane', '.niimap-room-thread-list-pane', '.niimap-room-thread-detail-pane'];
    const keep = {room: 0, 'room-list': 1, 'room-board': 2, 'room-thread': 3}[stage] || 0;
    panes.slice(keep).forEach((selector) => removeEmbeddedRoomPane(document.querySelector(selector)));
    threadStack.set(stage);
  }
};

function resetDraftPlacement() {
  draftMarker?.remove();
  draftMarker = null;
  ['thread', 'room', 'board'].forEach((kind) => {
    document.getElementById(`${kind}-latitude`).value = '';
    document.getElementById(`${kind}-longitude`).value = '';
    const placement = draftPlacementLinks.get(kind);
    placement.link.href = placement.href;
    placement.link.textContent = '';
    delete placement.link.dataset.latitude;
    delete placement.link.dataset.longitude;
  });
  document.getElementById('niimap-create-location-status').textContent = '地点を選択してください。';
  openThreadCreate.disabled = true;
  openRoomCreate.disabled = true;
  openBoardCreate.disabled = true;
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
const initialBoardId = new URLSearchParams(location.search).get('board');
const initialRoomId = new URLSearchParams(location.search).get('room');
const initialThreadId = /^\d+$/.test(initialRoomId || '') || /^\d+$/.test(initialBoardId || '') ? null : threadIdFromUrl();
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
  detailTitle.textContent = `${initialThreadPane.dataset.threadTitle}${initialThreadPane.dataset.threadPostCount === undefined ? '（閲覧不可）' : ` (${initialThreadPane.dataset.threadPostCount})`}`;
} else if (!initialRoomId && !initialBoardId) {
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
NiixyRoomForms.initialize(document, fieldCatalog, interfaceCatalog, {
  selectorHost: document.querySelector('.thread-track'),
  setStage: setThreadStage,
  returnStage: 'detail',
  currentAccount: workspace.dataset.currentActor,
  policyDialog: ruleDialog,
  beforeSelectorOpen: () => {
    document.getElementById('thread-interface-selector')?.remove();
    document.getElementById('thread-field-selector')?.remove();
    document.querySelector('.thread-interface-detail-pane:not(.thread-create-module-detail-pane):not(.thread-field-detail-pane)')?.remove();
    document.querySelector('.thread-field-detail-pane:not(.thread-create-module-detail-pane)')?.remove();
  },
});
function createFormData() {
  return csrf(createForm);
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
    document.querySelectorAll('#selected-direct-fields .thread-field-control[data-definition-id], #selected-thread-interfaces .thread-field-control[data-definition-id]'),
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
  button.dataset.summaryKind = 'field';
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
function applyFilters() {
  if (!mapReady || !searchReady) return;
  const bounds = map.getBounds();
  let visibleCount = 0;
  list.querySelectorAll('.thread-item').forEach((item) => {
    const thread = markers.find((candidate) => String(candidate.id) === item.dataset.threadId);
    const inSearch = appliedSearchIds === null || appliedSearchIds.has(item.dataset.threadId);
    const inBounds = item.dataset.threadViewable === 'false' || (thread && bounds.contains([thread.longitude, thread.latitude]));
    const visible = inSearch && inBounds;
    item.hidden = !visible;
    if (visible) visibleCount += 1;
    const marker = markerById.get(`thread:${item.dataset.threadId}`);
    if (marker) marker.getElement().hidden = !visible;
  });
  list.querySelectorAll('.room-item').forEach((item) => {
    const room = roomMarkers.find((candidate) => String(candidate.id) === item.dataset.roomId);
    const inSearch = appliedRoomSearchIds === null || appliedRoomSearchIds.has(item.dataset.roomId);
    const inBounds = room && bounds.contains([room.longitude, room.latitude]);
    const visible = inSearch && inBounds;
    item.hidden = !visible;
    if (visible) visibleCount += 1;
    const marker = markerById.get(`room:${item.dataset.roomId}`);
    if (marker) marker.getElement().hidden = !visible;
  });
  list.querySelectorAll('.board-item').forEach((item) => {
    const board = boardMarkers.find((candidate) => String(candidate.id) === item.dataset.boardId);
    const inSearch = appliedBoardSearchIds === null || appliedBoardSearchIds.has(item.dataset.boardId);
    const inBounds = item.dataset.boardViewable === 'false' || (board && bounds.contains([board.longitude, board.latitude]));
    const visible = inSearch && inBounds;
    item.hidden = !visible;
    if (visible) visibleCount += 1;
    const marker = markerById.get(`board:${item.dataset.boardId}`);
    if (marker) marker.getElement().hidden = !visible;
  });
  document.getElementById('thread-search-empty').hidden = visibleCount !== 0;
  if (appliedSortKind === 'near') sortByDistance();
  else if (appliedSpotOrder) {
    appliedSpotOrder.forEach(({kind, id}) => {
      const item = list.querySelector(`[data-${kind}-id="${id}"]`);
      if (item) list.append(item);
    });
  }
  list.hidden = false;
  document.getElementById('niimap-list-status').hidden = true;
  document.getElementById('niimap-list-retry').hidden = true;
}
function sortByDistance() {
  const center = map.getCenter();
  const distance = (spot) => spot ? (spot.latitude - center.lat) ** 2 + (spot.longitude - center.lng) ** 2 : Infinity;
  const spotFor = (item) => item.classList.contains('board-item')
    ? boardMarkers.find((board) => String(board.id) === item.dataset.boardId)
    : item.classList.contains('room-item')
    ? roomMarkers.find((room) => String(room.id) === item.dataset.roomId)
    : markers.find((thread) => String(thread.id) === item.dataset.threadId);
  Array.from(list.querySelectorAll('.thread-item, .room-item, .board-item')).sort((first, second) => {
    return distance(spotFor(first)) - distance(spotFor(second));
  }).forEach((item) => list.append(item));
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
      button.dataset.summaryKind = 'interface';
      button.innerHTML = `<span class="ui-summary-item-context"></span><strong class="ui-summary-item-title"></strong><small class="ui-summary-item-updated"></small>`;
      button.querySelector('strong').textContent = `${item.name}@${item.creator} v${item.version}/${item.kind}`;
      button.querySelector('small').textContent = `最終更新 ${new Date(item.updated_at).toLocaleString('ja-JP')}`;
      button.addEventListener('click', () => renderInterfacePreview(item.id)); results.append(button);
    });
  };
  input.addEventListener('input', render); panel.append(input, results); render();
}
function defaultAccountCondition(code) {
  return accountConditions.defaultCondition(code) || null;
}
function searchConditions() {
  return {
    creator_include_groups: accountConditions.getGroups('creator-include'),
    creator_exclude_groups: accountConditions.getGroups('creator-exclude'),
    policy: Array.from(document.querySelectorAll('.niimap-policy-condition')).map((row) => ({
      capability: row.dataset.policyCapability,
      decision: row.dataset.policyDecision,
      account_groups: accountConditions.getGroups(row.dataset.policyTarget),
    })).filter((condition) => condition.account_groups.length),
    fields: Array.from(document.querySelectorAll('[data-condition-kind="field"]')).map((row) => ({field_id: Number(row.dataset.fieldId), operator: row.querySelector('[name="operator"]').value, value: row.querySelector('[name="value"]').value})),
    interfaces: Array.from(document.querySelectorAll('[data-condition-kind="interface"]')).map((row) => ({interface_id: Number(row.dataset.interfaceId), operator: row.querySelector('[name="operator"]').value})),
  };
}
function restoreSearchState(state) {
  searchForm.reset(); selectedSortField = null;
  accountConditions.reset();
  document.querySelectorAll('#niimap-field-conditions, #niimap-interface-conditions').forEach((list) => list.replaceChildren());
  if (state) Object.entries(state).forEach(([name, value]) => { if (name !== 'conditions' && name !== 'sort_field_id' && searchForm.elements[name]) searchForm.elements[name].value = value; });
  accountConditions.setGroups('creator-include', state?.conditions?.creator_include_groups || []);
  accountConditions.setGroups('creator-exclude', state?.conditions?.creator_exclude_groups || []);
  document.querySelectorAll('.niimap-policy-condition').forEach((row) => {
    const condition = (state?.conditions?.policy || []).find((item) => (
      item.capability === row.dataset.policyCapability && item.decision === row.dataset.policyDecision
    ));
    const groups = condition?.account_groups || (condition?.actor ? [[defaultAccountCondition(condition.actor)]] : []);
    accountConditions.setGroups(row.dataset.policyTarget, groups.filter((group) => group.every(Boolean)));
  });
  (state?.conditions?.fields || []).forEach((condition) => { const field = fieldCatalog.find((item) => item.id === Number(condition.field_id)); if (field) addFieldCondition(field, condition); });
  (state?.conditions?.interfaces || []).forEach((condition) => { const item = interfaceCatalog.find((candidate) => candidate.id === Number(condition.interface_id)); if (item) addInterfaceCondition(item, condition); });
  if (state?.sort_field_id) {
    selectedSortField = fieldCatalog.find((field) => field.id === Number(state.sort_field_id)) || null;
  }
  const sortButton = searchForm.querySelector('[data-search-select="sort-field"]');
  sortButton.textContent = selectedSortField ? `${selectedSortField.name}@${selectedSortField.creator}` : 'Fieldを選択';
  updateSortControls();
}
function emptySearchState() {
  return {sort_kind: 'near', sort_direction: 'desc', target_type: 'all', updated_value: '', updated_operator: 'after', freeword_include: '', freeword_exclude: '', sort_field_id: '', conditions: {creator_include_groups: [], creator_exclude_groups: [], policy: [], fields: [], interfaces: []}};
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
function scrollThreadSummaryIntoView(item) {
  if (!item) return;
  const isMobile = window.matchMedia('(max-width: 780px)').matches;
  const container = item.closest(isMobile ? '.thread-map-list-pane' : '.thread-list-pane');
  if (!container) {
    item.scrollIntoView({block: 'nearest', inline: 'nearest'});
    return;
  }
  const itemRect = item.getBoundingClientRect();
  const containerRect = container.getBoundingClientRect();
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  container.scrollTo({
    top: Math.max(0, container.scrollTop + itemRect.top - containerRect.top - 12),
    behavior: reduceMotion ? 'auto' : 'smooth',
  });
}
function selectThread(id, scroll = false) {
  list.querySelectorAll('.thread-item').forEach((item) => {
    const selected = item.dataset.threadId === String(id);
    const summary = item.querySelector('.thread-summary');
    summary?.classList.toggle('is-selected', selected);
    if (selected) summary?.setAttribute('aria-current', 'true');
    else summary?.removeAttribute('aria-current');
  });
  list.querySelectorAll('.room-summary, .board-summary').forEach((summary) => {
    summary.classList.remove('is-selected');
    summary.removeAttribute('aria-current');
  });
  markerById.forEach((marker, markerId) => marker.getElement().classList.toggle('is-highlighted', markerId === `thread:${id}`));
  showThreadMarker(id);
  const item = list.querySelector(`[data-thread-id="${id}"]`);
  if (scroll) scrollThreadSummaryIntoView(item);
}
function selectRoom(id, scroll = false) {
  list.querySelectorAll('.thread-summary, .board-summary').forEach((summary) => {
    summary.classList.remove('is-selected');
    summary.removeAttribute('aria-current');
  });
  list.querySelectorAll('.room-item').forEach((item) => {
    const selected = item.dataset.roomId === String(id);
    const summary = item.querySelector('.room-summary');
    summary?.classList.toggle('is-selected', selected);
    if (selected) summary?.setAttribute('aria-current', 'true');
    else summary?.removeAttribute('aria-current');
  });
  markerById.forEach((marker, markerId) => marker.getElement().classList.toggle('is-highlighted', markerId === `room:${id}`));
  const item = list.querySelector(`[data-room-id="${id}"]`);
  if (scroll) scrollThreadSummaryIntoView(item);
}
function selectBoard(id, scroll = false) {
  list.querySelectorAll('.spot-summary').forEach((summary) => {
    const selected = summary.closest('.board-item')?.dataset.boardId === String(id);
    summary.classList.toggle('is-selected', selected);
    if (selected) summary.setAttribute('aria-current', 'true'); else summary.removeAttribute('aria-current');
  });
  markerById.forEach((marker, markerId) => marker.getElement().classList.toggle('is-highlighted', markerId === `board:${id}`));
  if (scroll) scrollThreadSummaryIntoView(list.querySelector(`.board-item[data-board-id="${id}"]`));
}
workspace.addEventListener('niimap-board-select', (event) => selectBoard(event.detail));
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
function roomTemplateUrl(template, id) {
  return template.replace('/0/', `/${id}/`);
}
function removeEmbeddedRoomPane(pane) {
  if (!pane) return;
  document.querySelectorAll('.thread-create-module-selector-pane').forEach((selector) => {
    if (selector.workspaceOwner === pane || pane.contains(selector.workspaceOwner)) selector.remove();
  });
  pane.remove();
}
function removeEmbeddedRoomPanes(includeOverview = true) {
  roomRequestId += 1;
  document.querySelectorAll('.niimap-room-list-pane, .niimap-room-thread-list-pane, .niimap-room-thread-detail-pane').forEach(removeEmbeddedRoomPane);
  if (includeOverview) document.querySelector('.thread-detail-pane [data-room-fragment]')?.remove();
  activeRoomBoard = null;
  if (includeOverview) activeRoomId = null;
}
function updateRoomUrl(roomId, values = {}, replace = false) {
  const url = new URL(location.href);
  ['thread', 'room', 'room_list', 'board'].forEach((name) => url.searchParams.delete(name));
  if (roomId) {
    url.searchParams.set('room', roomId);
    Object.entries(values).forEach(([name, value]) => {
      if (value !== null && value !== undefined && value !== '') url.searchParams.set(name, value);
    });
  }
  history[replace ? 'replaceState' : 'pushState']({}, '', url);
}
function createRoomPane(className, title, closeLabel) {
  const pane = document.createElement('section');
  pane.className = `ui-list-pane ${className}`;
  const header = document.createElement('header');
  header.className = 'ui-pane-header ui-list-pane-header';
  const heading = document.createElement('h2');
  heading.textContent = title;
  const close = document.createElement('button');
  close.className = 'icon-button';
  close.type = 'button';
  close.textContent = '×';
  close.setAttribute('aria-label', closeLabel);
  const actions = document.createElement('div');
  actions.className = 'ui-pane-header-actions';
  actions.append(close);
  const content = document.createElement('div');
  content.innerHTML = '<p class="room-pane-loading">読み込み中...</p>';
  header.append(heading, actions);
  pane.append(header, content);
  document.querySelector('.thread-track').append(pane);
  return {pane, heading, actions, close, content};
}
function activeRoomFragment() {
  return document.querySelector('.thread-detail-pane [data-room-fragment]');
}
async function openRoom(id, shouldUpdateUrl = true) {
  removeEmbeddedRoomPanes();
  const current = ++roomRequestId;
  activeRoomId = String(id);
  creating = false;
  createForm.hidden = true;
  roomCreateForm.hidden = true;
  boardCreateForm.hidden = true;
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  detailTitle.textContent = '読み込み中...';
  setThreadStage('room');
  document.querySelector('.thread-detail-pane').scrollTo({top: 0});
  if (shouldUpdateUrl) updateRoomUrl(activeRoomId);
  try {
    const pane = await NiixyUI.fetchFragment(roomTemplateUrl(workspace.dataset.roomPaneTemplate, activeRoomId));
    if (current !== roomRequestId || activeRoomId !== String(id)) return false;
    document.querySelector('.thread-detail-pane').append(pane);
    detailTitle.textContent = pane.dataset.roomTitle;
    pane.querySelector('[data-open-room-members]')?.addEventListener('click', () => openEmbeddedRoomList('参加者一覧', pane.dataset.membersUrl, 'members'));
    pane.querySelector('[data-open-room-boards]')?.addEventListener('click', () => openEmbeddedRoomList('Board一覧', pane.dataset.boardsUrl, 'boards'));
    return true;
  } catch {
    if (current === roomRequestId) detailTitle.textContent = 'Roomの読み込みに失敗しました';
    return false;
  }
}
async function openEmbeddedRoomList(title, url, kind, shouldUpdateUrl = true) {
  const current = ++roomRequestId;
  document.querySelectorAll('.niimap-room-list-pane, .niimap-room-thread-list-pane, .niimap-room-thread-detail-pane').forEach(removeEmbeddedRoomPane);
  activeRoomBoard = null;
  const ui = createRoomPane('niimap-room-list-pane', title, 'Roomに戻る');
  ui.close.addEventListener('click', () => {
    roomRequestId += 1;
    removeEmbeddedRoomPane(ui.pane);
    setThreadStage('room');
    updateRoomUrl(activeRoomId);
  });
  setThreadStage('room-list');
  if (shouldUpdateUrl) updateRoomUrl(activeRoomId, {room_list: kind});
  try {
    const response = await fetch(url, {cache: 'no-store', headers: {'X-Requested-With': 'fetch'}});
    if (!response.ok) throw new Error();
    const html = await response.text();
    if (current !== roomRequestId) return;
    ui.content.innerHTML = html;
    NiixyUI.bindTabs(ui.content);
    ui.content.addEventListener('click', (event) => {
      const board = event.target.closest('[data-open-board]');
      if (board) openEmbeddedBoard(board.dataset.openBoard, board.dataset.boardTitle, board.dataset.boardUrl);
    });
  } catch {
    if (current === roomRequestId) ui.content.innerHTML = '<p class="empty">読み込みに失敗しました。</p>';
  }
}
async function openEmbeddedBoard(boardId, title, url, shouldUpdateUrl = true) {
  const current = ++roomRequestId;
  document.querySelectorAll('.niimap-room-thread-list-pane, .niimap-room-thread-detail-pane').forEach(removeEmbeddedRoomPane);
  activeRoomBoard = {id: String(boardId), title, url};
  const ui = createRoomPane('niimap-room-thread-list-pane', title, 'Board一覧に戻る');
  ui.close.addEventListener('click', () => {
    roomRequestId += 1;
    removeEmbeddedRoomPane(ui.pane);
    removeEmbeddedRoomPane(document.querySelector('.niimap-room-thread-detail-pane'));
    activeRoomBoard = null;
    setThreadStage('room-list');
    updateRoomUrl(activeRoomId, {room_list: 'boards'});
  });
  setThreadStage('room-board');
  if (shouldUpdateUrl) updateRoomUrl(activeRoomId, {room_list: 'boards', board: activeRoomBoard.id});
  try {
    const response = await fetch(url, {cache: 'no-store', headers: {'X-Requested-With': 'fetch'}});
    if (!response.ok) throw new Error();
    const html = await response.text();
    if (current !== roomRequestId) return;
    ui.content.innerHTML = html;
    NiixyRoomForms.initialize(ui.content, fieldCatalog, interfaceCatalog, {
      selectorHost: document.querySelector('.thread-track'),
      setStage: setThreadStage,
      returnStage: 'room-board',
      currentAccount: workspace.dataset.currentActor,
      policyDialog: ruleDialog,
      beforeSelectorOpen: () => {
        NiixyWorkspaceTrail.prepare(ui.content);
        document.getElementById('thread-interface-selector')?.remove();
        document.getElementById('thread-field-selector')?.remove();
        document.querySelector('.thread-interface-detail-pane:not(.thread-create-module-detail-pane):not(.thread-field-detail-pane)')?.remove();
        document.querySelector('.thread-field-detail-pane:not(.thread-create-module-detail-pane)')?.remove();
      },
    });
    ui.content.addEventListener('click', (event) => {
      const thread = event.target.closest('[data-room-thread]');
      if (thread) openEmbeddedRoomThread(thread.dataset.roomThread);
    });
  } catch {
    if (current === roomRequestId) ui.content.innerHTML = '<p class="empty">読み込みに失敗しました。</p>';
  }
}
async function openEmbeddedRoomThread(threadId, shouldUpdateUrl = true) {
  const fragment = activeRoomFragment();
  if (!fragment || !activeRoomBoard) return;
  const current = ++roomRequestId;
  removeEmbeddedRoomPane(document.querySelector('.niimap-room-thread-detail-pane'));
  const ui = createRoomPane('niimap-room-thread-detail-pane', '', 'Thread一覧に戻る');
  ui.pane.classList.remove('ui-list-pane');
  ui.pane.classList.add('ui-detail-pane');
  ui.close.addEventListener('click', () => {
    roomRequestId += 1;
    removeEmbeddedRoomPane(ui.pane);
    setThreadStage('room-board');
    updateRoomUrl(activeRoomId, {room_list: 'boards', board: activeRoomBoard.id});
  });
  setThreadStage('room-thread');
  if (shouldUpdateUrl) updateRoomUrl(activeRoomId, {room_list: 'boards', board: activeRoomBoard.id, thread: threadId});
  try {
    const response = await fetch(roomTemplateUrl(fragment.dataset.threadDetailTemplate, threadId), {headers: {'X-Requested-With': 'fetch'}});
    if (!response.ok) throw new Error();
    const html = await response.text();
    if (current !== roomRequestId) return;
    ui.content.innerHTML = html;
    ui.heading.textContent = ui.content.querySelector('[data-thread-title]')?.dataset.threadTitle || '';
  } catch {
    if (current === roomRequestId) ui.content.innerHTML = '<p class="empty">読み込みに失敗しました。</p>';
  }
}
function updateThreadUrl(id, replace = false) {
  const url = new URL(location.href);
  const threadId = id ? String(id) : null;
  ['room', 'room_list', 'board'].forEach((name) => url.searchParams.delete(name));
  if (url.searchParams.get('thread') === threadId) return;
  if (threadId) url.searchParams.set('thread', threadId);
  else url.searchParams.delete('thread');
  history[replace ? 'replaceState' : 'pushState']({}, '', url);
}
function openDetail(id, shouldUpdateUrl = true) {
  const pane = document.querySelector(`[data-thread-detail-pane="${id}"]`);
  if (!pane) return false;
  removeEmbeddedRoomPanes();
  spotControlWindows?.set('create', false);
  creating = false;
  createForm.hidden = true;
  roomCreateForm.hidden = true;
  boardCreateForm.hidden = true;
  setThreadStage('detail');
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => {
    const selected = pane.dataset.threadDetailPane === String(id);
    pane.hidden = !selected;
    if (selected) detailTitle.textContent = `${pane.dataset.threadTitle}${pane.dataset.threadPostCount === undefined ? '（閲覧不可）' : ` (${pane.dataset.threadPostCount})`}`;
  });
  document.querySelector('.thread-detail-pane').scrollTo({top: 0});
  if (shouldUpdateUrl) updateThreadUrl(id);
  return true;
}
function closeDetail(shouldUpdateUrl = true) {
  removeEmbeddedRoomPanes();
  setThreadStage('list');
  createForm.hidden = true;
  roomCreateForm.hidden = true;
  boardCreateForm.hidden = true;
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  markerById.forEach((marker) => marker.getElement().classList.remove('is-highlighted'));
  list.querySelectorAll('.thread-summary, .board-summary').forEach((summary) => {
    summary.classList.remove('is-selected');
    summary.removeAttribute('aria-current');
  });
  list.querySelectorAll('.room-summary, .board-summary').forEach((summary) => {
    summary.classList.remove('is-selected');
    summary.removeAttribute('aria-current');
  });
  detailTitle.textContent = '';
  if (shouldUpdateUrl) updateRoomUrl(null);
}
async function applyThreadStateFromUrl() {
  const url = new URL(location.href);
  const roomId = url.searchParams.get('room');
  const boardId = url.searchParams.get('board');
  if (!roomId && /^\d+$/.test(boardId || '')) {
    closeDetail(false);
    selectBoard(boardId, true);
    await NiixyWorkspaceTrail.openMapBoard(boardId, list, url.searchParams.get('thread'));
    return;
  }
  if (/^\d+$/.test(roomId || '')) {
    selectRoom(roomId, true);
    if (!await openRoom(roomId, false)) {
      closeDetail(false);
      updateRoomUrl(null, {}, true);
      return;
    }
    const listKind = url.searchParams.get('room_list');
    const fragment = activeRoomFragment();
    if (!listKind || !fragment) return;
    const listUrl = listKind === 'members' ? fragment.dataset.membersUrl : fragment.dataset.boardsUrl;
    await openEmbeddedRoomList(listKind === 'members' ? '参加者一覧' : 'Board一覧', listUrl, listKind, false);
    const boardId = url.searchParams.get('board');
    if (!boardId) return;
    const board = document.querySelector(`.niimap-room-list-pane [data-open-board="${boardId}"]`);
    if (!board) return;
    await openEmbeddedBoard(boardId, board.dataset.boardTitle, board.dataset.boardUrl, false);
    const roomThreadId = url.searchParams.get('thread');
    if (roomThreadId) await openEmbeddedRoomThread(roomThreadId, false);
    return;
  }
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
spotControlWindows = NiixyUI.createExclusivePanels(document.getElementById('niimap-control-windows'), {
  create: {
    toggle: '#niimap-create-toggle',
    panel: createControls,
    label: '新規作成',
    onOpen: () => { creating = true; },
    onClose: () => {
      creating = false;
      resetDraftPlacement();
    },
  },
  search: {
    toggle: '#niimap-search-toggle',
    panel: searchControls,
    label: '検索',
  },
});
openThreadCreate.addEventListener('click', () => {
  if (openThreadCreate.disabled) return;
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  roomCreateForm.hidden = true;
  boardCreateForm.hidden = true;
  createForm.hidden = false; detailTitle.textContent = 'Threadを作成';
  setThreadStage('detail');
});
openBoardCreate.addEventListener('click', () => {
  if (openBoardCreate.disabled) return;
  NiixyWorkspaceTrail.prepare(boardCreateForm);
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  createForm.hidden = true; roomCreateForm.hidden = true;
  boardCreateForm.hidden = false; detailTitle.textContent = 'Boardを作成';
  setThreadStage('detail');
});
openRoomCreate.addEventListener('click', () => {
  if (openRoomCreate.disabled) return;
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  createForm.hidden = true;
  roomCreateForm.hidden = false;
  boardCreateForm.hidden = true;
  detailTitle.textContent = 'Roomを作成';
  setThreadStage('detail');
});
document.getElementById('close-thread-detail').addEventListener('click', () => {
  closeDetail();
  sessionStorage.removeItem(resumeStorageKey);
});
function updateSortControls() {
  const fieldSort = searchForm.elements.sort_kind.value === 'field';
  searchForm.querySelector('[data-search-select="sort-field"]').disabled = !fieldSort;
  searchForm.elements.sort_direction.disabled = !fieldSort;
}
searchForm.elements.sort_kind.addEventListener('change', updateSortControls);
searchForm.querySelectorAll('[data-search-select]').forEach((button) => button.addEventListener('click', () => {
  searchSelectionTarget = button.dataset.searchSelect;
  if (searchSelectionTarget === 'interface') openInterfaceSelector(null, 'search');
  else openFieldSelector(null, 'search');
}));
document.getElementById('niimap-search-reset').addEventListener('click', () => restoreSearchState(emptySearchState()));
async function runSpotSearch(initial = false) {
  const pending = NiixyUI.beginPendingAction(searchForm.querySelector('[type="submit"]'));
  if (!pending) return;
  const current = ++searchRequestId;
  const error = document.getElementById('niimap-search-error'); error.hidden = true; error.textContent = '';
  const status = document.getElementById('niimap-list-status');
  const retry = document.getElementById('niimap-list-retry');
  if (initial) { list.hidden = true; status.hidden = false; status.textContent = '読み込み中...'; retry.hidden = true; }
  const data = new FormData(searchForm); const conditions = searchConditions();
  data.append('creator_include_groups', JSON.stringify(conditions.creator_include_groups));
  data.append('creator_exclude_groups', JSON.stringify(conditions.creator_exclude_groups));
  data.append('policy_conditions', JSON.stringify(conditions.policy));
  data.append('field_conditions', JSON.stringify(conditions.fields));
  data.append('interface_conditions', JSON.stringify(conditions.interfaces));
  data.append('sort_field_id', selectedSortField?.id || '');
  data.set('sort_direction', searchForm.elements.sort_direction.value);
  try {
    const response = await fetch(workspace.dataset.searchUrl, {method: 'POST', body: data, headers: {'X-Requested-With': 'XMLHttpRequest'}});
    const result = await response.json();
    if (current !== searchRequestId) return;
    if (!response.ok) throw new Error(result.error || Object.values(result.errors || {}).flat().join(' ') || '検索に失敗しました。');
    appliedSearchIds = new Set(result.thread_ids.map(String));
    appliedRoomSearchIds = new Set((result.room_ids || []).map(String));
    appliedBoardSearchIds = new Set((result.board_ids || []).map(String));
    appliedSpotOrder = (result.spot_order || []).map((spot) => ({kind: spot.kind, id: String(spot.id)}));
    appliedSortKind = data.get('sort_kind'); searchReady = true;
    applyFilters();
    retry.hidden = mapReady || !mapFailed;
    if (!initial) spotControlWindows.set('search', false);
  } catch (exception) {
    if (current !== searchRequestId) return;
    error.textContent = exception.message || '検索に失敗しました。'; error.hidden = false;
    if (initial) { status.hidden = false; status.textContent = error.textContent; retry.hidden = false; }
  } finally { pending.restore(); }
}
searchForm.addEventListener('submit', (event) => { event.preventDefault(); runSpotSearch(!searchReady); });
document.getElementById('niimap-list-retry').addEventListener('click', () => {
  if (!mapReady && mapFailed) location.reload();
  else runSpotSearch(true);
});
restoreSearchState(initialSearchState());
runSpotSearch(true);
list.addEventListener('click', (event) => {
  const roomSummary = event.target.closest('.room-summary');
  if (roomSummary) {
    event.preventDefault();
    const id = roomSummary.closest('.room-item').dataset.roomId;
    selectRoom(id);
    openRoom(id);
    return;
  }
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
workspace.addEventListener('submit', async (event) => {
  const roomAction = event.target.closest('[data-room-fragment] [data-room-action]');
  const boardAction = event.target.closest('.niimap-room-list-pane [data-board-action], .niimap-room-thread-list-pane [data-board-action]');
  const boardCreate = event.target.closest('.niimap-room-thread-list-pane [data-board-thread-create]');
  const roomReply = event.target.closest('.niimap-room-thread-detail-pane .thread-reply-form');
  if (roomReply) {
    event.preventDefault();
    const result = await NiixyUI.submitThreadReply(roomReply, event.submitter);
    const threadId = roomReply.closest('[data-thread-id]')?.dataset.threadId;
    if (result && threadId) await openEmbeddedRoomThread(threadId, false);
    return;
  }
  const form = roomAction || boardAction || boardCreate || roomReply;
  if (!form) return;
  event.preventDefault();
  if (form.dataset.confirmMessage && !window.confirm(form.dataset.confirmMessage)) return;
  const pending = NiixyUI.beginPendingAction(event.submitter || form.querySelector('[type="submit"]'));
  if (!pending) return;
  const data = new FormData(form);
  const error = form.querySelector('.room-form-error, .reply-form-error');
  if (error) error.hidden = true;
  try {
    const response = await fetch(form.action, {method: 'POST', body: data});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || Object.values(result.errors || {}).flat().join(' '));
    if (roomAction) {
      const roomId = activeRoomId;
      await openRoom(roomId, false);
      updateRoomUrl(roomId, {}, true);
    }
    else if (boardAction) {
      const fragment = activeRoomFragment();
      if (!fragment) return;
      await openEmbeddedRoomList('Board一覧', fragment.dataset.boardsUrl, 'boards', false);
      if (boardAction.dataset.boardActionKind !== 'delete') {
        const board = document.querySelector(`.niimap-room-list-pane [data-open-board="${result.board_id}"]`);
        if (board) await openEmbeddedBoard(result.board_id, board.querySelector('.ui-summary-item-title').textContent, board.dataset.boardUrl, false);
      }
      updateRoomUrl(activeRoomId, boardAction.dataset.boardActionKind === 'delete' ? {room_list: 'boards'} : {room_list: 'boards', board: result.board_id}, true);
    }
    else if (boardCreate) {
      const board = {...activeRoomBoard};
      await openEmbeddedBoard(board.id, board.title, board.url, false);
      await openEmbeddedRoomThread(result.thread_id);
    }
  } catch (exception) {
    if (error) {
      error.textContent = exception.message || '処理に失敗しました。';
      error.hidden = false;
    }
    pending.restore();
  }
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
boardCreateForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const pending = NiixyUI.beginPendingAction(event.submitter || boardCreateForm.querySelector('[type="submit"]'));
  if (!pending) return;
  const error = boardCreateForm.querySelector('.event-form-error'); error.hidden = true;
  try {
    const response = await fetch(boardCreateForm.action, {method: 'POST', body: new FormData(boardCreateForm)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || Object.values(result.errors || {}).flat().join(' '));
    location.assign(result.redirect_url);
  } catch (exception) {
    error.textContent = exception.message || 'Boardの作成に失敗しました。'; error.hidden = false;
    pending.restore();
  }
});
roomCreateForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const pending = NiixyUI.beginPendingAction(event.submitter || roomCreateForm.querySelector('[type="submit"]'));
  if (!pending) return;
  let created = false;
  try {
    const response = await fetch(roomCreateForm.action, {method: 'POST', body: new FormData(roomCreateForm), headers: {'X-Requested-With': 'XMLHttpRequest'}});
    const data = await response.json();
    if (response.ok) {
      created = true;
      location.assign(data.redirect_url);
      return;
    }
    const error = document.getElementById('room-form-error');
    error.textContent = data.error || Object.values(data.errors || {}).flat().join(' ');
    error.hidden = false;
  } finally {
    if (!created) pending.restore();
  }
});
document.querySelectorAll('.thread-reply-form').forEach((form) => form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const result = await NiixyUI.submitThreadReply(form, event.submitter);
  if (!result) return;
  const threadId = form.closest('[data-thread-detail-pane]')?.dataset.threadDetailPane;
  if (threadId) saveResumeState(threadId);
  location.assign(result.redirect_url);
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
  const latitude = event.lngLat.lat.toFixed(6);
  const longitude = event.lngLat.lng.toFixed(6);
  ['thread', 'room', 'board'].forEach((kind) => {
    document.getElementById(`${kind}-latitude`).value = latitude;
    document.getElementById(`${kind}-longitude`).value = longitude;
    const placementLink = document.getElementById(`${kind}-create-placement-link`);
    const placementUrl = new URL(placementLink.href, location.href);
    placementUrl.searchParams.set('latitude', latitude);
    placementUrl.searchParams.set('longitude', longitude);
    placementUrl.searchParams.set('zoom', '15');
    placementLink.href = placementUrl;
    placementLink.dataset.latitude = latitude;
    placementLink.dataset.longitude = longitude;
    placementLink.textContent = `${latitude}, ${longitude}`;
  });
  document.getElementById('niimap-create-location-status').textContent = '地点を選択しました。';
  openThreadCreate.disabled = false;
  openBoardCreate.disabled = false;
  openRoomCreate.disabled = workspace.dataset.authenticated !== 'true';
});
map.on('error', () => {
  if (mapReady) return;
  mapFailed = true;
  const status = document.getElementById('niimap-list-status');
  status.hidden = false; status.textContent = '地図の読み込みに失敗しました。';
  document.getElementById('niimap-list-retry').hidden = false;
});
map.on('load', () => {
  mapReady = true;
  mapFailed = false;
  if (!focusMapFromUrl()) restoreMapView();
  markers.forEach((thread) => {
    const marker = new geolonia.Marker({color: threadMarkerColor}).setLngLat([thread.longitude, thread.latitude]).addTo(map);
    marker.getElement().classList.add('event-map-marker');
    marker.getElement().addEventListener('click', (event) => {
      event.stopPropagation();
      selectThread(thread.id, true);
    });
    markerById.set(`thread:${thread.id}`, marker);
  });
  roomMarkers.forEach((room) => {
    const marker = new geolonia.Marker({color: roomMarkerColor}).setLngLat([room.longitude, room.latitude]).addTo(map);
    marker.getElement().classList.add('event-map-marker', 'room-map-marker');
    marker.getElement().addEventListener('click', (event) => {
      event.stopPropagation();
      selectRoom(room.id, true);
    });
    markerById.set(`room:${room.id}`, marker);
  });
  boardMarkers.forEach((board) => {
    const marker = new geolonia.Marker({color: boardMarkerColor}).setLngLat([board.longitude, board.latitude]).addTo(map);
    marker.getElement().classList.add('event-map-marker', 'board-map-marker');
    marker.getElement().addEventListener('click', (event) => {
      event.stopPropagation(); selectBoard(board.id, true);
    });
    markerById.set(`board:${board.id}`, marker);
  });
  applyFilters();
  map.on('moveend', () => {
    applyFilters();
  });
  if (initialThreadPane) selectThread(initialThreadId);
});
window.addEventListener('popstate', applyThreadStateFromUrl);
if (/^\d+$/.test(initialRoomId || '') || /^\d+$/.test(initialBoardId || '')) {
  applyThreadStateFromUrl().finally(() => requestAnimationFrame(() => requestAnimationFrame(() => {
    document.documentElement.classList.remove('has-restored-niimap-workspace');
  })));
}
