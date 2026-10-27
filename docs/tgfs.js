/* Telegram tam ekran: başlık çubuğu (büyük çarpı / ⋯ düğmeleri) kalkar, yerine Telegram'ın küçük kontrolü gelir.
   Yalnız telefonda (iOS/Android) ve Bot API 8.0+ destekleyen sürümde açılır. İçerik, saat/pil alanı ve
   Telegram kontrolünün altından başlasın diye üst boşluk Telegram'ın verdiği güvenli alan değerlerinden alınır.
   Kapatmak için: bu dosyanın sayfalara eklendiği <script> satırını silmek yeterli. */
(function () {
  var tg = window.Telegram && window.Telegram.WebApp;
  if (!tg) return;
  var css = document.createElement("style");
  css.textContent = "html.tgfs body{padding-top:calc(var(--tg-safe-area-inset-top,0px) + var(--tg-content-safe-area-inset-top,0px))!important}";
  document.head.appendChild(css);
  function mark() { document.documentElement.classList.toggle("tgfs", !!tg.isFullscreen) }
  try {
    tg.onEvent("fullscreenChanged", mark);
    mark();
    var mobile = /^(ios|android)/.test(tg.platform || "");
    if (mobile && !tg.isFullscreen && tg.requestFullscreen && tg.isVersionAtLeast && tg.isVersionAtLeast("8.0")) tg.requestFullscreen();
  } catch (e) {}
})();
