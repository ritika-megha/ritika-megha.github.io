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
  const gestureArea = stage.closest('.collection');
  const discs = [...stage.querySelectorAll('.disc')];
  if (!discs.length) return;
  const title = document.getElementById('project-title');
  const category = document.getElementById('project-category');
  const collection = document.getElementById('project-collection');
  const collectionRow = document.getElementById('project-collection-row');
  const open = document.getElementById('open-project');
  const linkContext = document.getElementById('open-project-context');
  const number = document.getElementById('current-number');
  const status = document.getElementById('carousel-status');
  let audioContext;
  let tickBuffer;
  let lastTick = -Infinity;
  let lastSoundPosition = 0;

  function unlockSound() {
    try {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) return;
      if (!audioContext) {
        audioContext = new Audio();
        tickBuffer = audioContext.createBuffer(1, Math.ceil(audioContext.sampleRate * 0.022), audioContext.sampleRate);
        const samples = tickBuffer.getChannelData(0);
        for (let i = 0; i < samples.length; i++) samples[i] = (Math.random() * 2 - 1) * Math.exp(-i / (samples.length * 0.18));
      }
      if (audioContext.state === 'suspended') audioContext.resume().catch(() => {});
    } catch (_) { /* Browsing still works when audio is unavailable. */ }
  }

  function playTick() {
    if (!audioContext || audioContext.state !== 'running' || document.hidden) return;
    const now = audioContext.currentTime;
    if (now - lastTick < 0.035) return;
    lastTick = now;
    const source = audioContext.createBufferSource();
    const filter = audioContext.createBiquadFilter();
    const gain = audioContext.createGain();
    source.buffer = tickBuffer;
    filter.type = 'bandpass';
    filter.frequency.value = 1700;
    filter.Q.value = 0.8;
    gain.gain.value = 0.14;
    source.connect(filter).connect(gain).connect(audioContext.destination);
    source.onended = () => { source.disconnect(); filter.disconnect(); gain.disconnect(); };
    source.start(now);
  }

  // Browsers unlock audio after a visitor gesture, including touch release.
  document.addEventListener('pointerdown', unlockSound);
  document.addEventListener('pointerup', unlockSound);
  document.addEventListener('touchend', unlockSound, { passive: true });
  document.addEventListener('keydown', unlockSound);
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
  let swing = 0;
  let swingVelocity = 0;
  let renderedPosition = 0;
  let lastMovementDirection = 1;
  const hoverMotion = discs.map(() => ({ tilt: 0, velocity: 0, target: 0 }));

  discs.forEach((disc, index) => {
    disc.addEventListener('pointerenter', event => {
      if (event.pointerType !== 'mouse' || event.buttons || dragging() || reducedMotion.matches) return;
      // Hover leans against the last scroll direction, on this disc only.
      hoverMotion[index].target = -9 * lastMovementDirection;
      requestRender();
    });
    disc.addEventListener('pointerleave', () => {
      hoverMotion[index].target = 0;
      requestRender();
    });
  });

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
    // Small position increments create a soft ratchet while moving either way.
    if (Math.abs(position - lastSoundPosition) >= 0.075) {
      playTick();
      lastSoundPosition = position;
    }
    const mobile = stage.clientWidth <= 600;
    const rise = mobile ? 55 : Math.min(115, stage.clientHeight * 0.2);
    discs.forEach((disc, i) => {
      const offset = i - position;
      const visible = Math.abs(offset) < 3.2;
      const scale = Math.max(0.38, Math.min(1.45, Math.pow(1.23, offset)));
      const tilt = swing * Math.cos(offset * 0.65) + hoverMotion[i].tilt;
      disc.style.transform = `translate(-50%, -50%) translate(${offset * step}px, ${-offset * rise}px) scale(${scale}) perspective(1100px) translateZ(${tilt * 4}px) rotateY(${-24 + tilt * 0.8}deg) rotateX(${12 + tilt * 1.2}deg) rotateZ(20deg)`;
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
    if (reducedMotion.matches) {
      swing = swingVelocity = 0;
      hoverMotion.forEach(motion => { motion.tilt = motion.velocity = motion.target = 0; });
    } else {
      // A damped spring responds to movement, then comes to rest (no idle sway).
      const dt = elapsed / 1000;
      const travel = position - renderedPosition;
      if (Math.abs(travel) > 0.0001) lastMovementDirection = Math.sign(travel);
      swingVelocity += travel * 190;
      swingVelocity += (-55 * swing - 7 * swingVelocity) * dt;
      swing = Math.max(-12, Math.min(12, swing + swingVelocity * dt));
      if (Math.abs(swing) < 0.015 && Math.abs(swingVelocity) < 0.04) swing = swingVelocity = 0;
      hoverMotion.forEach(motion => {
        motion.velocity += (65 * (motion.target - motion.tilt) - 9 * motion.velocity) * dt;
        motion.tilt += motion.velocity * dt;
        if (Math.abs(motion.target - motion.tilt) < 0.015 && Math.abs(motion.velocity) < 0.04) {
          motion.tilt = motion.target;
          motion.velocity = 0;
        }
      });
    }
    renderedPosition = position;
    render();
    if ((!dragging() && position !== target) || swing !== 0 || swingVelocity !== 0 || hoverMotion.some(motion => motion.tilt !== motion.target || motion.velocity !== 0)) frame = requestAnimationFrame(animate);
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
    step = size * (stage.clientWidth <= 600 ? 0.93 : 0.88);
    requestRender();
  }

  stage.addEventListener('keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const keys = { ArrowLeft: Math.round(target) - 1, ArrowRight: Math.round(target) + 1, Home: 0, End: discs.length - 1 };
    if (!(event.key in keys)) return;
    event.preventDefault();
    goTo(keys[event.key]);
  });

  gestureArea.addEventListener('pointerdown', event => {
    if (!event.isPrimary || event.button !== 0) return;
    clearTimeout(settleTimer);
    hoverMotion.forEach(motion => { motion.target = 0; });
    pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, start: position, axis: event.pointerType === 'mouse' ? 'x' : null, lastDistance: 0, lastTime: performance.now(), velocity: 0, dragging: false };
    target = position;
  });

  gestureArea.addEventListener('pointermove', event => {
    if (!pointer || pointer.id !== event.pointerId) return;
    const dx = event.clientX - pointer.x;
    const dy = event.clientY - pointer.y;
    if (!pointer.dragging) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) < 7) return;
      if (!pointer.axis) pointer.axis = Math.abs(dy) > Math.abs(dx) ? 'y' : 'x';
      if (pointer.axis === 'x' && Math.abs(dx) < 7) return;
      pointer.dragging = true;
      stage.setPointerCapture(event.pointerId);
      stage.classList.add('is-dragging');
    }
    // Lock to the initial dominant axis so diagonal swipes stay predictable.
    // Swiping up or left advances; down or right returns to previous work.
    const distance = pointer.axis === 'y' ? dy : dx;
    const time = performance.now();
    const velocity = (distance - pointer.lastDistance) / Math.max(1, time - pointer.lastTime);
    pointer.velocity = pointer.velocity * 0.4 + velocity * 0.6;
    pointer.lastDistance = distance;
    pointer.lastTime = time;
    position = clamp(pointer.start - distance / step);
    target = position;
    requestRender();
  });

  function release(event) {
    if (!pointer || pointer.id !== event.pointerId) return;
    // Touch starts with implicit capture on the pressed disc. Its capture-loss
    // event bubbles when we transfer capture to the stage; the swipe is ongoing.
    if (event.type === 'lostpointercapture' && event.target !== stage) return;
    const wasDragging = pointer.dragging;
    const recent = performance.now() - pointer.lastTime < 100;
    const velocity = event.type === 'pointerup' && recent ? Math.max(-2, Math.min(2, pointer.velocity)) : 0;
    pointer = null;
    stage.classList.remove('is-dragging');
    if (stage.hasPointerCapture(event.pointerId)) stage.releasePointerCapture(event.pointerId);
    if (wasDragging) {
      suppressClickUntil = performance.now() + 350;
      goTo(position - velocity * 110 / step);
    } else goTo(position);
  }
  gestureArea.addEventListener('pointerup', release);
  gestureArea.addEventListener('pointercancel', release);
  gestureArea.addEventListener('lostpointercapture', release);
  window.addEventListener('pointerup', release);
  stage.addEventListener('dragstart', event => event.preventDefault());
  gestureArea.addEventListener('click', event => {
    if (performance.now() < suppressClickUntil) event.preventDefault();
  }, true);

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

  gestureArea.addEventListener('wheel', event => {
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
  lastSoundPosition = renderedPosition = position;
  window.addEventListener('pagehide', () => {
    try { sessionStorage.setItem('portfolio-project', String(selected)); } catch (_) { /* Optional persistence. */ }
  });
  document.body.classList.add('has-carousel');
  stage.classList.add('is-ready');
  measure();
})();
