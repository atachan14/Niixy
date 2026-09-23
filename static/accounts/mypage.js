const myPage = document.querySelector('.mypage');
const basicInfoButton = document.getElementById('open-basic-info');
const closeBasicInfoButton = document.getElementById('close-basic-info');
const displayNameInput = document.getElementById('id_display_name');
const myPageIdentity = document.getElementById('mypage-identity');
const myPageContext = document.getElementById('mypage-context');

function updateMyPageContext() {
  const isBasicInfoOpen = myPage.classList.contains('is-basic-info-open');
  myPageIdentity.disabled = !isBasicInfoOpen;
  myPageContext.hidden = !isBasicInfoOpen;
}

function openBasicInfo() {
  myPage.classList.add('is-basic-info-open');
  updateMyPageContext();
  window.setTimeout(() => displayNameInput.focus(), 260);
}

basicInfoButton.addEventListener('click', openBasicInfo);
closeBasicInfoButton.addEventListener('click', () => {
  myPage.classList.remove('is-basic-info-open');
  updateMyPageContext();
});
myPageIdentity.addEventListener('click', () => {
  myPage.classList.remove('is-basic-info-open');
  updateMyPageContext();
});
updateMyPageContext();
