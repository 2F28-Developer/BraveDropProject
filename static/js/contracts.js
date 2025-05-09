(() => {
  'use strict';

  // hide preloader when page loads or after 4s fallback
  const pre = document.getElementById('page-preloader');
  function hidePre() {
    pre?.classList.add('loaded');
    setTimeout(() => pre?.remove(), 600);
  }
  if (document.readyState === 'complete') hidePre();
  else window.addEventListener('load', hidePre);
  setTimeout(hidePre, 4000);

  const $  = selector => document.querySelector(selector);
  const $$ = selector => Array.from(document.querySelectorAll(selector));

  // header menu
  const burgerBtn = $('#burgerBtn');
  const miniMenu  = $('#miniMenu');
  const menuDim   = $('#menuDimmer');
  function initMenu() {
    if (!burgerBtn) return;
    burgerBtn.addEventListener('click', e => {
      e.stopPropagation();
      burgerBtn.classList.toggle('active');
      miniMenu.classList.toggle('show');
      menuDim.classList.toggle('show');
    });
    menuDim.addEventListener('click', closeMenu);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMenu(); });
    document.addEventListener('click', e => {
      if (!miniMenu.contains(e.target) && e.target !== burgerBtn) closeMenu();
    });
    function closeMenu() {
      burgerBtn.classList.remove('active');
      miniMenu.classList.remove('show');
      menuDim.classList.remove('show');
    }
  }
  initMenu();

    // how-to overlay
  function initHow() {
    const btn    = document.getElementById('howPlayBtn')
    const overlay= document.getElementById('howOverlay')
    if (!btn || !overlay) return
    const panels = overlay.querySelectorAll('.how-panel')
    const steps  = overlay.querySelectorAll('.step-num')

    btn.addEventListener('click', () => {
      overlay.classList.add('show')
      document.body.classList.add('no-scroll')
      panels.forEach((p,i) => setTimeout(() => p.classList.add('show'), i*180))
      steps .forEach((n,i) => setTimeout(() => n.classList.add('show'), i*180+150))
    })
    overlay.addEventListener('click', () => {
      steps .forEach((n,i) => setTimeout(() => n.classList.remove('show'), i*150))
      panels.forEach((p,i) => setTimeout(() => p.classList.remove('show'), i*150+120))
      setTimeout(() => {
        overlay.classList.remove('show')
        document.body.classList.remove('no-scroll')
      }, panels.length*150+300)
    })
  }
  initHow();

  // if guest, only init how-to
  const invPanel = $('#inventoryPanel');
  if (!invPanel) {
    initHow();
    return;
  }

  // DOM refs
  const invWrapper = $('#inventoryWrapper');
  let invOverlay = $('#inventoryOverlay');
  if (!invOverlay) {
    invOverlay = document.createElement('div');
    invOverlay.id = 'inventoryOverlay';
    invOverlay.className = 'inventory-overlay';
    invOverlay.innerHTML = '<div class="spinner"></div>';
    invWrapper.appendChild(invOverlay);
  }

  const slots      = $$('#contractCircle .slot');
  const howBtn     = $('#howPlayBtn');
  const howOv      = $('#howOverlay');
  const howPanels  = $$('#howOverlay .how-panel');
  const howSteps   = $$('#howOverlay .step-num');
  const btnCreate  = $('#create-contract');
  const cntSpan    = btnCreate.querySelector('.cnt');
  const sumSpan    = btnCreate.querySelector('.sum');
  const hint       = $('.contract-hint');
  const resultPane = $('#contractResult');
  const resImg     = $('.result-img');
  const resName    = $('.result-name');
  const resPrice   = $('.result-price');
  const balanceEl  = $('#balanceValue');

  const csrfToken  = () => $('meta[name="csrf-token"]').content;
  const urlCreate  = $('meta[name="create-contract-url"]').content;
  const rawItems   = JSON.parse($('#left-items-data')?.textContent || '[]');

  let selectedCount = 0;
  let selectedSum   = 0;
  let busy          = false;

  const formatPrice = n => '$' + n.toFixed(2);
  const pluralize   = n => n === 1 ? 'item' : 'items';

  function updateCreateButton() {
    cntSpan.textContent = `${selectedCount} ${pluralize(selectedCount)}`;
    sumSpan.textContent = formatPrice(selectedSum);
    btnCreate.disabled = busy || selectedCount < 3;
    hint.style.visibility = selectedCount < 3 ? 'visible' : 'hidden';
  }

  // build inventory cards or show stub
  function ensureStub() {
    if (invPanel.querySelector('.item-card') || invPanel.querySelector('.no-items-inv')) return;
    const stub = document.createElement('div');
    stub.className = 'no-items-inv show';
    stub.innerHTML = `
      <div class="no-items-label">No items</div>
      <button class="no-items-open" onclick="location.href='/'">OPEN</button>`;
    invPanel.appendChild(stub);
  }

  function makeCard(it) {
    const d = document.createElement('div');
    d.className = 'item-card';
    d.dataset.id = it.id;
    d.style.setProperty('--r-full', it.rarity_color);
    d.style.setProperty('--r-light', it.rarity_color_light);
    d.innerHTML = `
      <span class="item-weapon">${it.weapon_name}</span>
      ${it.skin_name ? `<span class="item-skin">${it.skin_name}</span>` : ''}
      <img class="item-img" src="${it.image_url}">
      <span class="item-price">${formatPrice(it.price)}</span>`;
    return d;
  }

  rawItems.forEach(it => invPanel.appendChild(makeCard(it)));
  ensureStub();

  // selection logic
  invPanel.addEventListener('click', e => {
    if (busy) return;
    const card = e.target.closest('.item-card');
    if (!card) return;
    const id = card.dataset.id;
    const price = parseFloat(card.querySelector('.item-price').textContent.slice(1)) || 0;

    if (card.classList.toggle('selected')) {
      if (selectedCount >= slots.length) {
        card.classList.remove('selected');
        return;
      }
      selectedCount++;
      selectedSum += price;
      const slot = slots.find(s => !s.dataset.itemId);
      slot.textContent = '';
      slot.dataset.itemId = id;
      const img = document.createElement('img');
      img.src = card.querySelector('.item-img').src;
      slot.appendChild(img);
      requestAnimationFrame(() => img.classList.add('loaded'));
    } else {
      selectedCount--;
      selectedSum -= price;
      slots.forEach(s => {
        if (s.dataset.itemId === id) {
          s.textContent = s.dataset.index;
          s.querySelector('img')?.remove();
          delete s.dataset.itemId;
        }
      });
    }
    updateCreateButton();
  });

  slots.forEach(s => s.addEventListener('click', () => {
    if (busy || !s.dataset.itemId) return;
    invPanel.querySelector(`.item-card[data-id="${s.dataset.itemId}"]`)?.click();
  }));

  // fly/back animations for slots
  function flySlots() {
    const ctr = $('#contractCircle').getBoundingClientRect();
    slots.forEach(s => {
      const r = s.getBoundingClientRect();
      s.style.setProperty('--dx', `${ctr.left+ctr.width/2 - (r.left+r.width/2)}px`);
      s.style.setProperty('--dy', `${ctr.top+ctr.height/2 - (r.top+r.height/2)}px`);
      s.classList.add('fly');
    });
  }
  function resetSlots() {
    slots.forEach(s => {
      s.classList.remove('fly');
      s.classList.add('back');
      requestAnimationFrame(() => s.classList.remove('back'));
      s.textContent = s.dataset.index;
      s.querySelector('img')?.remove();
      delete s.dataset.itemId;
    });
  }

  // send contract
  btnCreate?.addEventListener('click', async () => {
    if (btnCreate.disabled || busy) return;
    busy = true;
    btnCreate.disabled = true;
    selectedCount = 0;
    selectedSum   = 0;
    updateCreateButton();
    resetSlots();
    invOverlay.style.display = 'flex';
    invOverlay.classList.add('show');
    flySlots();

    const ids = [...invPanel.querySelectorAll('.item-card.selected')].map(c => c.dataset.id);
    let res;
    try {
      res = await fetch(urlCreate, {
        method:'POST',
        headers: { 'Content-Type':'application/json', 'X-CSRFToken':csrfToken() },
        body: JSON.stringify({ user_item_ids: ids, extra_balance: 0 })
      }).then(r => r.json());
    } catch {
      res = { success:false };
    }

    invOverlay.classList.remove('show');
    invOverlay.addEventListener('transitionend', () => invOverlay.style.display = '', { once:true });

    if (!res.success) {
      resetSlots();
      busy = false;
      updateCreateButton();
      return;
    }

    const item = res.result_item;
    resImg.style.backgroundImage = `url(${item.image_url})`;
    resName.textContent = item.weapon_name + (item.skin_name ? ` | ${item.skin_name}` : '');
    resPrice.textContent = formatPrice(item.price);
    resultPane.classList.add('show');

    setTimeout(() => {
      resultPane.classList.remove('show');
      resetSlots();
      // restore create button
      setTimeout(() => {
        $('#contractCenter').classList.remove('hidden');
        howBtn.classList.remove('hidden');
      }, 300);

      // update inventory with flip animation
      setTimeout(() => {
        const h0 = invWrapper.offsetHeight;
        invWrapper.style.height = `${h0}px`;
        const firstRects = [...invPanel.querySelectorAll('.item-card')].map(el => ({ el, rect:el.getBoundingClientRect() }));
        ids.forEach(id => invPanel.querySelector(`.item-card[data-id="${id}"]`)?.remove());
        invPanel.prepend(makeCard(item));
        ensureStub();

        requestAnimationFrame(() => {
          invPanel.querySelectorAll('.item-card').forEach(el => {
            const src = firstRects.find(f => f.el === el);
            if (!src) return;
            const to = el.getBoundingClientRect();
            const dx = src.rect.left - to.left;
            const dy = src.rect.top  - to.top;
            if (!dx && !dy) return;
            el.style.transition = 'none';
            el.style.transform  = `translate(${dx}px,${dy}px)`;
            requestAnimationFrame(() => {
              el.style.transition = 'transform .35s cubic-bezier(.4,0,.2,1)';
              el.style.transform  = '';
            });
          });
          const h1 = invPanel.offsetHeight + (invPanel.querySelector('.item-card') ? 0 : 4);
          invWrapper.style.transition = 'height .45s ease';
          invWrapper.style.height     = `${h1}px`;
          invWrapper.addEventListener('transitionend', e => {
            if (e.propertyName === 'height') invWrapper.style.height = '';
          }, { once:true });
        });

        if (res.new_balance != null) {
          balanceEl.textContent = formatPrice(parseFloat(res.new_balance));
        }
        busy = false;
        updateCreateButton();
      }, 650);

    }, 1000);
  });

  // format initial balance
  if (balanceEl) {
    const b = parseFloat(balanceEl.textContent.replace(/[^0-9.\-]/g,'')) || 0;
    balanceEl.textContent = formatPrice(b);
  }

  updateCreateButton();
})();
