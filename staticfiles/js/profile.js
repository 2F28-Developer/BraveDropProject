document.addEventListener('DOMContentLoaded', () => {

  /* ────────── 0. Cache DOM elements + helpers ───────────────── */
  const invWrapper      = document.getElementById('inventoryWrapper');
  const invPanel        = document.getElementById('inventoryPanel');
  const toastBox        = document.getElementById('toastContainer');
  const balEl           = document.getElementById('balanceValue');
  const profBalEl       = document.getElementById('profileBalance');
  const overlay         = document.getElementById('inventoryOverlay');
  const oText           = document.getElementById('overlayText');

  const burger          = document.getElementById('burgerBtn');
  const miniMenu        = document.getElementById('miniMenu');
  const dimmer          = document.getElementById('menuDimmer');

  const tradeLinkBtn    = document.getElementById('tradeLinkBtn');
  const tradePopup      = document.getElementById('tradePopup');
  const whereFindBtn    = document.getElementById('whereFindBtn');
  const tradeUrlInput   = document.getElementById('tradeUrlInput');
  const saveTradeUrlBtn = document.getElementById('saveTradeUrlBtn');
  const balanceBtn = document.getElementById('balanceBtn');

  const sellBtn         = document.getElementById('sellBtn');
  const sellAllBtn      = document.getElementById('sellAllBtn');
  const withdrawBtn     = document.getElementById('withdrawBtn');

  const selected  = new Set();
  let   busy      = false;
  const CSRF      = () => document.querySelector('meta[name="csrf-token"]').content;
  const url       = n  => document.querySelector(`meta[name="${n}"]`).content;

  function ease(t){ return t<.5 ? 2*t*t : -1+(4-2*t)*t; }

  function balanceAnim(el, newVal){
    const from = parseFloat(el.textContent.replace(/[^0-9.\-]/g, '')) || 0;
    const duration = 800;
    let start = null;

    el.classList.add('balance-change');
    setTimeout(()=> el.classList.remove('balance-change'), duration);

    function ease(t){ return t<.5 ? 2*t*t : -1+(4-2*t)*t; }

    function step(ts){
      if (!start) start = ts;
      const t = Math.min((ts - start)/duration, 1);
      const curr = from + (newVal - from) * ease(t);

      el.textContent = '$' + curr.toFixed(2);

      if (t < 1) requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
  }

  /* ────────── 1. Stub building ───────────────────────── */
  function buildStub(){
    const d = document.createElement('div');
    d.className = 'no-items-inv';
    d.innerHTML = `
      <div class="no-items-label">No items</div>
      <button class="no-items-open" onclick="location.href='/'">OPEN</button>`;
    return d;
  }
  function ensureStub(immediate = false){
    if (invPanel.querySelector('.item-card')) return;
    let stub = invPanel.querySelector('.no-items-inv');
    if (!stub){
      stub = buildStub();
      invPanel.appendChild(stub);
    }
    if (immediate){
      stub.style.opacity = '1';
    } else {
      requestAnimationFrame(()=>requestAnimationFrame(()=>{
        stub.classList.add('show');
      }));
    }
  }
  function hideStub(){
    const s = invPanel.querySelector('.no-items-inv');
    if(!s) return;
    s.classList.remove('show');
    s.addEventListener('transitionend', ()=>s.remove(), { once:true });
  }
  ensureStub(true);

  /* ────────── 2. FLIP animations ──────────────────────── */
  function withInventoryFLIP(action) {
    hideStub();

    const h0 = invWrapper.offsetHeight;
    invWrapper.style.height = h0 + 'px';

    const first = [];
    invPanel.querySelectorAll('.item-card')
      .forEach(el => first.push({ el, rect: el.getBoundingClientRect() }));

    action();
    ensureStub();

    requestAnimationFrame(() => {
      invPanel.querySelectorAll('.item-card').forEach(el => {
        const f = first.find(o => o.el === el);
        if (!f) return;
        const to = el.getBoundingClientRect();
        const dx = f.rect.left - to.left;
        const dy = f.rect.top  - to.top;
        if (!dx && !dy) return;

        el.style.transition = 'none';
        el.style.transform  = `translate(${dx}px,${dy}px)`;

        requestAnimationFrame(() => {
          el.style.transform  = '';
          el.style.transition = 'transform .35s cubic-bezier(.4,0,.2,1)';
          el.addEventListener('transitionend',
            e => e.propertyName === 'transform' && (el.style.transition = ''),
            { once: true }
          );
        });
      });

      let h1 = invPanel.offsetHeight;
      if (!invPanel.querySelector('.item-card')) {
        h1 += 4;
      }

      invWrapper.style.transition = 'height .45s ease';
      invWrapper.style.height     = h1 + 'px';

      invWrapper.addEventListener('transitionend', e => {
        if (e.propertyName !== 'height') return;
        invWrapper.style.cssText = '';
      }, { once: true });
    });
  }

  /* ────────── 4. Selection handling ──────────────────── */
  function toggleButtons(){
    const movable = invPanel.querySelectorAll('.item-card:not(.locked)').length;
    sellAllBtn.disabled  = busy || !movable;
    sellBtn.disabled     = busy || !selected.size;
    withdrawBtn.disabled = busy || !selected.size;
  }
  invPanel.addEventListener('click', e => {
    const card = e.target.closest('.item-card');
    if(!card || busy || card.classList.contains('locked')) return;
    const id = card.dataset.itemId;
    if(selected.has(id)){
      selected.delete(id); card.classList.remove('selected');
    } else {
      selected.add(id); card.classList.add('selected');
    }
    toggleButtons();
  });
  function lockCard(c){ c.classList.add('locked'); c.style.pointerEvents='none'; }
  function unlockCard(c){ c.classList.remove('locked'); c.style.pointerEvents=''; }

  /* ────────── 5. Withdrawal overlays ─────────────────── */
  function markWithdrawing(ids, instant=false){
    ids.forEach(id => {
      const card = invPanel.querySelector(`.item-card[data-item-id="${id}"]`);
      if(!card) return;
      let ov = card.querySelector('.card-overlay');
      let lb = card.querySelector('.card-label');
      if(!ov){
        ov = document.createElement('div'); ov.className='card-overlay';
        lb = document.createElement('div'); lb.className='card-label';
        lb.textContent='Withdrawing';
        card.append(ov,lb);
        if(instant){
          ov.classList.add('show'); lb.classList.add('show');
        } else {
          requestAnimationFrame(()=>requestAnimationFrame(()=>{
            ov.classList.add('show'); lb.classList.add('show');
          }));
        }
      }
      card.classList.remove('pending','selected');
      lockCard(card);
    });
    toggleButtons();
  }
  function rollbackWithdrawing(ids){
    ids.forEach(id => {
      const card = invPanel.querySelector(`.item-card[data-item-id="${id}"]`);
      if(!card) return;
      card.querySelectorAll('.card-overlay,.card-label').forEach(el=>{
        el.classList.remove('show');
        el.addEventListener('transitionend', ()=>el.remove(), { once:true });
      });
      unlockCard(card);
    });
    toggleButtons();
  }

  /* ────────── 6. Smooth removal ──────────────────────── */
  function sellAndShrink(ids, newBal = null){
    return new Promise(resolve => {
      ids = ids.map(String);
      const cards = ids
        .map(id => invPanel.querySelector(`.item-card[data-item-id="${id}"]`))
        .filter(Boolean);

      cards.forEach(c => { c.classList.add('fade-out'); lockCard(c); });

      let left = cards.length;
      cards.forEach(c => {
        c.addEventListener('transitionend', function onEnd(e){
          if (e.propertyName !== 'opacity') return;
          c.removeEventListener('transitionend', onEnd);
          if (--left === 0){
            withInventoryFLIP(() => cards.forEach(c2 => c2.remove()));
            ensureStub();
            toggleButtons();
            if (newBal !== null){
              balanceAnim(balEl, newBal);
              balanceAnim(profBalEl, newBal);
            }
            resolve();
          }
        });
      });
    });
  }

  /* ────────── 7. Busy overlay ────────────────────────── */
  function showOv(txt){
    invWrapper.appendChild(overlay);
    busy = true; toggleButtons();
    oText.textContent = txt;
    invPanel.style.pointerEvents = 'none';
    overlay.style.display = 'flex';
    overlay.offsetHeight;
    overlay.classList.add('show');
  }
  function hideOv(){
    overlay.classList.remove('show');
    overlay.addEventListener('transitionend', ()=>{
      overlay.style.display = 'none';
      invPanel.style.pointerEvents = '';
      busy = false; toggleButtons();
      invPanel.appendChild(overlay);
    }, { once:true });
  }

  /* ────────── 8. POST helper ─────────────────────────── */
  async function post(u, fm){
    const r = await fetch(u, { method:'POST', credentials:'same-origin', body:fm });
    return { ok: r.ok, data: await r.json() };
  }

  /* ────────── 9. Sell selected ───────────────────────── */
  sellBtn.addEventListener('click', async () => {
    if (busy || !selected.size) return;
    const ids = [...selected]; selected.clear();
    ids.forEach(id => invPanel.querySelector(`.item-card[data-item-id="${id}"]`)?.classList.remove('selected'));
    showOv('Selling');
    try {
      const fm = new FormData();
      ids.forEach(i => fm.append('item_ids[]', i));
      fm.append('csrfmiddlewaretoken', CSRF());
      const { data } = await post(url('sell-items-url'), fm);
      if (data.success){
        await sellAndShrink(data.removed_ids, data.new_balance);
        createToast('success','Sold');
      } else {
        createToast('error', data.error || 'Sell error');
      }
    } catch {
      createToast('error','Network error');
    } finally {
      hideOv();
    }
  });

  /* ────────── 10. Sell all ───────────────────────────── */
  sellAllBtn.addEventListener('click', async () => {
    if (busy) return;
    const cards = [...invPanel.querySelectorAll('.item-card:not(.locked)')];
    const ids   = cards.map(c => c.dataset.itemId);
    if (!ids.length) return;
    showOv('Selling');
    try {
      const fm = new FormData();
      ids.forEach(i => fm.append('item_ids[]', i));
      fm.append('csrfmiddlewaretoken', CSRF());
      const { data } = await post(url('sell-items-url'), fm);
      if (data.success){
        await sellAndShrink(data.removed_ids, data.new_balance);
        createToast('success','Sold');
      } else {
        createToast('error', data.error || 'Sell error');
      }
    } catch {
      createToast('error','Network error');
    } finally {
      hideOv();
    }
  });

  /* ────────── 11. Create withdrawal ───────────────────── */
  withdrawBtn.addEventListener('click', async () => {
    if (busy || !selected.size) return;

    const ids = [...selected];
    selected.clear();
    ids.forEach(id =>
      invPanel.querySelector(`.item-card[data-item-id="${id}"]`)?.classList.remove('selected')
    );

    showOv('Withdrawing');

    try {
      const fm = new FormData();
      ids.forEach(i => fm.append('item_ids[]', i));
      fm.append('csrfmiddlewaretoken', CSRF());

      const res = await fetch(url('buy-for-item-url'), {
        method: 'POST',
        body: fm,
        credentials: 'same-origin'
      });
      const d = await res.json();

      if (res.ok && d.success) {
        if (d.created?.length) {
          markWithdrawing(d.created.map(String));
          createToast('success', 'Withdrawal created');
        }

        if (d.failed?.length) {
          d.failed.forEach(m => createToast('error', m));
        }

        if (!d.created?.length && !d.failed?.length) {
          createToast('error', 'No withdrawals created');
        }
      } else {
        rollbackWithdrawing(ids);
        createToast('error', d.error || 'Withdrawal error');
      }
    } catch {
      rollbackWithdrawing(ids);
      createToast('error', 'Network error');
    } finally {
      hideOv();
      toggleButtons();
    }
  });

  /* ────────── 12. Init withdrawal overlays ───────────── */
  function refreshWithdrawOverlays(){
    invPanel.querySelectorAll('.item-card.pending')
            .forEach(c=>markWithdrawing([c.dataset.itemId], true));
    if (window.active_withdrawals_json){
      JSON.parse(window.active_withdrawals_json)
           .forEach(id=>markWithdrawing([String(id)], true));
    }
    toggleButtons();
  }
  refreshWithdrawOverlays();

  /* ────────── 13. Poll withdrawal status ─────────────── */
  setInterval(()=>{
    fetch(url('poll-withdrawals-url'))
      .then(r=>r.json())
      .then(d=>{
        (d.removed||[]).map(String).forEach(id=>{
          const c = invPanel.querySelector(`.item-card[data-item-id="${id}"]`);
          if(!c) return;
          c.classList.add('fade-out');
          c.addEventListener('transitionend',()=>{
            withInventoryFLIP(()=>c.remove());
            ensureStub();
          },{once:true});
          createToast('success','Withdrawal completed');
        });
        (d.returned||[]).map(String).forEach(id=>{
          rollbackWithdrawing([id]);
          createToast('error','Withdrawal cancelled');
        });
        if(d.removed?.length || d.returned?.length) toggleButtons();
      })
      .catch(()=>{});
  }, 25000);

  /* ────────── 14. Trade URL toggles ───────────────────── */
  function closeMenu(){
    miniMenu.classList.remove('show');
    dimmer.classList.remove('show');
    burger.classList.remove('active');
  }
  burger.addEventListener('click', e => {
    e.stopPropagation();
    miniMenu.classList.toggle('show');
    dimmer.classList.toggle('show');
    burger.classList.toggle('active');
  });
  dimmer.addEventListener('click', closeMenu);
  document.addEventListener('keydown', e => e.key==='Escape' && closeMenu());

  tradeLinkBtn.addEventListener('click', e => {
    e.stopPropagation();
    tradePopup.classList.toggle('active');
    tradeLinkBtn.classList.toggle('active');
  });
  tradePopup.addEventListener('click', e => e.stopPropagation());
  document.addEventListener('click', ()=>{
    tradePopup.classList.remove('active');
    tradeLinkBtn.classList.remove('active');
  });
  whereFindBtn.addEventListener('click', ()=>{
    window.open('https://steamcommunity.com/id/me/tradeoffers/privacy#trade_offer_access_url','_blank');
  });

  tradeUrlInput.addEventListener('input', ()=> saveTradeUrlBtn.disabled = !tradeUrlInput.value.trim());
  saveTradeUrlBtn.addEventListener('click', async ()=>{
    const v = tradeUrlInput.value.trim();
    if (!v){ createToast('error','Link not provided'); return; }
    const fm = new FormData();
    fm.append('trade_url', v);
    fm.append('csrfmiddlewaretoken', CSRF());
    try {
      const { ok, data } = await post(url('update-trade-url'), fm);
      if (ok && data.success){
        createToast('success','Link saved');
        tradeUrlInput.value = '';
        saveTradeUrlBtn.disabled = true;
        tradePopup.classList.remove('active');
        tradeLinkBtn.classList.remove('active');
      } else {
        createToast('error', data.error || data.message || 'Error');
      }
    } catch {
      createToast('error','Network error');
    }
  });


  balanceBtn.addEventListener('click', () => {
    const current = parseFloat(balEl.textContent.replace(/[^0-9.]/g, '')) || 0;
    const newVal  = current + 100;

    balanceAnim(balEl,    newVal);
    balanceAnim(profBalEl, newVal);
  });

  /* ────────── 15. Misc initial setup ────────────────── */
  toggleButtons();
  document.querySelectorAll('img,a').forEach(el=>el.setAttribute('draggable','false'));
  document.addEventListener('dragstart', e=>{ e.preventDefault(); return false; });
  window.addEventListener('load', ()=>document.getElementById('page-preloader')?.classList.add('loaded'));
  [balEl, profBalEl].forEach(el=>{ el.textContent = el.textContent.replace(/,/g,'.'); });

}); /* ────── DOMContentLoaded end ────── */
