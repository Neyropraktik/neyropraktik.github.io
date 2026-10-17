// НейроПрактик 2026 — интерактивный слой курса
// Возможности: интерактивные тесты, трекер прогресса (localStorage),
// копирование промптов, тёмная тема, «наверх», футер-уведомления.
// Подключается ПОСЛЕ app.js.
(function () {
  "use strict";

  var doc = document;
  var PROGRESS_KEY = "np-progress-v1";
  var QUIZ_KEY = "np-quiz-v1";
  var THEME_KEY = "np-theme";

  /* ---------- безопасное хранилище ---------- */

  var store = {
    get: function (key, fallback) {
      try {
        var raw = localStorage.getItem(key);
        return raw === null ? fallback : JSON.parse(raw);
      } catch (e) { return fallback; }
    },
    set: function (key, value) {
      try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ }
    }
  };

  /* ---------- модель прогресса ---------- */
  // Отдельно учитываемые элементы: уроки (h2), задания (.task), тесты (.test), финал.
  var MODULE_TOTALS = { 1: 5, 2: 6, 3: 6, 4: 5, 5: 6 }; // уроки + задания + тест (в модуле 5 — + финальный чек-лист)
  var COURSE_TOTAL = 28;

  var progress = store.get(PROGRESS_KEY, { items: {} });
  if (!progress || typeof progress !== "object" || !progress.items) progress = { items: {} };

  function moduleOf(id) {
    var m = id.match(/^lesson-(\d)-/);
    if (m) return parseInt(m[1], 10);
    m = id.match(/^(?:task|test)-(\d)$/);
    if (m) return parseInt(m[1], 10);
    if (id === "final") return 5;
    return 0;
  }

  function isDone(id) {
    var rec = progress.items[id];
    return !!(rec && rec.d);
  }

  function setDone(id, val) {
    var mod = moduleOf(id);
    var beforeMod = mod ? doneInModule(mod) : 0;
    var beforeAll = doneTotal();
    if (val) progress.items[id] = { d: 1, t: Date.now() };
    else delete progress.items[id];
    store.set(PROGRESS_KEY, progress);

    if (val && mod) {
      var afterMod = doneInModule(mod);
      if (afterMod === MODULE_TOTALS[mod] && beforeMod < afterMod) toast("Модуль " + mod + " пройден полностью!");
    }
    var afterAll = doneTotal();
    if (val && afterAll === COURSE_TOTAL && beforeAll < afterAll) {
      toast("Весь курс пройден. Респект!");
      burstConfetti();
    }
    refresh();
  }

  function doneInModule(m) {
    var n = 0;
    Object.keys(progress.items).forEach(function (id) {
      if (moduleOf(id) === m && isDone(id)) n++;
    });
    return n;
  }

  function doneTotal() {
    var n = 0;
    Object.keys(progress.items).forEach(function (id) { if (isDone(id)) n++; });
    return n;
  }

  function lastDoneTs() {
    var best = 0;
    Object.keys(progress.items).forEach(function (id) {
      var rec = progress.items[id];
      if (rec && rec.d && rec.t > best) best = rec.t;
    });
    return best;
  }

  /* ---------- уведомления ---------- */

  var toastEl = null, toastTimer = null, confettiRunning = false;

  function toast(msg) {
    if (!toastEl) {
      toastEl = doc.createElement("div");
      toastEl.className = "np-toast";
      toastEl.setAttribute("role", "status");
      doc.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 2800);
  }

  /* ---------- конфетти (5/5 и полный курс) ---------- */

  function burstConfetti() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || confettiRunning) return;
    confettiRunning = true;
    var colors = ["#5b3df5", "#8f76ff", "#e8a33d", "#2aa968", "#ffffff"];
    var parts = [];
    for (var i = 0; i < 30; i++) {
      var el = doc.createElement("i");
      el.style.cssText = "position:fixed;left:" + (38 + Math.random() * 24) + "%;top:34%;width:8px;height:13px;"
        + "border-radius:2px;z-index:300;pointer-events:none;background:" + colors[i % colors.length] + ";";
      doc.body.appendChild(el);
      parts.push({
        el: el, x: 0, y: 0,
        vx: (Math.random() - 0.5) * 12,
        vy: -(6 + Math.random() * 8),
        rot: Math.random() * 360,
        vr: (Math.random() - 0.5) * 24
      });
    }
    var t = null;
    function frame(ts) {
      if (t === null) t = ts;
      var dt = Math.min(40, ts - t); t = ts;
      var alive = false;
      for (var i = 0; i < parts.length; i++) {
        var p = parts[i];
        p.vy += 0.35 * (dt / 16);
        p.x += p.vx * (dt / 16);
        p.y += p.vy * (dt / 16);
        p.rot += p.vr * (dt / 16);
        p.el.style.transform = "translate(" + p.x + "px," + p.y + "px) rotate(" + p.rot + "deg)";
        if (p.y < 460) alive = true;
      }
      if (alive) { window.requestAnimationFrame(frame); return; }
      for (var j = 0; j < parts.length; j++) parts[j].el.remove();
      confettiRunning = false;
    }
    window.requestAnimationFrame(frame);
  }

  /* =========================================================
     1. Интерактивные тесты
     ========================================================= */

  var LETTERS = ["а", "б", "в", "г"];

  function parseAnswerKey(text) {
    var map = {}; // вопрос(1-based) -> индекс буквы
    var re = /(\d+)\s*[-–—]\s*([а-гё])/g, m;
    while ((m = re.exec(text)) !== null) {
      map[parseInt(m[1], 10)] = LETTERS.indexOf(m[2].toLowerCase());
    }
    return map;
  }

  function parseTest(testEl) {
    var list = testEl.querySelector(":scope > ol");
    if (!list) return null;
    var items = [];
    var qEls = list.querySelectorAll(":scope > li");
    for (var i = 0; i < qEls.length; i++) {
      var li = qEls[i];
      var clone = li.cloneNode(true);
      var ul = clone.querySelector("ul");
      if (ul) ul.remove();
      var qText = (clone.textContent || "").replace(/\s+/g, " ").trim();

      var opts = [];
      var optUl = li.querySelector(":scope > ul");
      if (optUl) {
        var raw = (optUl.textContent || "").split(";");
        for (var j = 0; j < raw.length; j++) {
          var part = raw[j].trim();
          var m = part.match(/^([а-гё])\)\s*([\s\S]+)$/i);
          if (!m) continue;
          opts.push(m[2].replace(/\s*\.$/, "").trim());
        }
      }
      items.push({ q: qText, opts: opts });
    }
    var ansEl = testEl.querySelector(".test-answer");
    var key = ansEl ? parseAnswerKey(ansEl.textContent || "") : {};
    return { list: list, ansEl: ansEl, items: items, key: key };
  }

  var quizzes = store.get(QUIZ_KEY, {});

  function quizState(testId, numQ) {
    var st = quizzes[testId];
    if (!st || !Array.isArray(st.chosen) || st.chosen.length !== numQ) {
      st = { chosen: [], graded: false, score: 0 };
      for (var i = 0; i < numQ; i++) st.chosen.push(-1);
      st.numQ = numQ;
      quizzes[testId] = st;
    }
    return st;
  }

  function saveQuizState() { store.set(QUIZ_KEY, quizzes); }

  function buildQuiz(testEl) {
    if (testEl.dataset.quizDone) return;
    var data = parseTest(testEl);
    if (!data || !data.items.length) return;
    testEl.dataset.quizDone = "1";

    var testId = testEl.id || "test";
    var state = quizState(testId, data.items.length);

    var wrap = doc.createElement("div");
    wrap.className = "np-quiz";

    for (var qi = 0; qi < data.items.length; qi++) {
      var item = data.items[qi];
      var card = doc.createElement("div");
      card.className = "np-quiz-q";
      card.dataset.q = String(qi);

      var head = doc.createElement("div");
      head.className = "np-quiz-qtitle";
      var num = doc.createElement("span");
      num.className = "np-quiz-num";
      num.textContent = String(qi + 1);
      head.appendChild(num);
      head.appendChild(doc.createTextNode(item.q));
      card.appendChild(head);

      var box = doc.createElement("div");
      box.className = "np-quiz-opts";
      for (var oi = 0; oi < item.opts.length; oi++) {
        var label = doc.createElement("label");
        label.className = "np-quiz-opt";
        var input = doc.createElement("input");
        input.type = "radio";
        input.name = "np-" + testId + "-q" + qi;
        input.value = String(oi);
        if (state.chosen[qi] === oi) input.checked = true;
        label.appendChild(input);
        var letter = doc.createElement("span");
        letter.className = "np-quiz-letter";
        letter.textContent = LETTERS[oi].toUpperCase();
        label.appendChild(letter);
        var text = doc.createElement("span");
        text.className = "np-quiz-text";
        text.textContent = item.opts[oi];
        label.appendChild(text);
        if (state.chosen[qi] === oi) label.classList.add("picked");
        box.appendChild(label);
      }
      card.appendChild(box);
      wrap.appendChild(card);
    }

    var foot = doc.createElement("div");
    foot.className = "np-quiz-foot";
    var check = doc.createElement("button");
    check.type = "button";
    check.className = "btn btn-primary btn-small np-quiz-check";
    check.textContent = "Проверить ответы";
    var reset = doc.createElement("button");
    reset.type = "button";
    reset.className = "btn btn-ghost btn-small np-quiz-reset";
    reset.textContent = "Сбросить";
    foot.appendChild(check);
    foot.appendChild(reset);
    wrap.appendChild(foot);

    var result = doc.createElement("div");
    result.className = "np-quiz-result";
    result.setAttribute("role", "status");
    result.setAttribute("aria-live", "polite");
    wrap.appendChild(result);

    // прячем исходный статичный список и строку ответов (остаются для no-JS)
    data.list.style.display = "none";
    if (data.ansEl) data.ansEl.hidden = true;

    testEl.appendChild(wrap);

    wrap.addEventListener("change", function (e) {
      var input = e.target;
      if (!input || input.type !== "radio") return;
      var card = input.closest(".np-quiz-q");
      var qi = parseInt(card.dataset.q, 10);
      state.chosen[qi] = parseInt(input.value, 10);
      saveQuizState();
      // снятие подсветки ответов этого вопроса
      card.classList.remove("missing");
      var labels = card.querySelectorAll(".np-quiz-opt");
      for (var i = 0; i < labels.length; i++) {
        labels[i].classList.remove("correct", "wrong");
      }
    });

    function clearGrades() {
      state.graded = false;
      state.score = 0;
      var labels = wrap.querySelectorAll(".np-quiz-opt");
      for (var i = 0; i < labels.length; i++) labels[i].classList.remove("correct", "wrong");
      result.className = "np-quiz-result";
      result.textContent = "";
    }

    function showResult(score, total) {
      result.classList.add("show");
      if (score === total) {
        result.classList.add("ok");
        result.textContent = "Идеально — " + score + " из " + total + "! Тест сдан.";
      } else if (score >= total - 1) {
        result.classList.add("mid");
        result.textContent = score + " из " + total + " — почти! Перечитайте вопрос, где ошиблись.";
      } else {
        result.classList.add("bad");
        result.textContent = score + " из " + total + " — перечитайте уроки модуля и попробуйте снова.";
      }
    }

    function applyGrades() {
      for (var qi = 0; qi < data.items.length; qi++) {
        var correctIdx = typeof data.key[qi + 1] === "number" ? data.key[qi + 1] : -1;
        if (correctIdx < 0) continue;
        var card = wrap.querySelectorAll(".np-quiz-q")[qi];
        var labels = card.querySelectorAll(".np-quiz-opt");
        for (var oi = 0; oi < labels.length; oi++) {
          if (oi === correctIdx) labels[oi].classList.add("correct");
          else if (state.chosen[qi] === oi) labels[oi].classList.add("wrong");
        }
      }
    }

    check.addEventListener("click", function () {
      var missing = -1;
      for (var qi = 0; qi < data.items.length; qi++) {
        if (state.chosen[qi] < 0) { missing = qi; break; }
      }
      var cards = wrap.querySelectorAll(".np-quiz-q");
      if (missing >= 0) {
        cards[missing].classList.add("missing");
        result.className = "np-quiz-result bad show";
        result.textContent = "Ответьте на все вопросы — подсвечен вопрос №" + (missing + 1) + ".";
        cards[missing].scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      clearGrades();
      applyGrades();
      var score = 0;
      for (var q = 0; q < data.items.length; q++) {
        if (state.chosen[q] === data.key[q + 1]) score++;
      }
      state.graded = true;
      state.score = score;
      saveQuizState();
      showResult(score, data.items.length);
      if (score === data.items.length) {
        burstConfetti();
        toast("Тест сдан: 5 из 5. Так держать!");
      }
      if (testEl.id && /^test-\d$/.test(testEl.id)) setDoneAuto(testEl.id);
    });

    reset.addEventListener("click", function () {
      clearGrades();
      state.chosen = [];
      for (var i = 0; i < data.items.length; i++) state.chosen.push(-1);
      saveQuizState();
      var inputs = wrap.querySelectorAll("input[type=radio]");
      for (var j = 0; j < inputs.length; j++) inputs[j].checked = false;
      var opts = wrap.querySelectorAll(".np-quiz-opt");
      for (var k = 0; k < opts.length; k++) opts[k].classList.remove("picked", "correct", "wrong");
      var qe = wrap.querySelectorAll(".np-quiz-q");
      for (var n = 0; n < qe.length; n++) qe[n].classList.remove("missing");
    });

    // восстановление после перезагрузки
    if (state.graded && state.score === data.items.length) {
      applyGrades();
      showResult(state.score, data.items.length);
      if (testEl.id && /^test-\d$/.test(testEl.id)) setDoneAuto(testEl.id);
    }
  }

  function setDoneAuto(testId) {
    if (!isDone(testId)) setDone(testId, true);
  }

  /* =========================================================
     2. Копирование промптов
     ========================================================= */

  function bindCopy() {
    var blocks = doc.querySelectorAll(".lesson-body blockquote, .lesson-body pre");
    for (var i = 0; i < blocks.length; i++) {
      var block = blocks[i];
      if (block.querySelector(".np-copy")) continue;
      if (block.closest(".np-quiz")) continue;

      var btn = doc.createElement("button");
      btn.type = "button";
      btn.className = "np-copy";
      btn.setAttribute("aria-label", "Копировать текст");
      btn.title = "Копировать текст";

      var icon = doc.createElementNS("http://www.w3.org/2000/svg", "svg");
      icon.setAttribute("width", "13");
      icon.setAttribute("height", "13");
      icon.setAttribute("viewBox", "0 0 24 24");
      icon.setAttribute("fill", "none");
      icon.setAttribute("stroke", "currentColor");
      icon.setAttribute("stroke-width", "2.4");
      var r1 = doc.createElementNS("http://www.w3.org/2000/svg", "rect");
      r1.setAttribute("x", "9"); r1.setAttribute("y", "9");
      r1.setAttribute("width", "11"); r1.setAttribute("height", "11");
      r1.setAttribute("rx", "2");
      var p1 = doc.createElementNS("http://www.w3.org/2000/svg", "path");
      p1.setAttribute("d", "M5 15V5a1 1 0 0 1 1-1h10");
      icon.appendChild(r1);
      icon.appendChild(p1);
      btn.appendChild(icon);
      btn.appendChild(doc.createElement("span"));

      var baseText = blockInnerText(block);
      btn.addEventListener("click", function () {
        var self = this;
        copyText(baseText).then(function () {
          markCopied(self, true);
        }, function () {
          markCopied(self, false);
        });
      });

      block.appendChild(btn);
      block.classList.add("np-copyable");
    }

    function markCopied(btn, ok) {
      var span = btn.querySelector("span");
      span.textContent = ok ? "Скопировано ✓" : "Не получилось";
      btn.classList.toggle("ok", ok);
      setTimeout(function () {
        span.textContent = "Копировать";
        btn.classList.remove("ok");
      }, 1600);
    }
  }

  function blockInnerText(block) {
    var clone = block.cloneNode(true);
    var btn = clone.querySelector(".np-copy");
    if (btn) btn.remove();
    return (clone.textContent || "").trim();
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () {
        return fallbackCopy(text);
      });
    }
    return fallbackCopy(text);
  }

  function fallbackCopy(text) {
    return new Promise(function (resolve, reject) {
      try {
        var ta = doc.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.cssText = "position:fixed;opacity:0;pointer-events:none;";
        doc.body.appendChild(ta);
        ta.focus();
        ta.select();
        var ok = doc.execCommand("copy");
        doc.body.removeChild(ta);
        ok ? resolve() : reject(new Error("copy failed"));
      } catch (e) { reject(e); }
    });
  }

  /* =========================================================
     3. Чипы «отметить пройденным»
     ========================================================= */

  function makeChip(itemId) {
    var chip = doc.createElement("button");
    chip.type = "button";
    chip.className = "np-chip";
    chip.dataset.item = itemId;
    chip.setAttribute("aria-pressed", isDone(itemId) ? "true" : "false");
    chip.textContent = isDone(itemId) ? "Пройдено ✓" : "Отметить пройденным";
    chip.addEventListener("click", function () {
      setDone(itemId, !isDone(itemId));
    });
    return chip;
  }

  function injectChips() {
    // уроки
    var heads = doc.querySelectorAll(".lesson-body h2[id^='lesson-']");
    for (var i = 0; i < heads.length; i++) {
      var h2 = heads[i];
      if (h2.querySelector(".np-chip")) continue;
      h2.appendChild(makeChip(h2.id));
    }
    // задания, тесты, финал
    var boxes = doc.querySelectorAll(".task[id], .test[id]");
    for (var j = 0; j < boxes.length; j++) {
      var box = boxes[j];
      if (box.querySelector(".np-chip")) continue;
      var chip = makeChip(box.id);
      var tag = box.querySelector(".task-tag");
      if (tag) tag.insertAdjacentElement("afterend", chip);
      else box.insertBefore(chip, box.firstChild);
    }
  }

  /* =========================================================
     4. Карточка прогресса в оглавлении (модули)
     ========================================================= */

  var MODULE_NAMES = { 1: "1. База", 2: "2. Формула промпта", 3: "3. Профессии", 4: "4. Автоматизация", 5: "5. Монетизация" };

  function renderProgressCard() {
    var toc = doc.querySelector(".toc");
    if (!toc || toc.querySelector(".np-progress")) return;

    var card = doc.createElement("div");
    card.className = "np-progress";

    var row = doc.createElement("div");
    row.className = "np-progress-row";
    row.appendChild(makeRing(24, 150.8, "np-ring"));
    var info = doc.createElement("div");
    info.className = "np-progress-info";
    var total = doc.createElement("b");
    var sub = doc.createElement("span");
    info.appendChild(total);
    info.appendChild(sub);
    row.appendChild(info);
    card.appendChild(row);

    var list = doc.createElement("ul");
    list.className = "np-progress-mods";
    for (var m = 1; m <= 5; m++) {
      var li = doc.createElement("li");
      var a = doc.createElement("a");
      a.href = "modul-" + m + ".html";
      a.textContent = MODULE_NAMES[m];
      var count = doc.createElement("span");
      count.className = "np-count";
      li.appendChild(a);
      li.appendChild(count);
      list.appendChild(li);
    }
    card.appendChild(list);

    var resetBtn = doc.createElement("button");
    resetBtn.type = "button";
    resetBtn.className = "np-progress-reset";
    resetBtn.textContent = "Сбросить прогресс";
    resetBtn.addEventListener("click", function () {
      if (!window.confirm("Сбросить весь прогресс курса?")) return;
      progress = { items: {} };
      quizzes = {};
      store.set(PROGRESS_KEY, progress);
      store.set(QUIZ_KEY, quizzes);
      window.location.reload();
    });
    card.appendChild(resetBtn);

    toc.insertBefore(card, toc.firstChild);
  }

  function makeRing(r, circumference, cls) {
    var ring = doc.createElement("div");
    ring.className = cls;
    var svg = doc.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 54 54");
    var bg = doc.createElementNS("http://www.w3.org/2000/svg", "circle");
    bg.setAttribute("class", "bg");
    bg.setAttribute("cx", "27"); bg.setAttribute("cy", "27"); bg.setAttribute("r", String(r));
    var fg = doc.createElementNS("http://www.w3.org/2000/svg", "circle");
    fg.setAttribute("class", "fg");
    fg.setAttribute("cx", "27"); fg.setAttribute("cy", "27"); fg.setAttribute("r", String(r));
    fg.setAttribute("stroke-dasharray", String(circumference));
    fg.setAttribute("stroke-dashoffset", String(circumference));
    svg.appendChild(bg); svg.appendChild(fg);
    var label = doc.createElement("b");
    ring.appendChild(svg);
    ring.appendChild(label);
    ring.dataset.circ = String(circumference);
    return ring;
  }

  /* =========================================================
     5. Обзор на странице программы
     ========================================================= */

  function renderProgramOverview() {
    var header = doc.querySelector(".lesson-header");
    if (!header || !doc.getElementById("module-1")) return;
    if (doc.querySelector(".np-course-progress")) return;

    var box = doc.createElement("div");
    box.className = "np-course-progress";

    var text = doc.createElement("div");
    text.className = "np-text";
    var b = doc.createElement("b");
    b.textContent = "Мой прогресс";
    var span = doc.createElement("span");
    text.appendChild(b);
    text.appendChild(span);
    box.appendChild(text);

    var bar = doc.createElement("div");
    bar.className = "np-bar";
    bar.appendChild(doc.createElement("i"));
    box.appendChild(bar);

    var cont = doc.createElement("a");
    cont.className = "btn btn-primary btn-small np-continue";
    cont.href = "modul-1.html";
    cont.textContent = "Начать курс";
    box.appendChild(cont);

    header.insertAdjacentElement("afterend", box);
  }

  function renderModuleBadges() {
    var heads = doc.querySelectorAll("h2[id^='module-']");
    for (var i = 0; i < heads.length; i++) {
      var h2 = heads[i];
      var m = parseInt(h2.id.replace("module-", ""), 10);
      if (!MODULE_TOTALS[m]) continue;
      var badge = h2.querySelector(".np-mod-badge");
      if (!badge) {
        badge = doc.createElement("span");
        badge.className = "np-mod-badge";
        h2.appendChild(badge);
      }
      var n = doneInModule(m);
      badge.textContent = n + " / " + MODULE_TOTALS[m];
      badge.classList.toggle("full", n === MODULE_TOTALS[m]);
    }
  }

  /* =========================================================
     6. Единый refresh всех виджетов прогресса
     ========================================================= */

  function refresh() {
    var total = doneTotal();
    var pct = COURSE_TOTAL ? Math.round((total / COURSE_TOTAL) * 100) : 0;

    // чипы и галочки
    var chips = doc.querySelectorAll(".np-chip");
    for (var i = 0; i < chips.length; i++) {
      var chip = chips[i];
      var d = isDone(chip.dataset.item);
      chip.classList.toggle("done", d);
      chip.setAttribute("aria-pressed", d ? "true" : "false");
      chip.textContent = d ? "Пройдено ✓" : "Отметить пройденным";
    }

    // галочки в оглавлении уроков
    var links = doc.querySelectorAll(".toc-lessons a");
    for (var j = 0; j < links.length; j++) {
      var a = links[j];
      var href = a.getAttribute("href") || "";
      if (href.charAt(0) !== "#") continue;
      var id = href.slice(1);
      var tick = a.querySelector(".np-tick");
      if (isDone(id)) {
        if (!tick) {
          tick = doc.createElement("span");
          tick.className = "np-tick";
          tick.textContent = "✓";
          a.appendChild(tick);
        }
      } else if (tick) tick.remove();
    }

    // карточка прогресса в toc
    var tocCard = doc.querySelector(".toc .np-progress");
    if (tocCard) {
      var ring = tocCard.querySelector(".np-ring");
      var fg = ring.querySelector(".fg");
      var circ = parseFloat(ring.dataset.circ);
      fg.setAttribute("stroke-dashoffset", String(circ * (1 - pct / 100)));
      ring.querySelector("b").textContent = pct + "%";
      var infoB = tocCard.querySelector(".np-progress-info b");
      var infoS = tocCard.querySelector(".np-progress-info span");
      infoB.textContent = total + " из " + COURSE_TOTAL;
      infoS.textContent = "элементов пройдено — " + pct + "%";
      var lis = tocCard.querySelectorAll(".np-progress-mods li");
      for (var m = 0; m < lis.length; m++) {
        var mod = m + 1;
        var n = doneInModule(mod);
        var count = lis[m].querySelector(".np-count");
        count.textContent = n + " / " + MODULE_TOTALS[mod];
        lis[m].classList.toggle("full", n === MODULE_TOTALS[mod]);
      }
    }

    // обзор на странице программы
    var overview = doc.querySelector(".np-course-progress");
    if (overview) {
      overview.querySelector(".np-bar i").style.width = pct + "%";
      overview.querySelector(".np-text span").textContent = total + " из " + COURSE_TOTAL + " · " + pct + "%";
      var cont = overview.querySelector(".np-continue");
      if (total === COURSE_TOTAL) {
        cont.textContent = "Курс пройден 🎉";
        cont.href = "modul-1.html";
      } else {
        var mod = 0;
        var best = lastDoneTs();
        if (best > 0) {
          Object.keys(progress.items).forEach(function (id) {
            var rec = progress.items[id];
            if (rec.t === best) mod = moduleOf(id) || mod;
          });
        }
        if (!mod) mod = 1;
        if (total === 0) {
          cont.textContent = "Начать курс";
          cont.href = "modul-" + mod + ".html";
        } else if (doneInModule(mod) === MODULE_TOTALS[mod] && mod < 5) {
          var next = mod + 1;
          while (next <= 5 && doneInModule(next) === MODULE_TOTALS[next]) next++;
          mod = next;
          cont.textContent = "Продолжить: модуль " + mod;
          cont.href = "modul-" + mod + ".html";
        } else {
          cont.textContent = "Продолжить: модуль " + mod;
          cont.href = "modul-" + mod + ".html";
        }
      }
    }

    renderModuleBadges();
  }

  /* =========================================================
     7. Тёмная тема
     ========================================================= */

  function initTheme() {
    var htmlEl = doc.documentElement;
    if (!htmlEl.getAttribute("data-theme")) {
      var saved = null;
      try { saved = localStorage.getItem(THEME_KEY); } catch (e) {}
      if (!saved) saved = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      htmlEl.setAttribute("data-theme", saved);
    }
    var inner = doc.querySelector(".nav .nav-inner");
    if (!inner || doc.querySelector(".np-theme")) return;
    var btn = doc.createElement("button");
    btn.type = "button";
    btn.className = "np-theme";
    btn.setAttribute("aria-label", "Переключить тему");
    btn.title = "Переключить тему";
    btn.innerHTML = '<span class="i-moon">🌙</span><span class="i-sun">☀️</span>';
    btn.addEventListener("click", function () {
      var next = htmlEl.getAttribute("data-theme") === "dark" ? "light" : "dark";
      htmlEl.setAttribute("data-theme", next);
      try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    });
    var burger = inner.querySelector(".burger");
    if (burger) inner.insertBefore(btn, burger);
    else inner.appendChild(btn);
  }

  /* =========================================================
     8. Кнопка «наверх» и счётчики
     ========================================================= */

  function initBackTop() {
    var btn = doc.createElement("button");
    btn.className = "np-top";
    btn.type = "button";
    btn.setAttribute("aria-label", "Наверх");
    btn.title = "Наверх";
    btn.innerHTML = "↑";
    btn.addEventListener("click", function () {
      var behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
      window.scrollTo({ top: 0, behavior: behavior });
    });
    doc.body.appendChild(btn);
    var ticking = false;
    window.addEventListener("scroll", function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(function () {
        btn.classList.toggle("show", window.scrollY > 560);
        ticking = false;
      });
    }, { passive: true });
  }

  function initCounters() {
    var stats = doc.querySelectorAll(".stats .stat b");
    if (!stats.length) return;
    var targets = [];
    for (var i = 0; i < stats.length; i++) {
      var raw = parseInt(stats[i].textContent.replace(/\D/g, ""), 10);
      if (isNaN(raw)) continue;
      targets.push({ el: stats[i], value: raw });
    }
    if (!targets.length) return;
    function animate() {
      var duration = 900;
      var start = null;
      var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      function frame(ts) {
        if (reduced) {
          for (var i = 0; i < targets.length; i++) targets[i].el.textContent = String(targets[i].value);
          return;
        }
        if (start === null) start = ts;
        var k = Math.min(1, (ts - start) / duration);
        k = 1 - Math.pow(1 - k, 3); // easeOutCubic
        for (var j = 0; j < targets.length; j++) {
          targets[j].el.textContent = String(Math.round(targets[j].value * k));
        }
        if (k < 1) window.requestAnimationFrame(frame);
      }
      window.requestAnimationFrame(frame);
    }
    if (!("IntersectionObserver" in window)) { animate(); return; }
    var first = doc.querySelector(".stats");
    var io = new IntersectionObserver(function (entries) {
      for (var i = 0; i < entries.length; i++) {
        if (entries[i].isIntersecting) {
          animate();
          io.disconnect();
          break;
        }
      }
    }, { threshold: 0.2 });
    io.observe(first);
  }

  /* =========================================================
     Инициализация
     ========================================================= */

  function init() {
    initTheme();
    renderProgressCard();
    renderProgramOverview();
    injectChips();

    var tests = doc.querySelectorAll(".test[id^='test-']");
    for (var i = 0; i < tests.length; i++) buildQuiz(tests[i]);

    bindCopy();
    initBackTop();
    initCounters();
    refresh();
  }

  if (doc.readyState === "loading") {
    doc.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
