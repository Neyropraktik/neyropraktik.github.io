// НейроПрактик 2026 — доступ к закрытым модулям курса.
// Программа и модуль 1 открыты всем; модули 2–5 открываются кодом,
// который бот присылает после покупки: ссылкой ?k=… или вводом вручную.
// Проверка идёт по SHA-256-хэшу (window.NP_ACCESS_HASH из <head>) —
// сам код доступа в исходниках сайта не хранится.
// Подключается ПОСЛЕ app.js и course.js.
(function () {
  "use strict";

  var doc = document;
  var HASH = window.NP_ACCESS_HASH || ""; // задаётся inline-скриптом в <head> каждой страницы
  var STORE = "np-access-ok";             // localStorage: подтверждённый хэш

  /* ---------- нормализация и хэш ---------- */

  function norm(s) {
    return String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  function sha256hex(s) {
    if (window.crypto && crypto.subtle && crypto.subtle.digest && window.TextEncoder) {
      var data = new TextEncoder().encode(s);
      return crypto.subtle.digest("SHA-256", data).then(function (buf) {
        var b = new Uint8Array(buf), out = "";
        for (var i = 0; i < b.length; i++) out += (b[i] < 16 ? "0" : "") + b[i].toString(16);
        return out;
      });
    }
    return Promise.reject(new Error("no-crypto"));
  }

  function validate(raw) {
    var k = norm(raw);
    if (k.length < 8 || k.length > 64) return Promise.resolve(false);
    return sha256hex(k).then(function (h) { return h === HASH; });
  }

  function isUnlocked() {
    return doc.documentElement.classList.contains("np-unlocked");
  }

  /* ---------- открытие доступа ---------- */

  function unlock(save) {
    doc.documentElement.classList.remove("np-checking");
    doc.documentElement.classList.add("np-unlocked");
    if (save) { try { localStorage.setItem(STORE, HASH); } catch (e) { /* private mode */ } }
    decorate();
  }

  function stopChecking() {
    doc.documentElement.classList.remove("np-checking");
  }

  function setMsg(text, cls) {
    var el = doc.getElementById("unlockMsg");
    if (!el) return;
    el.textContent = text || "";
    el.className = "unlock-msg" + (cls ? " " + cls : "");
  }

  /* ---------- значки «закрыто/открыто» в оглавлениях ---------- */

  function decorate() {
    var links = doc.querySelectorAll('a[href^="modul-"]');
    for (var i = 0; i < links.length; i++) {
      var a = links[i];
      var m = (a.getAttribute("href") || "").match(/modul-([1-5])\.html/);
      if (!m || m[1] === "1") continue; // модуль 1 бесплатный — значок не нужен
      var lock = a.querySelector(".np-lock-mark");
      var open = a.querySelector(".np-unlock-mark");
      if (isUnlocked()) {
        if (lock) lock.remove();
        if (!open) {
          open = doc.createElement("span");
          open.className = "np-unlock-mark";
          open.textContent = " 🔓";
          a.appendChild(open);
        }
      } else if (!lock) {
        lock = doc.createElement("span");
        lock.className = "np-lock-mark";
        lock.textContent = " 🔒";
        a.appendChild(lock);
      }
    }
    // подписи у ссылок на странице программы
    var hints = doc.querySelectorAll(".lock-hint.locked");
    for (var j = 0; j < hints.length; j++) {
      if (isUnlocked()) {
        hints[j].classList.remove("locked");
        hints[j].classList.add("open");
        hints[j].textContent = "✓ Открыт";
      }
    }
  }

  /* ---------- форма «Уже купили?» ---------- */

  function bindForm() {
    var form = doc.getElementById("unlockForm");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var input = doc.getElementById("unlockKey");
      var raw = input ? input.value : "";
      if (!norm(raw)) { setMsg("Введите код доступа из бота.", "bad"); return; }
      setMsg("Проверяю…");
      validate(raw).then(function (ok) {
        if (ok) {
          unlock(true);
          setMsg("Доступ открыт ✓", "ok");
          toast("Доступ открыт ✓ — приятной учёбы!");
        } else {
          setMsg("Код не подошёл. Проверьте дефисы и раскладку — или напишите в бот.", "bad");
        }
      }, function () {
        setMsg("Проверка работает только на сайте, открытом с телефона или компьютера.", "bad");
      });
    });
  }

  /* ---------- уведомление ---------- */

  var toastEl = null, toastTimer = null;

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
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 2600);
  }

  /* ---------- запуск ---------- */

  function init() {
    decorate();
    bindForm();

    var k = "";
    try { k = new URLSearchParams(location.search).get("k") || ""; } catch (e) {}

    // ссылка из бота: ?k=… — уже разблокировано или параметра нет
    if (!k || isUnlocked()) { stopChecking(); return; }

    validate(k).then(function (ok) {
      if (ok) {
        unlock(true);
        try {
          if (window.history && history.replaceState) {
            history.replaceState(null, "", location.pathname + location.hash);
          }
        } catch (e) { /* ignore */ }
        setMsg("Доступ открыт ✓", "ok");
        toast("Доступ открыт ✓ — приятной учёбы!");
      } else {
        stopChecking();
        setMsg("Ссылка-доступ не сработала. Введите код вручную — или напишите в бот.", "bad");
      }
    }, function () {
      stopChecking();
      setMsg("Не удалось проверить доступ. Откройте ссылку из бота ещё раз.", "bad");
    });
  }

  if (doc.readyState === "loading") {
    doc.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
