(() => {
  'use strict';

  document.querySelectorAll('[data-dialog]').forEach(button => {
    const dialog = document.getElementById(button.dataset.dialog);
    if (!dialog) return;
    button.addEventListener('click', () => dialog.showModal());
    dialog.querySelector('.close-dialog').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const box = dialog.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
    });
  });

  const stage = document.getElementById('carousel');
  if (!stage) return;
  const discs = [...stage.querySelectorAll('.disc')];
  if (!discs.length) return;
  const previous = document.getElementById('previous-project');
  const next = document.getElementById('next-project');
  const title = document.getElementById('project-title');
  const category = document.getElementById('project-category');
  const collection = document.getElementById('project-collection');
  const collectionRow = document.getElementById('project-collection-row');
  const open = document.getElementById('open-project');
  const linkContext = document.getElementById('open-project-context');
  const number = document.getElementById('current-number');
  const status = document.getElementById('carousel-status');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let position = 0;
  let target = 0;
  let selected = -1;
  let step = 260;
  let frame = 0;
  let lastFrameTime = 0;
  let settleTimer;
  let announcementTimer;
  let pointer = null;
  let suppressClickUntil = 0;

  const clamp = value => Math.max(0, Math.min(discs.length - 1, value));
  const dragging = () => pointer && pointer.dragging;

  function updateSelection(index) {
    if (index === selected) return;
    selected = index;
    const disc = discs[index];
    title.textContent = disc.dataset.title;
    category.textContent = disc.dataset.category;
    collection.textContent = (disc.dataset.collection || '').trim();
    collectionRow.hidden = !collection.textContent;
    open.href = disc.href;
    if (disc.dataset.destination === 'internal') {
      open.removeAttribute('target');
      open.removeAttribute('rel');
      linkContext.textContent = '';
    } else {
      open.target = '_blank';
      open.rel = 'noopener noreferrer';
      linkContext.textContent = ' (opens in a new tab)';
    }
    number.textContent = String(index + 1).padStart(2, '0');
    previous.disabled = index === 0;
    next.disabled = index === discs.length - 1;
    discs.forEach((item, i) => {
      if (i === index) item.setAttribute('aria-current', 'true');
      else item.removeAttribute('aria-current');
    });
    clearTimeout(announcementTimer);
    announcementTimer = setTimeout(() => {
      status.textContent = `${index + 1} of ${discs.length}: ${disc.dataset.title}`;
    }, 220);
  }

  function render() {
    const mobile = stage.clientWidth <= 600;
    const rise = mobile ? 55 : Math.min(115, stage.clientHeight * 0.2);
    discs.forEach((disc, i) => {
      const offset = i - position;
      const visible = Math.abs(offset) < 3.2;
      const scale = Math.max(0.38, Math.min(1.45, Math.pow(1.23, offset)));
      disc.style.transform = `translate(-50%, -50%) translate(${offset * step}px, ${-offset * rise}px) scale(${scale}) perspective(1100px) rotateY(-24deg) rotateX(12deg) rotateZ(20deg)`;
      disc.style.zIndex = String(i + 1);
      disc.style.visibility = visible ? 'visible' : 'hidden';
      disc.style.pointerEvents = visible ? 'auto' : 'none';
      disc.tabIndex = visible ? 0 : -1;
      disc.setAttribute('aria-hidden', String(!visible));
    });
    updateSelection(Math.round(clamp(position)));
  }

  function animate(time) {
    frame = 0;
    const elapsed = lastFrameTime ? Math.min(time - lastFrameTime, 50) : 16;
    lastFrameTime = time;
    if (!dragging()) {
      position = reducedMotion.matches ? target : position + (target - position) * (1 - Math.exp(-elapsed / 85));
      if (Math.abs(target - position) < 0.001) position = target;
    }
    render();
    if (!dragging() && position !== target) frame = requestAnimationFrame(animate);
    else lastFrameTime = 0;
  }

  function requestRender() {
    if (!frame) frame = requestAnimationFrame(animate);
  }

  function goTo(index) {
    clearTimeout(settleTimer);
    // Keep keyboard controls usable when the previously focused disc moves offscreen.
    if (document.activeElement && document.activeElement.classList.contains('disc')) {
      stage.focus({ preventScroll: true });
    }
    target = clamp(Math.round(index));
    requestRender();
  }

  function measure() {
    const size = discs[0].offsetWidth;
    step = size * (stage.clientWidth <= 600 ? 0.73 : 0.69);
    requestRender();
  }

  previous.addEventListener('click', () => goTo(Math.round(target) - 1));
  next.addEventListener('click', () => goTo(Math.round(target) + 1));

  stage.addEventListener('keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const keys = { ArrowLeft: Math.round(target) - 1, ArrowRight: Math.round(target) + 1, Home: 0, End: discs.length - 1 };
    if (!(event.key in keys)) return;
    event.preventDefault();
    goTo(keys[event.key]);
  });

  stage.addEventListener('pointerdown', event => {
    if (!event.isPrimary || event.button !== 0) return;
    clearTimeout(settleTimer);
    pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, start: position, lastX: event.clientX, lastTime: performance.now(), velocity: 0, dragging: false };
    target = position;
  });

  stage.addEventListener('pointermove', event => {
    if (!pointer || pointer.id !== event.pointerId) return;
    const dx = event.clientX - pointer.x;
    const dy = event.clientY - pointer.y;
    if (!pointer.dragging) {
      if (Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx)) { pointer = null; goTo(position); return; }
      if (Math.abs(dx) < 7) return;
      pointer.dragging = true;
      stage.setPointerCapture(event.pointerId);
      stage.classList.add('is-dragging');
    }
    const time = performance.now();
    const velocity = (event.clientX - pointer.lastX) / Math.max(1, time - pointer.lastTime);
    pointer.velocity = pointer.velocity * 0.4 + velocity * 0.6;
    pointer.lastX = event.clientX;
    pointer.lastTime = time;
    position = clamp(pointer.start - dx / step);
    target = position;
    requestRender();
  });

  function release(event) {
    if (!pointer || pointer.id !== event.pointerId) return;
    const wasDragging = pointer.dragging;
    const recent = performance.now() - pointer.lastTime < 100;
    const velocity = recent ? Math.max(-2, Math.min(2, pointer.velocity)) : 0;
    pointer = null;
    stage.classList.remove('is-dragging');
    if (stage.hasPointerCapture(event.pointerId)) stage.releasePointerCapture(event.pointerId);
    if (wasDragging) {
      suppressClickUntil = performance.now() + 350;
      goTo(position - velocity * 110 / step);
    } else goTo(position);
  }
  stage.addEventListener('pointerup', release);
  stage.addEventListener('pointercancel', release);
  stage.addEventListener('lostpointercapture', release);
  window.addEventListener('pointerup', release);
  stage.addEventListener('dragstart', event => event.preventDefault());

  stage.addEventListener('click', event => {
    const disc = event.target.closest('.disc');
    if (!disc) return;
    if (performance.now() < suppressClickUntil) { event.preventDefault(); return; }
    const index = Number(disc.dataset.index);
    if (index !== selected || Math.abs(position - index) > 0.08) {
      event.preventDefault();
      goTo(index);
    }
  });

  stage.addEventListener('wheel', event => {
    if (event.ctrlKey || dragging()) return;
    let delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
    if (event.deltaMode === 1) delta *= 16;
    if (event.deltaMode === 2) delta *= stage.clientHeight;
    if (!delta || (target <= 0 && delta < 0) || (target >= discs.length - 1 && delta > 0)) return;
    event.preventDefault();
    target = clamp(target + delta / (step * 1.8));
    requestRender();
    clearTimeout(settleTimer);
    settleTimer = setTimeout(() => goTo(target), 160);
  }, { passive: false });

  window.addEventListener('resize', measure);
  reducedMotion.addEventListener('change', requestRender);
  // Restore the viewed project after returning from an internal case study.
  try { target = position = clamp(Number(sessionStorage.getItem('portfolio-project')) || 0); } catch (_) { /* Storage may be unavailable. */ }
  window.addEventListener('pagehide', () => {
    try { sessionStorage.setItem('portfolio-project', String(selected)); } catch (_) { /* Optional persistence. */ }
  });
  document.body.classList.add('has-carousel');
  stage.classList.add('is-ready');
  measure();
})();
