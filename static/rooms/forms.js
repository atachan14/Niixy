window.NiixyRoomForms = (() => {
  function fieldControl(field, name, required) {
    const label = document.createElement('label');
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
    wrappers.filter((wrapper) => connected.has(wrapper.dataset.roomDefinitionId) && wrapper !== source)
      .forEach((wrapper) => writeFieldValues(wrapper, values));
  }

  function selectedModule(title) {
    const root = document.createElement('section');
    root.className = 'room-thread-selected';
    const header = document.createElement('div');
    header.className = 'room-thread-selected-header';
    const name = document.createElement('span');
    name.textContent = title;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = '×';
    remove.setAttribute('aria-label', `${title}を削除`);
    remove.addEventListener('click', () => root.remove());
    header.append(name, remove);
    const fields = document.createElement('div');
    fields.className = 'room-thread-selected-fields';
    root.append(header, fields);
    return {root, fields};
  }

  function initialize(root, fieldCatalog, interfaceCatalog) {
    root.querySelectorAll('[data-board-thread-create]:not([data-room-form-ready])').forEach((form) => {
      form.dataset.roomFormReady = 'true';
      const fieldPicker = form.querySelector('[data-room-field-picker]');
      const interfacePicker = form.querySelector('[data-room-interface-picker]');
      fieldPicker.add(new Option('Fieldを選択', ''));
      fieldCatalog.forEach((field) => fieldPicker.add(new Option(`${field.name}@${field.creator} v${field.version}`, field.id)));
      interfacePicker.add(new Option('ThreadIFを選択', ''));
      interfaceCatalog.forEach((item) => interfacePicker.add(new Option(`${item.name}@${item.creator} v${item.version}`, item.id)));

      form.querySelector('[data-add-room-field]').addEventListener('click', () => {
        const field = fieldCatalog.find((item) => item.id === Number(fieldPicker.value));
        if (!field || form.querySelector(`[data-room-direct-field="${field.id}"]`)) return;
        const selected = selectedModule(`${field.name}@${field.creator}`);
        selected.root.dataset.roomDirectField = field.id;
        const id = document.createElement('input');
        id.type = 'hidden';
        id.name = 'direct_field_ids';
        id.value = field.id;
        selected.fields.append(id, fieldControl(field, `direct_field_value_${field.key}`, true));
        form.querySelector('[data-room-direct-fields]').append(selected.root);
        fieldPicker.value = '';
      });

      form.querySelector('[data-add-room-interface]').addEventListener('click', () => {
        const item = interfaceCatalog.find((candidate) => candidate.id === Number(interfacePicker.value));
        if (!item || form.querySelector(`[data-room-interface="${item.id}"]`)) return;
        const selected = selectedModule(`${item.name}@${item.creator} v${item.version}/ThreadIF`);
        selected.root.dataset.roomInterface = item.id;
        const id = document.createElement('input');
        id.type = 'hidden';
        id.name = 'interface_ids';
        id.value = item.id;
        selected.fields.append(id);
        item.implementations.forEach((implementation) => implementation.fields.forEach((field) => {
          selected.fields.append(fieldControl(field, `interface_value_${implementation.id}_${field.key}`, field.required));
        }));
        form.querySelector('[data-room-thread-interfaces]').append(selected.root);
        interfacePicker.value = '';
      });
    });
  }

  return {initialize};
})();
