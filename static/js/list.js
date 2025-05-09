window.addEventListener('load', () => {
  // fade out and remove preloader
  const pre = document.getElementById('page-preloader');
  if (pre) {
    pre.style.transition = 'opacity 0.3s ease';
    pre.style.opacity = '0';
    setTimeout(() => { pre.remove(); }, 300);
  }

  // format balance and prepend $
  const balEl = document.getElementById('balanceValue');
  if (balEl) {
    const num = parseFloat(balEl.textContent.replace(/[^0-9.\-]/g, '')) || 0;
    balEl.textContent = '$' + num.toFixed(2);
  }

  // cache menu elements
  const burger   = document.getElementById('burgerBtn');
  const miniMenu = document.getElementById('miniMenu');
  const dimmer   = document.getElementById('menuDimmer');

  // helper to close burger menu
  function closeMenu() {
    miniMenu.classList.remove('show');
    dimmer.classList.remove('show');
    burger.classList.remove('active');
  }

  // toggle menu open/close
  burger.addEventListener('click', e => {
    e.stopPropagation();
    miniMenu.classList.toggle('show');
    dimmer.classList.toggle('show');
    burger.classList.toggle('active');
  });
  dimmer.addEventListener('click', closeMenu);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeMenu();
  });

  // disable dragging on images and links
  document.querySelectorAll('img, a')
    .forEach(el => el.setAttribute('draggable', 'false'));
});
