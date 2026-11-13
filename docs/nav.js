/* Üst gezinme şeridi: Bugün · ABD · BIST · Defter. Her sayfada <body>'nin ilk satırına tek <script src="nav.js"> ile eklenir.
   Şerit akışın içindedir (fixed değil): Telegram tam ekran güvenli alanı (tgfs.js body üst boşluğu) ve alttaki sekme çubuğu etkilenmez.
   Tek satır, 36 px; dar ekranda yatay kayar. ES5; DOM textContent ile kurulur. */
(function () {
  var p = location.pathname, sub = /\/(bist|defter)\/[^\/]*$/.test(p), up = sub ? "../" : "";
  var cur = /\/bist\/tg\.html$/.test(p) ? "bist" : /\/defter\//.test(p) ? "defter" : /\/tg\.html$/.test(p) ? "us" : /bugun\.html$/.test(p) ? "bugun" : "";
  var L = [["bugun", "Bugün", up + "bugun.html"], ["us", "ABD", up + "tg.html"], ["bist", "BIST", up + "bist/tg.html"], ["defter", "Defter", up + "defter/index.html"]];
  var s = document.createElement("style");
  s.textContent =
    ".gnav{position:relative;z-index:5;display:flex;align-items:center;gap:4px;height:36px;overflow-x:auto;white-space:nowrap;scrollbar-width:none;" +
    "border-bottom:1px solid var(--line,#1d2330);font:600 13px/1 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}" +
    ".gnav::-webkit-scrollbar{display:none}" +
    ".gnav a{flex:0 0 auto;padding:7px 12px;border-radius:999px;color:var(--mut,var(--mute,#7d8798));text-decoration:none}" +
    ".gnav a[aria-current]{background:var(--on,rgba(255,255,255,.08));color:var(--txt,var(--ink,#e8ecf4))}";
  document.head.appendChild(s);
  var nav = document.createElement("nav"); nav.className = "gnav"; nav.setAttribute("aria-label", "Sayfalar");
  L.forEach(function (x) {
    var a = document.createElement("a"); a.href = x[2]; a.textContent = x[1];
    if (x[0] === cur) a.setAttribute("aria-current", "page");
    nav.appendChild(a);
  });
  document.body.insertBefore(nav, document.body.firstChild);
})();
