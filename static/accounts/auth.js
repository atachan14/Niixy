const authDialog = document.getElementById('auth-dialog');
const authDialogTitle = document.getElementById('auth-dialog-title');
const authForms = document.querySelectorAll('.auth-form');
const authTabs = document.querySelectorAll('[data-auth-tab]');

function clearAuthErrors(form) {
  form.querySelectorAll('.field-error').forEach((error) => error.remove());
  const formError = form.querySelector('.auth-form-error');
  formError.hidden = true;
  formError.textContent = '';
}

function showAuthErrors(form, errors) {
  clearAuthErrors(form);

  Object.entries(errors).forEach(([fieldName, messages]) => {
    const message = messages.join(' ');
    const input = form.elements.namedItem(fieldName);
    const field = input && input.closest('.field');
    if (!field) {
      const formError = form.querySelector('.auth-form-error');
      formError.textContent = message;
      formError.hidden = false;
      return;
    }

    const error = document.createElement('p');
    error.className = 'field-error';
    error.textContent = message;
    field.append(error);
  });
}

function setAuthMode(mode) {
  const isSignup = mode === 'signup';
  authDialogTitle.textContent = isSignup ? '新規登録' : 'ログイン';
  authForms.forEach((form) => {
    const isActive = form.id === `${mode}-form`;
    form.hidden = !isActive;
    if (isActive) clearAuthErrors(form);
  });
  authTabs.forEach((tab) => tab.setAttribute('aria-selected', String(tab.dataset.authTab === mode)));
}

document.querySelectorAll('[data-auth-mode]').forEach((trigger) => {
  trigger.addEventListener('click', () => {
    setAuthMode(trigger.dataset.authMode);
    authDialog.showModal();
  });
});

authTabs.forEach((tab) => tab.addEventListener('click', () => setAuthMode(tab.dataset.authTab)));
document.getElementById('auth-dialog-close').addEventListener('click', () => authDialog.close());

authDialog.addEventListener('click', (event) => {
  if (event.target === authDialog) authDialog.close();
});

authForms.forEach((form) => {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearAuthErrors(form);

    const response = await fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    const data = await response.json();

    if (response.ok) {
      window.location.reload();
      return;
    }

    showAuthErrors(form, data.errors || {});
  });
});
