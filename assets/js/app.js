// НейроПрактик — 3D-поведение: прогресс, меню, tilt, параллакс, reveal
(function () {
  "use strict";

  document.documentElement.classList.add('js');

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- прогресс-бар ---------- */
  var progress = document.getElementById('progress');
  if (progress) {
    window.addEventListener('scroll', function () {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      progress.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
    }, { passive: true });
  }

  /* ---------- мобильное меню ---------- */
  var burger = document.getElementById('burger');
  var links = document.getElementById('navLinks');
  if (burger && links) {
    burger.addEventListener('click', function () { links.classList.toggle('open'); });
    links.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') links.classList.remove('open');
    });
  }

  /* ---------- reveal при скролле ---------- */
  var revealEls = Array.prototype.slice.call(document.querySelectorAll('.reveal'));
  if (revealEls.length && 'IntersectionObserver' in window) {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in-view');
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { revealObserver.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add('in-view'); });
  }

  /* ---------- 3D-tilt по курсору ---------- */
  var MAX_TILT = 8; // градусы
  function bindTilt(el) {
    if (reduced) return;
    el.addEventListener('mousemove', function (e) {
      var r = el.getBoundingClientRect();
      var px = (e.clientX - r.left) / r.width - 0.5;
      var py = (e.clientY - r.top) / r.height - 0.5;
      var rx = (-py * MAX_TILT).toFixed(2);
      var ry = (px * MAX_TILT).toFixed(2);
      el.style.transform = 'perspective(1000px) rotateX(' + rx + 'deg) rotateY(' + ry + 'deg) translateY(-4px)';
    });
    el.addEventListener('mouseleave', function () {
      el.style.transform = '';
    });
  }
  document.querySelectorAll('.tilt3d').forEach(bindTilt);

  /* ---------- параллакс орбов и hero-стека ---------- */
  var orbs = Array.prototype.slice.call(document.querySelectorAll('.orb'));
  var stack = document.querySelector('.hero-stack');
  if (!reduced && (orbs.length || stack)) {
    var hero = document.querySelector('.hero');
    if (hero) {
      hero.addEventListener('mousemove', function (e) {
        var r = hero.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - 0.5;
        var py = (e.clientY - r.top) / r.height - 0.5;
        orbs.forEach(function (orb, i) {
          var depth = (i + 1) * 14;
          orb.style.transform = 'translate(' + (px * depth).toFixed(1) + 'px,' + (py * depth).toFixed(1) + 'px)';
        });
        if (stack) {
          stack.style.transform = 'rotateY(' + (px * 6).toFixed(2) + 'deg) rotateX(' + (-py * 4).toFixed(2) + 'deg)';
        }
      });
      hero.addEventListener('mouseleave', function () {
        orbs.forEach(function (orb) { orb.style.transform = ''; });
        if (stack) stack.style.transform = '';
      });
    }
  }

  /* ---------- активный урок в оглавлении ---------- */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc-lessons a'));
  if (tocLinks.length && 'IntersectionObserver' in window) {
    var byId = {};
    tocLinks.forEach(function (a) { byId[a.getAttribute('href').slice(1)] = a; });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          tocLinks.forEach(function (a) { a.classList.remove('active'); });
          var link = byId[entry.target.id];
          if (link) link.classList.add('active');
        }
      });
    }, { rootMargin: '-20% 0px -70% 0px' });
    tocLinks.forEach(function (a) {
      var el = document.getElementById(a.getAttribute('href').slice(1));
      if (el) observer.observe(el);
    });
  }
})();
