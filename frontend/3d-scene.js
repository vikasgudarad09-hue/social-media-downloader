/**
 * JPMediaSaver & File2File — 3D Interactive Spatial Engine
 * ─────────────────────────────────────────────────────────────────────────────
 * • File2File: Clean, eye-friendly, calm ambient cosmic backdrop
 * • JPMediaSaver: Deep Cosmic Constellation & Media Stream Web
 * • Interactive 3D Card Tilt with Specular Glare Reflection & Layered translateZ Depth
 * • Gravitational Particle Pull & Click Shockwave Ripples
 * • Synthesized Spatial Audio FX via Web Audio API
 * ─────────────────────────────────────────────────────────────────────────────
 */

(function () {
  'use strict';

  // ─────────────────────────────────────────────────────────────
  // 1. Synthesized Futuristic Spatial Audio (Web Audio API)
  // ─────────────────────────────────────────────────────────────
  let audioCtx = null;
  let soundEnabled = true;

  function initAudio() {
    if (!audioCtx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) audioCtx = new AudioContext();
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
  }

  function playHoverChime(freq = 520) {
    if (!soundEnabled || !audioCtx) return;
    try {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(freq * 1.5, audioCtx.currentTime + 0.08);

      gain.gain.setValueAtTime(0.015, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.12);

      osc.connect(gain);
      gain.connect(audioCtx.destination);

      osc.start();
      osc.stop(audioCtx.currentTime + 0.12);
    } catch (_) {}
  }

  function playClickPulse() {
    if (!soundEnabled || !audioCtx) return;
    try {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(180, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(60, audioCtx.currentTime + 0.07);

      gain.gain.setValueAtTime(0.035, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.08);

      osc.connect(gain);
      gain.connect(audioCtx.destination);

      osc.start();
      osc.stop(audioCtx.currentTime + 0.08);
    } catch (_) {}
  }

  ['click', 'keydown', 'pointerdown'].forEach((evt) => {
    window.addEventListener(evt, initAudio, { once: true, passive: true });
  });

  // ─────────────────────────────────────────────────────────────
  // 2. 3D Spatial Canvas Universe
  // ─────────────────────────────────────────────────────────────
  function init3DBackground() {
    let canvas = document.getElementById('bg-3d-canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'bg-3d-canvas';
      canvas.style.position = 'fixed';
      canvas.style.top = '0';
      canvas.style.left = '0';
      canvas.style.width = '100vw';
      canvas.style.height = '100vh';
      canvas.style.pointerEvents = 'none';
      canvas.style.zIndex = '0';
      canvas.style.opacity = '0.9';
      document.body.prepend(canvas);
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let dpr = 1;

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.scale(dpr, dpr);
    }
    window.addEventListener('resize', resize, { passive: true });
    resize();

    const isFormShift = window.location.pathname.includes('formshift') || !!document.querySelector('.lab-card');

    // Mouse tracking & momentum
    const mouse = {
      x: width / 2,
      y: height / 2,
      targetX: width / 2,
      targetY: height / 2,
      crankActivity: 0
    };

    window.addEventListener('mousemove', (e) => {
      mouse.targetX = e.clientX;
      mouse.targetY = e.clientY;
      mouse.crankActivity = Math.min(mouse.crankActivity + 0.15, 4);
    }, { passive: true });

    // Shockwave Ripples
    const shockwaves = [];
    window.addEventListener('click', (e) => {
      initAudio();
      playClickPulse();
      mouse.crankActivity = Math.min(mouse.crankActivity + 1.2, 5);

      shockwaves.push({
        x: e.clientX,
        y: e.clientY,
        radius: 10,
        maxRadius: Math.max(width, height) * 0.45,
        alpha: 0.75,
        speed: 13
      });
    }, { passive: true });

    // Ambient Depth Particles
    const PARTICLE_COUNT = Math.min(width < 768 ? 40 : 80, 100);
    const particles = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: (Math.random() - 0.5) * width * 1.5,
        y: (Math.random() - 0.5) * height * 1.5,
        z: Math.random() * 800 + 80,
        baseSize: Math.random() * 1.5 + 0.8,
        colorRGB: i % 3 === 0 ? '115, 243, 239' : (i % 3 === 1 ? '168, 85, 247' : '251, 191, 36'),
        speedZ: Math.random() * 0.3 + 0.12
      });
    }
    // ─────────────────────────────────────────────────────────────
    // 3. Calm & Clean Ambient Background
    // ─────────────────────────────────────────────────────────────

    // ─────────────────────────────────────────────────────────────
    // 4. Main Animation Frame Loop
    // ─────────────────────────────────────────────────────────────
    let isVisible = true;
    document.addEventListener('visibilitychange', () => {
      isVisible = !document.hidden;
    });

    function project(x, y, z, cx, cy) {
      const scale = 550 / (550 + z);
      return {
        x: cx + x * scale,
        y: cy + y * scale,
        scale,
        visible: z > -550
      };
    }

    let globalAnimTime = 0;

    function renderScene() {
      requestAnimationFrame(renderScene);
      if (!isVisible) return;

      globalAnimTime += 16;
      const time = globalAnimTime;

      // Mouse easing
      mouse.x += (mouse.targetX - mouse.x) * 0.05;
      mouse.y += (mouse.targetY - mouse.y) * 0.05;
      mouse.crankActivity = Math.max(0, mouse.crankActivity - 0.025);

      const parallaxX = (mouse.x - width / 2) * 0.05;
      const parallaxY = (mouse.y - height / 2) * 0.05;

      ctx.clearRect(0, 0, width, height);

      // ── Render Shockwaves ──
      for (let i = shockwaves.length - 1; i >= 0; i--) {
        const sw = shockwaves[i];
        sw.radius += sw.speed;
        sw.alpha -= 0.022;

        if (sw.alpha <= 0 || sw.radius >= sw.maxRadius) {
          shockwaves.splice(i, 1);
          continue;
        }

        ctx.save();
        ctx.lineWidth = 2.5;
        ctx.strokeStyle = `rgba(115, 243, 239, ${sw.alpha * 0.7})`;
        ctx.beginPath();
        ctx.arc(sw.x, sw.y, sw.radius, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }

      // ── Render Ambient Cosmic Particles & Constellation Web ──
      const projectedParticles = [];
      particles.forEach((p) => {
        p.z -= p.speedZ * 60 * 0.016;
        if (p.z < 60) p.z = 850;

        const pX = p.x - parallaxX * (500 / p.z);
        const pY = p.y - parallaxY * (500 / p.z);
        const proj = project(pX, pY, p.z, width / 2, height / 2);

        if (proj.visible) {
          projectedParticles.push({ x: proj.x, y: proj.y, size: p.baseSize * proj.scale, color: p.colorRGB });
          const alpha = Math.min((850 - p.z) / 450, 0.65);
          ctx.fillStyle = `rgba(${p.colorRGB}, ${alpha})`;
          ctx.beginPath();
          ctx.arc(proj.x, proj.y, Math.max(0.6, p.baseSize * proj.scale), 0, Math.PI * 2);
          ctx.fill();
        }
      });

      // Connect constellation lines
      const maxDist = 90;
      ctx.lineWidth = 0.5;
      for (let i = 0; i < projectedParticles.length; i++) {
        for (let j = i + 1; j < projectedParticles.length; j++) {
          const p1 = projectedParticles[i];
          const p2 = projectedParticles[j];
          const d = Math.hypot(p1.x - p2.x, p1.y - p2.y);
          if (d < maxDist) {
            ctx.strokeStyle = `rgba(168, 85, 247, ${(1 - d / maxDist) * 0.18})`;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }
    }

    requestAnimationFrame(renderScene);
  }

  // ─────────────────────────────────────────────────────────────
  // 6. Interactive 3D Card Tilt with Specular Glare & Layer Pop
  // ─────────────────────────────────────────────────────────────
  function init3DTilt() {
    const tiltElements = document.querySelectorAll('.tilt-3d');

    tiltElements.forEach((el) => {
      let glare = el.querySelector('.tilt-glare');
      if (!glare) {
        glare = document.createElement('div');
        glare.className = 'tilt-glare';
        el.appendChild(glare);
      }

      let bounds = null;
      let rafId = null;

      function onMouseEnter() {
        bounds = el.getBoundingClientRect();
        playHoverChime(620);
      }

      function onMouseMove(e) {
        if (!bounds) bounds = el.getBoundingClientRect();

        const x = e.clientX - bounds.left;
        const y = e.clientY - bounds.top;

        const centerX = bounds.width / 2;
        const centerY = bounds.height / 2;

        const maxAngle = parseFloat(el.getAttribute('data-tilt-max') || '10');
        const rotateX = ((y - centerY) / centerY) * -maxAngle;
        const rotateY = ((x - centerX) / centerX) * maxAngle;

        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(() => {
          el.style.transform = `perspective(1200px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateZ(8px) scale3d(1.018, 1.018, 1.018)`;

          // Elevated 3D layer pop
          const frontLayers = el.querySelectorAll('.layer-3d-front, button, .dropzone, input, select');
          frontLayers.forEach((layer) => {
            layer.style.transform = 'translateZ(26px)';
            layer.style.transition = 'transform 0.15s ease';
          });

          // Specular glare reflection
          const glareX = (x / bounds.width) * 100;
          const glareY = (y / bounds.height) * 100;
          glare.style.background = `radial-gradient(circle 320px at ${glareX}% ${glareY}%, rgba(255, 255, 255, 0.2), transparent 75%)`;
          glare.style.opacity = '1';
        });
      }

      function onMouseLeave() {
        bounds = null;
        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(() => {
          el.style.transform = 'perspective(1200px) rotateX(0deg) rotateY(0deg) translateZ(0px) scale3d(1, 1, 1)';
          glare.style.opacity = '0';

          const frontLayers = el.querySelectorAll('.layer-3d-front, button, .dropzone, input, select');
          frontLayers.forEach((layer) => {
            layer.style.transform = 'translateZ(0px)';
          });
        });
      }

      el.addEventListener('mouseenter', onMouseEnter, { passive: true });
      el.addEventListener('mousemove', onMouseMove, { passive: true });
      el.addEventListener('mouseleave', onMouseLeave, { passive: true });
    });
  }

  // ─────────────────────────────────────────────────────────────
  // 7. Interactive 3D Cursor Lighting Follower
  // ─────────────────────────────────────────────────────────────
  function init3DCursorAura() {
    if (window.innerWidth < 768) return;

    let aura = document.getElementById('cursor-3d-aura');
    if (!aura) {
      aura = document.createElement('div');
      aura.id = 'cursor-3d-aura';
      aura.style.position = 'fixed';
      aura.style.width = '360px';
      aura.style.height = '360px';
      aura.style.borderRadius = '50%';
      aura.style.pointerEvents = 'none';
      aura.style.zIndex = '1';
      aura.style.transform = 'translate(-50%, -50%)';
      aura.style.background = 'radial-gradient(circle, rgba(99, 102, 241, 0.07) 0%, rgba(115, 243, 239, 0.035) 45%, transparent 70%)';
      aura.style.transition = 'opacity 0.3s ease';
      aura.style.opacity = '0';
      document.body.appendChild(aura);
    }

    let cx = window.innerWidth / 2;
    let cy = window.innerHeight / 2;
    let tx = cx, ty = cy;

    window.addEventListener('mousemove', (e) => {
      tx = e.clientX;
      ty = e.clientY;
      aura.style.opacity = '1';
    }, { passive: true });

    window.addEventListener('mouseleave', () => {
      aura.style.opacity = '0';
    });

    function loop() {
      cx += (tx - cx) * 0.12;
      cy += (ty - cy) * 0.12;
      aura.style.left = `${cx}px`;
      aura.style.top = `${cy}px`;
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
  }

  // ─────────────────────────────────────────────────────────────
  // 8. Sound Control Toggle Button
  // ─────────────────────────────────────────────────────────────
  function initSoundToggle() {
    let toggleBtn = document.getElementById('btn-sound-toggle');
    if (!toggleBtn) {
      const navContainer = document.querySelector('header nav, header .space-x-2, header .flex.items-center');
      if (navContainer) {
        toggleBtn = document.createElement('button');
        toggleBtn.id = 'btn-sound-toggle';
        toggleBtn.type = 'button';
        toggleBtn.className = 'inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-semibold bg-slate-900/90 border border-slate-800 text-slate-300 hover:text-cyan-300 hover:border-cyan-400/50 transition cursor-pointer select-none';
        toggleBtn.title = 'Toggle 3D Audio FX';
        toggleBtn.innerHTML = '<i class="fa-solid fa-volume-high text-xs text-cyan-400"></i><span class="hidden sm:inline">3D Sound</span>';

        toggleBtn.addEventListener('click', () => {
          initAudio();
          soundEnabled = !soundEnabled;
          if (soundEnabled) {
            toggleBtn.innerHTML = '<i class="fa-solid fa-volume-high text-xs text-cyan-400"></i><span class="hidden sm:inline">3D Sound</span>';
            playHoverChime(700);
          } else {
            toggleBtn.innerHTML = '<i class="fa-solid fa-volume-xmark text-xs text-slate-500"></i><span class="hidden sm:inline text-slate-500">Muted</span>';
          }
        });

        navContainer.appendChild(toggleBtn);
      }
    }
  }

  // ─────────────────────────────────────────────────────────────
  // 9. Boot on DOM Ready
  // ─────────────────────────────────────────────────────────────
  function boot() {
    init3DBackground();
    init3DTilt();
    init3DCursorAura();
    initSoundToggle();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.init3DScene = {
    init3DBackground,
    init3DTilt,
    playHoverChime,
    playClickPulse
  };
})();
