(() => {
  'use strict';

  /* ────────── 0. Data ────────── */
  const caseItems   = JSON.parse(document.getElementById('case-data').textContent);
  const spinUrl     = document.querySelector('meta[name="spin-case-url"]').content;
  const sellUrl     = document.querySelector('meta[name="sell-items-url"]').content;
  const csrfToken   = document.querySelector('meta[name="csrf-token"]').content;
  const casePrice   = +document.querySelector('meta[name="case-price"]').content;
  let   userBalance = 0;

  /* ────────── 1. DOM caching ────────── */
  const $ = s => document.querySelector(s);
  const dom = {
    balance      : $('#balanceValue'),
    track        : $('.roulette-track'),
    viewport     : $('.roulette-viewport'),
    loginNotice  : $('#login-notice'),
    balanceNotice: $('#balance-notice'),
    openBtn      : $('#open-btn'),
    spinnerArea  : $('#spinner-area'),
    resultArea   : $('#result-area'),
    sellBtn      : $('#sell-btn'),
    againBtn     : $('#again-btn'),
    contentCards : $('#content-cards'),
    contentTitle : $('#content-title'),
    burgerBtn    : $('#burgerBtn'),
    miniMenu     : $('#miniMenu'),
    menuDimmer   : $('#menuDimmer'),
    supportBtn   : $('#supportBtn'),
  };

  /* ────────── 2. Utilities ────────── */
  const show = el => el && el.classList.add('visible');
  const hide = el => el && el.classList.remove('visible');

  function postJSON(url, data) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken': csrfToken,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    }).then(r => r.json());
  }

  /* animate balance from old to new */
  function balanceAnim(newVal) {
    if (!dom.balance) return;
    const from = parseFloat(dom.balance.textContent.replace(/[^0-9.\-]/g, '')) || 0;
    dom.balance.classList.add('balance-change');
    setTimeout(() => dom.balance.classList.remove('balance-change'), 800);
    let start;
    (function step(ts) {
      start ??= ts;
      const t = Math.min((ts - start) / 800, 1);
      const ease = t < .5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
      dom.balance.textContent = '$' + (from + (newVal - from) * ease).toFixed(2);
      t < 1 && requestAnimationFrame(step);
    })(performance.now());
  }

  /* ────────── 3. Create a card element ────────── */
  function makeCard(item, withPrice = false) {
    const d = document.createElement('div');
    d.className = 'item-card';
    d.style.setProperty('--r-full',  item.rarity_color);
    d.style.setProperty('--r-light', item.rarity_color_light);
    d.innerHTML = `
      <span class="item-weapon">${item.weapon_name}</span>
      <span class="item-skin">${item.skin_name}</span>
      <img  class="item-img" src="${item.image_url}">
      ${withPrice ? `<span class="item-price">$${item.price.toFixed(2)}</span>` : ''}`;
    return d;
  }

  /* ────────── 4. Render content cards ────────── */
  function renderContentCards() {
    if (!dom.contentCards) return;
    const order = ['Extraordinary','Covert','Classified','Restricted','Mil-Spec'];
    [...caseItems]
      .sort((a,b) => order.indexOf(a.rarity) - order.indexOf(b.rarity))
      .forEach(i => dom.contentCards.appendChild(makeCard(i, true)));
  }

  /* ────────── 5. Weighted pool setup ────────── */
  const pool = caseItems.map((ci, i) => ({ idx: i, w: Math.max(ci.drop_chance, 0.1) }));
  const sumW = pool.reduce((s, o) => s + o.w, 0);
  function pick(prev) {
    let r = Math.random() * sumW, p, tries = 0;
    do {
      for (const o of pool) {
        if ((r -= o.w) <= 0) { p = o.idx; break; }
      }
    } while (p === prev && ++tries < 3);
    return p;
  }

  /* ────────── 6. Track variables ────────── */
  let cw = 0, vw = 0;
  let curIdx = 0, curOff = 0;
  const trackIdx = [];
  const INITIAL = 450, EXTEND = 160;

  function fillTrack(n) {
    let prev = trackIdx.at(-1);
    for (let i = 0; i < n; i++) {
      const idx = pick(prev);
      prev = idx;
      trackIdx.push(idx);
      dom.track.appendChild(makeCard(caseItems[idx]));
    }
  }

  /* ────────── 7. Initialization ────────── */
  document.addEventListener('DOMContentLoaded', () => {
    if (dom.balance) {
      const bal = parseFloat(dom.balance.textContent.replace(/[^0-9.\-]/g, '')) || 0;
      dom.balance.textContent = '$' + bal.toFixed(2);
      userBalance = bal;
    }
    initMenu();
    renderContentCards();
    initRoulette();
    dom.openBtn?.addEventListener('click', openCase);
    dom.againBtn?.addEventListener('click', again);
    dom.sellBtn ?.addEventListener('click', sell);
  });

  function initRoulette() {
    fillTrack(INITIAL);
    const c0 = dom.track.firstElementChild;
    const st = getComputedStyle(c0);
    cw = c0.getBoundingClientRect().width
         + parseFloat(st.marginLeft)
         + parseFloat(st.marginRight);
    vw = dom.viewport.getBoundingClientRect().width;
    curIdx = Math.floor(trackIdx.length / 2);
    curOff = curIdx * cw - (vw / 2 - cw / 2);
    dom.track.style.transform = `translateX(-${curOff}px)`;
  }

  /* ────────── 8. Handle case opening ────────── */
  async function openCase() {
    hide(dom.loginNotice);
    hide(dom.balanceNotice);
    if (userBalance < casePrice) {
      showBalanceNotice(casePrice - userBalance);
      return;
    }

    hide(dom.openBtn);
    hide(dom.resultArea);
    show(dom.spinnerArea);
    dom.contentCards?.classList.add('shifted');
    dom.contentTitle?.classList.add('shifted');

    try {
      const r = await postJSON(spinUrl, {});
      lastInvId = r.inventory_item_id;
      balanceAnim(r.new_balance);
      userBalance = r.new_balance;

      const win = caseItems.find(ci => ci.id === r.winning_item_id);
      dom.sellBtn.textContent = `Sell for $${win.price.toFixed(2)}`;

      await spinTo(win);

      hide(dom.spinnerArea);
      show(dom.resultArea);
      dom.contentCards?.classList.remove('shifted');
      dom.contentTitle?.classList.remove('shifted');
    } catch (e) {
      console.error(e);
      hide(dom.spinnerArea);
      show(dom.openBtn);
      if (userBalance < casePrice) showBalanceNotice(casePrice - userBalance);
    }
  }

  /* ────────── 9. Spin animation ────────── */
  async function spinTo(winItem) {
    const MIN = 110, EXTRA = Math.floor(Math.random() * 80);
    let target = curIdx + MIN + EXTRA;

    while (trackIdx.length <= target) fillTrack(EXTEND);

    const winGlobal = caseItems.indexOf(winItem);
    trackIdx[target] = winGlobal;
    dom.track.replaceChild(
      makeCard(winItem),
      dom.track.children[target]
    );

    const offFinal = target * cw - (vw / 2 - cw / 2);
    let overshift = cw * (Math.random() * 0.8 - 0.4);
    if (Math.abs(overshift) < cw * 0.1) {
      overshift += overshift > 0 ? cw * 0.1 : -cw * 0.1;
    }
    const offOver = offFinal + overshift;
    const longDur = 7500 + Math.random() * 2000;

    await dom.track.animate(
      [
        { transform: `translateX(-${curOff}px)` },
        { transform: `translateX(-${offOver}px)` }
      ],
      { duration: longDur, easing: 'cubic-bezier(.25,.01,.14,1)', fill: 'forwards' }
    ).finished;

    await new Promise(res => setTimeout(res, 450));
    dom.track.querySelectorAll('.item-card')
      .forEach((c, i) => i !== target && c.classList.add('faded'));

    await dom.track.animate(
      [
        { transform: `translateX(-${offOver}px)` },
        { transform: `translateX(-${offFinal}px)` }
      ],
      { duration: 900, easing: 'cubic-bezier(.18,0,.08,1)', fill: 'forwards' }
    ).finished;

    curOff = offFinal;
    curIdx = target;
  }

  /* ────────── 10. Result buttons ────────── */
  let lastInvId = null;
  function again() {
    hide(dom.resultArea);
    dom.track.querySelectorAll('.item-card')
      .forEach(c => c.classList.remove('faded'));
    lastInvId = null;
    userBalance < casePrice
      ? showBalanceNotice(casePrice - userBalance)
      : show(dom.openBtn);
  }

  async function sell(){
    if(!lastInvId) return;
    const fd=new FormData();
    fd.append('item_ids[]',lastInvId);
    fd.append('csrfmiddlewaretoken',csrfToken);
    try{
      const d=await (await fetch(sellUrl,{method:'POST',credentials:'same-origin',body:fd})).json();
      if(d.success){ balanceAnim(d.new_balance); userBalance=d.new_balance; }
    }catch(e){console.error(e);}

    dom.track.querySelectorAll('.item-card').forEach(c=>c.classList.remove('faded'));
    hide(dom.resultArea); lastInvId=null;
    userBalance<casePrice ? showBalanceNotice(casePrice-userBalance) : show(dom.openBtn);
  }

  function showBalanceNotice(missing) {
    dom.balanceNotice.innerHTML = `
      <span class="notice-text">
        You need <span class="notice-amount">$${missing.toFixed(2)}</span> more to open
      </span>`;
    show(dom.balanceNotice);
  }

  /* ────────── 12. Burger menu setup ────────── */
  function initMenu() {
    dom.burgerBtn?.addEventListener('click', e => {
      e.stopPropagation();
      dom.miniMenu.classList.toggle('show');
      dom.menuDimmer.classList.toggle('show');
      dom.burgerBtn.classList.toggle('active');
    });
    dom.menuDimmer?.addEventListener('click', () => {
      dom.miniMenu.classList.remove('show');
      dom.menuDimmer.classList.remove('show');
      dom.burgerBtn.classList.remove('active');
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') {
        dom.miniMenu.classList.remove('show');
        dom.menuDimmer.classList.remove('show');
        dom.burgerBtn.classList.remove('active');
      }
    });
    dom.supportBtn?.addEventListener('click', () => {
      createToast('info','Please don’t contact us');
      dom.miniMenu.classList.remove('show');
      dom.menuDimmer.classList.remove('show');
      dom.burgerBtn.classList.remove('active');
    });
  }

  /* ────────── 13. Recalculate dimensions on resize ────────── */
  window.addEventListener('resize', () => {
    const c0 = dom.track.firstElementChild;
    const st = getComputedStyle(c0);
    cw = c0.getBoundingClientRect().width
         + parseFloat(st.marginLeft)
         + parseFloat(st.marginRight);
    vw = dom.viewport.getBoundingClientRect().width;
    curOff = curIdx * cw - (vw / 2 - cw / 2);
    dom.track.style.transition = 'none';
    dom.track.style.transform = `translateX(-${curOff}px)`;
  });

  /* disable drag/select on images/links */
  document.querySelectorAll('img,a')
    .forEach(el => el.setAttribute('draggable','false'));

  /* fade out preloader on full load */
  window.addEventListener('load', () => {
    const pre = $('#page-preloader');
    pre?.classList.add('loaded');
    setTimeout(() => pre?.remove(), 600);
  });
})();
