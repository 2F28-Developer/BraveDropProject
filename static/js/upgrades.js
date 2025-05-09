document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  /* === 0. MINI-MENU & PRELOADER ============================================= */
  const burger    = document.getElementById('burgerBtn');
  const miniMenu  = document.getElementById('miniMenu');
  const dimmer    = document.getElementById('menuDimmer');
  const panelsRow = document.querySelector('.panels-row');

  // Toggle mobile menu
  burger?.addEventListener('click', e => {
    e.stopPropagation();
    burger.classList.toggle('active');
    miniMenu.classList.toggle('show');
    dimmer.classList.toggle('show');
  });
  dimmer?.addEventListener('click', closeMenu);
  document.addEventListener('click', e => {
    if (!miniMenu.contains(e.target) && e.target !== burger) closeMenu();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMenu(); });
  function closeMenu() {
    burger.classList.remove('active');
    miniMenu.classList.remove('show');
    dimmer.classList.remove('show');
  }

  // Hide preloader on page load
  window.addEventListener('load', () => {
    const pre = document.getElementById('page-preloader');
    pre?.classList.add('loaded');
    setTimeout(() => pre?.remove(), 600);
  });

  /* === HOW-TO OVERLAY (available to all) ===================================== */
  const howBtn    = document.getElementById('howPlayBtn');
  const howOv     = document.getElementById('howOverlay');
  const howPanels = [...document.querySelectorAll('.how-panel')];
  const howNums   = [...document.querySelectorAll('.step-num')];

  howBtn?.addEventListener('click', openHow);
  howOv?.addEventListener('click', closeHow);

  function openHow() {
    howOv.classList.add('show');
    document.body.classList.add('no-scroll');
    howPanels.forEach((p, i) => setTimeout(() => p.classList.add('show'), i * 180));
    howNums   .forEach((n, i) => setTimeout(() => n.classList.add('show'), i * 180 + 150));
  }

  function closeHow() {
    const revP = [...howPanels].reverse();
    const revN = [...howNums].reverse();
    revN.forEach((n, i) => setTimeout(() => n.classList.remove('show'), i * 150));
    revP.forEach((p, i) => setTimeout(() => p.classList.remove('show'), i * 150 + 120));
    const total = revP.length * 150 + 300;
    setTimeout(() => {
      howOv.classList.remove('show');
      document.body.classList.remove('no-scroll');
    }, total);
  }

  /* === exit early for non-authenticated users ================================ */
  if (!window.isAuthenticated) return;

  /* === 1. CONSTANTS & HELPERS ================================================ */
  const ease           = t => 1 - Math.pow(1 - t, 3);
  const ARC_LEN        = 2 * Math.PI * 120;
  const SPIN_MS        = 7000;
  const REVERSE_MS     = 2000;
  const SLIDER_MS      = 2000;
  const RIGHT_STEP     = 60;
  const MIN_FULL_TURNS = 2;
  const fmtUsd         = n => '$' + n.toFixed(2);

  /* === 2. DOM ELEMENTS & STATE =============================================== */
  const arc         = document.getElementById('arcFill');
  const pointer     = document.getElementById('pointer');
  const chanceTxt   = document.getElementById('chanceTxt');
  const resultCir   = document.getElementById('resultCircle');
  const extra       = document.getElementById('extraInput');
  const extraLbl    = document.getElementById('extraLabel');
  const usedLbl     = document.getElementById('usedValue');
  const runBtn      = document.getElementById('upgradeBtn');
  const balanceEl   = document.getElementById('balanceValue');
  const leftGrid    = document.getElementById('leftGrid');
  const rightGrid   = document.getElementById('rightGrid');
  const rightScroll = document.getElementById('rightScrollable');
  const rightOv     = document.getElementById('rightOverlay');
  const invSortBtn  = document.getElementById('invSortBtn');
  const tgtSortBtn  = document.getElementById('targetSortBtn');

  let leftSel        = new Set();
  let rightSel       = null;
  let prevChance     = 0;
  let locked         = false;
  let spinAngle      = 0;
  let loadingTargets = false;
  let rightOffset    = 0;
  let noMoreTargets  = false;

  /* === 3. SLIDER INITIALIZATION ============================================= */
  extra.max = Math.floor(parseFloat(extra.getAttribute('max')) || 0);
  const sliderDisabled = () =>
    !window.isAuthenticated ||
    parseFloat(balanceEl.textContent.replace(/[^0-9.\-]/g, '')) <= 0 ||
    extra.max === 0 ||
    locked;

  function updateSliderDisabled() {
    extra.disabled = sliderDisabled();
    extra.style.filter = extra.disabled ? 'grayscale(1) brightness(.5)' : 'none';
  }

  extra.addEventListener('input', () => {
    extraLbl.textContent = '$' + parseFloat(extra.value).toFixed(2);
    const p = extra.max ? (extra.value / extra.max) * 100 : 0;
    extra.style.background = `linear-gradient(90deg, var(--accent) ${p}%, var(--track) ${p}%)`;
    recalc();
  });

  extra.dispatchEvent(new Event('input'));
  updateSliderDisabled();

  /* === 4. DRAW CHANCE ARC =================================================== */
  function drawChance(v) {
    arc.style.transition = 'stroke-width .35s, stroke-dashoffset .35s';
    if (v <= 0) {
      arc.style.strokeWidth = '0';
      arc.style.strokeDashoffset = ARC_LEN;
      animateNum(chanceTxt, prevChance, 0);
      prevChance = 0;
    } else {
      arc.style.strokeWidth = '20';
      arc.style.strokeDashoffset = ARC_LEN * (1 - v / 100);
      animateNum(chanceTxt, prevChance, v);
      prevChance = v;
    }
  }

  function animateNum(el, from, to, ms = 350) {
    const start = performance.now();
    requestAnimationFrame(function step(now) {
      const k = Math.min((now - start) / ms, 1);
      el.textContent = Math.round(from + (to - from) * ease(k)) + '%';
      if (k < 1) requestAnimationFrame(step);
    });
  }

  /* === 5. BALANCE & VALUE ANIMATIONS ======================================== */
  function animateBalance(el, from, to, ms = 800) {
    el.classList.add('balance-change');
    setTimeout(() => el.classList.remove('balance-change'), ms);
    const start = performance.now();
    requestAnimationFrame(function step(now) {
      const k = Math.min((now - start) / ms, 1);
      el.textContent = fmtUsd(from + (to - from) * ease(k));
      if (k < 1) requestAnimationFrame(step);
    });
  }

  function animateValue(el, from, to, ms = 800) {
    const start = performance.now();
    requestAnimationFrame(function step(now) {
      const k = Math.min((now - start) / ms, 1);
      el.textContent = fmtUsd(from + (to - from) * ease(k));
      if (k < 1) requestAnimationFrame(step);
    });
  }

  function animateSlider(from, to = 0, ms = SLIDER_MS) {
    const start = performance.now();
    requestAnimationFrame(function step(now) {
      const k = Math.min((now - start) / ms, 1);
      const v = Math.round(from + (to - from) * ease(k));
      extra.value = v;
      extraLbl.textContent = '$' + v.toFixed(2);
      const p = extra.max ? (v / extra.max) * 100 : 0;
      extra.style.background =
        `linear-gradient(90deg, var(--accent) ${p}%, var(--track) ${p}%)`;
      if (k < 1) requestAnimationFrame(step);
      else extra.disabled = sliderDisabled();
    });
  }

  /* === 6. ITEM CARD TEMPLATE ================================================= */
  const makeCard = o => `
    <div class="item-card" data-id="${o.id}"
         style="--r-full:${o.rarity_color_full}; --r-light:${o.rarity_color_light}">
      <div class="item-weapon">${o.weapon_name}</div>
      ${o.skin_name ? `<div class="item-skin">${o.skin_name}</div>` : ''}
      ${o.image_url
        ? `<img src="${o.image_url}" class="item-img">`
        : `<div class="img-placeholder"></div>`
      }
      <div class="item-price">$${o.price.toFixed(2)}</div>
    </div>`;

  window.leftItems.sort((a, b) => b.price - a.price);
  leftGrid.innerHTML = window.leftItems.map(makeCard).join('');
  window.rightItems = [];
  checkInventoryEmpty();

  /* === 7. LAZY LOAD TARGET ITEMS =========================================== */
  async function loadTargets() {
    if (loadingTargets || noMoreTargets) return;
    loadingTargets = true;
    rightOv.classList.add('show');
    try {
      const url  = `${window.urls.loadTargets}?offset=${rightOffset}&limit=${RIGHT_STEP}`;
      const resp = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (!data.success) throw new Error('bad JSON');
      if (!data.items.length) noMoreTargets = true;
      else {
        window.rightItems.push(...data.items);
        rightOffset += data.items.length;
        rightGrid.insertAdjacentHTML('beforeend', data.items.map(makeCard).join(''));
      }
    } catch (err) {
      console.error(err);
      alert('Failed to load items:\n' + err.message);
    } finally {
      rightOv.classList.remove('show');
      loadingTargets = false;
    }
  }

  loadTargets();
  rightScroll.addEventListener('scroll', () => {
    const { scrollTop, scrollHeight, clientHeight } = rightScroll;
    if (scrollTop + clientHeight > scrollHeight - 300) loadTargets();
  });

  /* === 8. SELECTION LOGIC =================================================== */
  leftGrid.addEventListener('click', e => {
    if (locked) return;
    const c = e.target.closest('.item-card'); if (!c) return;
    const id = +c.dataset.id;
    if (leftSel.has(id)) leftSel.delete(id), c.classList.remove('selected');
    else if (leftSel.size < 10) leftSel.add(id), c.classList.add('selected');
    recalc();
  });

  rightGrid.addEventListener('click', e => {
    if (locked) return;
    const c = e.target.closest('.item-card'); if (!c) return;
    rightGrid.querySelectorAll('.selected').forEach(x => x.classList.remove('selected'));
    c.classList.add('selected');
    rightSel = +c.dataset.id;
    recalc();
  });

  /* === 9. RECALCULATE CHANCE ================================================= */
  function recalc() {
    const sumLeft = [...leftSel].reduce((sum, id) =>
      sum + ((window.leftItems.find(x => x.id === id) || {}).price || 0), 0
    );
    const used = sumLeft + (+extra.value || 0);
    usedLbl.textContent = fmtUsd(used);

    const target = window.rightItems.find(x => x.id === rightSel);
    const raw    = target?.price ? (used / target.price) * 100 : 0;
    const clamped= Math.max(0, Math.min(raw, 75));

    drawChance(clamped);
    runBtn.disabled = !(leftSel.size && rightSel !== null && !locked);
  }

  /* === 10. COMPUTE FINAL SPIN ANGLE ========================================= */
  function computeFinalAngle(isWin) {
    const filled = (prevChance / 100) * 360;
    const spins  = (Math.floor(Math.random() * 3) + 3) * 360;
    let offset;
    if (isWin) offset = Math.random() * filled;
    else {
      do { offset = Math.random() * 360; } while (offset < filled);
    }
    return Math.max(spins + offset, MIN_FULL_TURNS * 360 + offset);
  }

  /* === 11. PERFORM UPGRADE REQUEST ========================================== */
  runBtn.addEventListener('click', async () => {
    if (locked) return;
    const usedExtra = +extra.value;
    const oldBal    = parseFloat(balanceEl.textContent.replace(/[^0-9.\-]/g, '')) || 0;
    const newBal    = Math.max(0, oldBal - usedExtra);

    setLock(true);
    runBtn.disabled = true;
    extra.disabled  = true;
    extra.style.filter = 'grayscale(1) brightness(.5)';

    try {
      const resp = await fetch(window.urls.createUpgrade, {
        method : 'POST',
        headers: {
          'Content-Type':'application/json',
          'X-CSRFToken': window.urls.csrf
        },
        body   : JSON.stringify({
          user_item_ids : [...leftSel],
          target_item_id: rightSel,
          extra_balance : usedExtra
        })
      });
      const data = await resp.json();
      if (!resp.ok || !data.success) throw new Error(data.message || 'Error');
      if (usedExtra > 0) animateBalance(balanceEl, oldBal, newBal);
      startSpin(data, usedExtra, newBal);
    } catch (err) {
      alert(err.message || err);
      setLock(false);
      runBtn.disabled = false;
      updateSliderDisabled();
    }
  });

  /* === 12. SPIN & ROLLBACK ANIMATION ======================================== */
  function startSpin(res, usedExtra, newBal) {
    spinAngle = computeFinalAngle(res.is_win);
    pointer.style.transition = `transform ${SPIN_MS}ms cubic-bezier(.08,.9,.1,1)`;
    pointer.style.transform  = `rotate(${spinAngle}deg)`;

    setTimeout(() => {
      resultCir.className = `result-circle ${res.is_win ? 'win' : 'lose'} show`;
      resultCir.textContent = res.is_win ? 'VICTORY' : 'DEFEAT';

      animateValue(usedLbl, parseFloat(usedLbl.textContent.replace(/[^0-9.\-]/g,''))||0, 0, SLIDER_MS);
      removeItems([...leftSel]);
      if (res.is_win && res.result_item) addItem(res.result_item);

      leftSel.clear();
      rightSel = null;
      rightGrid.querySelectorAll('.selected').forEach(x => x.classList.remove('selected'));
      checkInventoryEmpty();

      setTimeout(() => {
        resultCir.classList.remove('show');
        drawChance(0);

        const reverseTo = spinAngle - (spinAngle % 360) - 720;
        pointer.style.transition = `transform ${REVERSE_MS}ms ease-in-out`;
        pointer.addEventListener('transitionend', function reset() {
          pointer.removeEventListener('transitionend', reset);
          pointer.style.transition = 'none';
          pointer.style.transform  = 'rotate(0deg)';
          spinAngle = 0;
          pointer.getBoundingClientRect();

          extra.max = Math.floor(newBal);
          updateSliderDisabled();
          setLock(false);
        }, { once:true });

        pointer.style.transform = `rotate(${reverseTo}deg)`;
        animateSlider(usedExtra, 0, SLIDER_MS);
      }, 1400);
    }, SPIN_MS + 200);
  }

  /* === 13. REMOVE & ADD INVENTORY ITEMS ===================================== */
  function removeItems(ids) {
    ids.forEach(id => {
      const idx = window.leftItems.findIndex(o => o.id === id);
      if (idx > -1) window.leftItems.splice(idx, 1);
      const el = leftGrid.querySelector(`[data-id="${id}"]`);
      if (el) {
        el.classList.add('exit');
        requestAnimationFrame(() => el.classList.add('exit-active'));
        el.addEventListener('transitionend', () => el.remove(), { once:true });
      }
    });
  }

  function addItem(o) {
    window.leftItems.unshift(o);
    const div = document.createElement('div');
    div.innerHTML = makeCard(o);
    const card = div.firstElementChild;
    card.classList.add('enter');
    leftGrid.prepend(card);
    requestAnimationFrame(() => card.classList.add('enter-active'));
  }

  /* === 14. SORTING LOGIC ==================================================== */
  function sortArr(arr, btn) {
    const dir = btn.dataset.dir === 'asc' ? 'desc' : 'asc';
    btn.dataset.dir = dir;
    btn.textContent = `Price ${dir === 'asc' ? '↑' : '↓'}`;
    return [...arr].sort((a, b) => dir === 'asc' ? a.price - b.price : b.price - a.price);
  }

  invSortBtn?.addEventListener('click', () => {
    window.leftItems = sortArr(window.leftItems, invSortBtn);
    leftSel.clear();
    leftGrid.innerHTML = window.leftItems.map(makeCard).join('');
    recalc();
  });

  tgtSortBtn?.addEventListener('click', () => {
    window.rightItems = sortArr(window.rightItems, tgtSortBtn);
    rightSel = null;
    rightGrid.querySelectorAll('.selected').forEach(x => x.classList.remove('selected'));
    rightGrid.innerHTML = window.rightItems.map(makeCard).join('');
    recalc();
  });

  /* === 15. MISC UTILITIES & STATE MANAGEMENT ================================ */
  function setLock(v) {
    locked = v;
    panelsRow.classList.toggle('lock', v);
    runBtn.disabled = v || !(leftSel.size && rightSel !== null);
    updateSliderDisabled();
  }

  function checkInventoryEmpty() {
    const scroll = leftGrid.parentElement;
    let ph = scroll.querySelector('.no-items-inv');
    if (!window.leftItems.length) {
      if (!ph) {
        ph = document.createElement('div');
        ph.className = 'no-items-inv';
        ph.innerHTML = `
          <div class="no-items-label">No items</div>
          <button class="no-items-open" onclick="location.href='/'">OPEN</button>`;
        scroll.appendChild(ph);
        requestAnimationFrame(() => ph.classList.add('show'));
      }
    } else if (ph) {
      ph.classList.remove('show');
      ph.addEventListener('transitionend', () => ph.remove(), { once:true });
    }
  }

  // Initial calculation
  recalc();
});

