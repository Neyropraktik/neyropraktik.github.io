// НейроПрактик 2026 — доступ к закрытым модулям курса: хэш ключа.
// Единая точка изменения при ротации ключа:
//   config/.env → COURSE_ACCESS_KEY (сам ключ, секрет)
//   здесь      → SHA-256 от нормализованного ключа (публично)
// Нормализация: нижний регистр, только a-z0-9 (дефисы и пробелы отбрасываются).
// Подключается в <head> синхронно, до первой отрисовки: не мигает «замок».
window.NP_ACCESS_HASH = "c2502813cb2dfdb37c2d9c90d43f3d437fd9e6d50e849a5910b4791f5ebd091f";
(function () {
  try {
    var H = window.NP_ACCESS_HASH;
    var el = document.documentElement;
    if (localStorage.getItem("np-access-ok") === H) el.classList.add("np-unlocked");
    else if (/[?&]k=/.test(location.search)) el.classList.add("np-checking");
  } catch (e) { /* приватный режим — просто покажем «замок» */ }
})();
