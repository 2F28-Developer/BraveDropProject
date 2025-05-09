(function(window, document) {
  /* === Toast container setup === */
  let toastBox;
  document.addEventListener('DOMContentLoaded', () => {
    toastBox = document.getElementById('toastContainer');
  });

  /* === Create a toast message === */
  function createToast(type = 'success', msg = '') {
    if (!toastBox) return;
    if (typeof msg !== 'string') msg = msg?.error ?? msg?.message ?? String(msg);
    if (msg.startsWith('{') || msg.startsWith('[')) msg = 'Unknown error';

    const t = document.createElement('div');
    t.className = 'toast-item';
    t.style.background = (type === 'success' ? '#64ce82' : '#c3545b');
    t.textContent = msg;

    /* progress bar */
    const p = document.createElement('div');
    p.className = 'progress';
    t.appendChild(p);

    toastBox.appendChild(t);
    requestAnimationFrame(() => t.classList.add('show'));

    /* auto-dismiss with progress */
    let duration = 4000, remaining = duration, lastTime = 0, paused = false;
    function tick(timestamp) {
      if (!lastTime) lastTime = timestamp;
      if (!paused) {
        remaining -= timestamp - lastTime;
        lastTime = timestamp;
        p.style.width = `${Math.max((remaining / duration) * 100, 0)}%`;
        if (remaining <= 0) return closeToast();
      }
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);

    t.addEventListener('mouseenter', () => paused = true);
    t.addEventListener('mouseleave', () => { paused = false; lastTime = performance.now(); });
    t.addEventListener('click', closeToast);

    /* === Close and remove toast === */
    function closeToast() {
      const height = t.offsetHeight;
      const gap = parseFloat(getComputedStyle(toastBox).gap) || 0;
      t.style.marginBottom = `-${height + gap}px`;
      t.classList.replace('show', 'hide');
      t.addEventListener('animationend', () => t.remove(), { once: true });
    }
  }

  window.createToast = createToast;
})(window, document);
