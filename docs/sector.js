/* Sektör & Rejim görünümü (mini uygulama). Veri: market.json (market-data dalı) + data/sector_notes.json (yorum).
   Tüm metinler textContent ile yazılır. Tutarlar portföyden (şifre çözülmüş P) hesaplanır, hiçbir yere gönderilmez. */
(function () {
  "use strict";
  var VCLS = { "Ol": "up", "Erken giriş adayı": "up", "Tut, yeni alım yok": "warn", "İzle": "warn",
    "İzle (trend zayıfladı)": "warn", "Azalt / kâr al": "dn", "Uzak dur": "dn", "Veri yetersiz": "" };
  var QCLS = { "Lider": "up", "Toparlanan": "acc", "Zayıflayan": "warn", "Geride": "dn" };
  var RISK_PCT_KEY = "pm_risk_pct";

  function el(tag, c, t) { var e = document.createElement(tag); if (c) e.className = c; if (t !== undefined && t !== null) e.textContent = t; return e }
  function n(x, d) { return (x === null || x === undefined || isNaN(+x)) ? "–" : (+x).toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }) }
  function sp(x, d) { if (x === null || x === undefined) return "–"; return (x > 0 ? "+" : x < 0 ? "−" : "") + n(Math.abs(x), d === undefined ? 1 : d) }
  function cls(x) { return x > 0 ? "up" : x < 0 ? "dn" : "" }
  function vcls(v) {
    v = (v || "").split(" · ")[0]; if (VCLS[v] !== undefined) return VCLS[v];
    for (var k in VCLS) if (k && v.indexOf(k.split(" ")[0]) === 0) return VCLS[k];
    return "";
  }
  function dots(p) { var s = ""; for (var i = 0; i < 7; i++) s += i < p ? "●" : "○"; return s }

  function css() {
    if (document.getElementById("sector-css")) return;
    var s = document.createElement("style"); s.id = "sector-css";
    s.textContent =
      ".sx-card{background:rgba(17,21,31,.82);border:1px solid var(--line);border-radius:16px;padding:14px;margin-bottom:10px}" +
      ".sx-h{display:flex;justify-content:space-between;align-items:baseline;gap:10px}" +
      ".sx-t{font-size:18px;font-weight:700}.sx-s{color:var(--mut);font-size:12.5px}" +
      ".sx-bar{position:relative;height:10px;border-radius:6px;background:#1a2030;margin:12px 0 6px;overflow:hidden}" +
      ".sx-bar i{position:absolute;top:0;bottom:0;background:rgba(90,169,255,.28);border-left:1px solid #5aa9ff;border-right:1px solid #5aa9ff}" +
      ".sx-bar b{position:absolute;top:-3px;width:3px;height:16px;border-radius:2px;background:#fff}" +
      ".sx-ck{display:flex;gap:8px;font-size:13px;padding:3px 0}.sx-ck span:first-child{width:16px;text-align:center}" +
      ".sx-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}" +
      ".sx-chip{border:1px solid var(--line);border-radius:999px;padding:5px 10px;font-size:12.5px;font-weight:600;background:#151b28}" +
      ".sx-chip.up{border-color:rgba(61,220,132,.35);color:var(--up)}.sx-chip.dn{border-color:rgba(255,92,108,.35);color:var(--dn)}" +
      ".sx-row{padding:11px 2px;border-bottom:1px solid var(--line);cursor:pointer}.sx-row:last-child{border-bottom:0}" +
      ".sx-r1{display:flex;justify-content:space-between;gap:8px;align-items:center}" +
      ".sx-nm{font-weight:700}.sx-nm small{color:var(--mut);font-weight:500;margin-left:6px}" +
      ".sx-v{font-size:12px;font-weight:700;padding:3px 8px;border-radius:8px;background:#1a2030;white-space:nowrap}" +
      ".sx-v.up{color:var(--up);background:rgba(61,220,132,.1)}.sx-v.dn{color:var(--dn);background:rgba(255,92,108,.1)}.sx-v.warn{color:var(--warn);background:rgba(245,185,66,.1)}" +
      ".sx-r2{display:flex;gap:12px;color:var(--mut);font-size:12.5px;margin-top:4px;font-variant-numeric:tabular-nums;flex-wrap:wrap}" +
      ".sx-dots{letter-spacing:1px;color:#5aa9ff}.sx-q.up{color:var(--up)}.sx-q.dn{color:var(--dn)}.sx-q.warn{color:var(--warn)}.sx-q.acc{color:#5aa9ff}" +
      ".sx-det{display:none;margin-top:8px;font-size:13px;color:#c9d1de}.sx-row.open .sx-det{display:block}" +
      ".sx-note{margin-top:6px;padding:8px 10px;border-left:2px solid #5aa9ff;background:rgba(90,169,255,.06);border-radius:6px;color:#dbe3ef;font-size:13px}" +
      ".sx-calc{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}" +
      ".sx-calc label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--mut)}" +
      ".sx-calc input,.sx-calc select{background:#0b0f17;border:1px solid #2c3850;border-radius:10px;color:#fff;padding:9px 10px;font:inherit;font-size:15px;width:100%}" +
      ".sx-out{margin-top:10px;font-size:14px;line-height:1.5}" +
      ".sx-seg{display:flex;gap:4px;background:var(--chip);border-radius:12px;padding:3px;margin:4px 0 10px;width:max-content;max-width:100%;overflow-x:auto}" +
      ".sx-seg button{border:0;background:transparent;color:var(--mut);font:inherit;font-weight:600;padding:7px 12px;border-radius:9px;cursor:pointer;white-space:nowrap}" +
      ".sx-seg button.on{background:var(--on);color:var(--txt)}";
    document.head.appendChild(s);
  }

  /* ---- portföy hesapları ---- */
  function book(P, Q, M) {
    var q = (Q && Q.quotes) || {}, st = (M && M.stocks) || {}, pos = (P && P.portfolio) || {}, lv = (P && P.position_levels) || {};
    var rows = [], val = 0;
    Object.keys(pos).forEach(function (t) {
      var p = pos[t], px = +((q[t] && q[t].c) || (st[t] && st[t].close) || p.cost_basis);
      var v = p.shares * px; val += v;
      var stop = (lv[t] && lv[t].stop_loss != null) ? +lv[t].stop_loss : null, src = "senin stopun";
      if (stop === null && st[t] && st[t].stop_atr) { stop = +st[t].stop_atr; src = "ATR önerisi" }
      var risk = stop !== null ? Math.max(0, (px - stop) * p.shares) : null;
      rows.push({ t: t, shares: p.shares, px: px, v: v, stop: stop, stopSrc: src, risk: risk, below: stop !== null && px <= stop });
    });
    var cash = +(P && P.cash) || 0, eq = val + cash;
    rows.forEach(function (r) { r.w = eq ? r.v / eq * 100 : 0 });
    var heat = rows.reduce(function (s, r) { return s + (r.risk || 0) }, 0);
    return { rows: rows, cash: cash, eq: eq, cashPct: eq ? cash / eq * 100 : 0, heat: heat, heatPct: eq ? heat / eq * 100 : 0 };
  }

  /* Portföy sekmesine kısa şerit: nakit hedefi + ısı + yoğunlaşma */
  function strip(box, P, Q, M, hide) {
    if (!box) return; box.textContent = "";
    if (!P || !M || !M.regime) return;
    css();
    var b = book(P, Q, M), r = M.regime, lo = r.cash_target[0], hi = r.cash_target[1];
    var c = el("div", "sx-card");
    var h = el("div", "sx-h"); h.appendChild(el("div", "sx-t", "Nakit %" + n(b.cashPct, 1)));
    h.appendChild(el("div", "sx-s", "Rejim: " + r.label + " → hedef %" + lo + "–" + hi)); c.appendChild(h);
    var bar = el("div", "sx-bar"), band = el("i"), mk = el("b");
    band.style.left = Math.min(lo, 60) / 60 * 100 + "%"; band.style.width = (Math.min(hi, 60) - Math.min(lo, 60)) / 60 * 100 + "%";
    mk.style.left = "calc(" + Math.min(b.cashPct, 60) / 60 * 100 + "% - 1px)";
    bar.appendChild(band); bar.appendChild(mk); c.appendChild(bar);
    var gap = (lo - b.cashPct) / 100 * b.eq, msg;
    if (b.cashPct < lo) msg = "Nakit hedefin altında: hedefe ulaşmak için " + (hide ? "*****" : "$" + n(gap, 0)) + " nakde geçmek gerekir (en zayıf pozisyondan başlanır).";
    else if (b.cashPct > hi) msg = "Nakit hedefin üstünde: " + (hide ? "*****" : "$" + n((b.cashPct - hi) / 100 * b.eq, 0)) + " güçlü sektörlerde kademeli kullanılabilir.";
    else msg = "Nakit hedef aralığında.";
    c.appendChild(el("div", "sx-s", msg));
    var heat = el("div", "sx-s", "Portföy ısısı (tüm stoplar tetiklenirse kayıp): %" + n(b.heatPct, 1) + (hide ? "" : " · $" + n(b.heat, 0)) +
      (b.heatPct > 8 ? " — yüksek (öneri ≤ %6)" : ""));
    heat.style.marginTop = "6px"; c.appendChild(heat);
    var big = b.rows.filter(function (x) { return x.w > 25 }).map(function (x) { return x.t + " %" + n(x.w, 0) });
    if (big.length) { var w = el("div", "sx-s warn", "Yoğunlaşma: " + big.join(", ") + " (tek hisse için öneri ≤ %25)"); w.style.marginTop = "4px"; c.appendChild(w) }
    box.appendChild(c);
  }

  /* ---- ana görünüm ---- */
  var view = "sektor";
  function render(box, ctx) {
    css(); box.textContent = "";
    var M = ctx.M, N = ctx.N || {}, P = ctx.P, Q = ctx.Q, hide = ctx.hide;
    if (!M) { box.appendChild(el("div", "empty", "Sektör verisi henüz yok (Piyasa & Sektör Rotasyonu iş akışı ilk kez çalışınca gelir).")); return }
    var r = M.regime || {};
    // rejim kartı
    var c = el("div", "sx-card");
    var h = el("div", "sx-h"); h.appendChild(el("div", "sx-t " + (r.score / r.max >= .8 ? "up" : r.score / r.max >= .45 ? "warn" : "dn"), r.label || "–"));
    h.appendChild(el("div", "sx-s", "puan " + r.score + "/" + r.max)); c.appendChild(h);
    c.appendChild(el("div", "sx-s", "Önerilen nakit: %" + (r.cash_target || []).join("–") + " · Genişlik (SMA50 üstü): %" + (r.breadth50 == null ? "–" : r.breadth50)));
    (r.checks || []).forEach(function (k) { var row = el("div", "sx-ck"); row.appendChild(el("span", k[1] ? "up" : "dn", k[1] ? "✓" : "✗")); row.appendChild(el("span", "", k[0])); c.appendChild(row) });
    if (N.summary) c.appendChild(el("div", "sx-note", N.summary));
    box.appendChild(c);
    strip(box.appendChild(el("div")), P, Q, M, hide);

    // olunacak / uzak durulacak
    var G = M.groups || [], gn = N.groups || {};
    function view_of(g) { return (gn[g.sym] && gn[g.sym].view) || g.verdict }
    var go = G.filter(function (g) { return /^(Ol|Erken)/.test(view_of(g)) && !g.bank });
    var avoid = G.filter(function (g) { return /^(Uzak|Azalt)/.test(view_of(g)) }).slice(-8).reverse();
    var c2 = el("div", "sx-card");
    c2.appendChild(el("div", "sx-t", "Nerede olmalı?"));
    var ch = el("div", "sx-chips"); go.forEach(function (g) { ch.appendChild(el("span", "sx-chip up", g.name + " · " + g.sym)) });
    if (!go.length) ch.appendChild(el("span", "sx-s", "Şu an net lider yok"));
    c2.appendChild(ch);
    var t2 = el("div", "sx-t", "Uzak durulacak"); t2.style.marginTop = "12px"; c2.appendChild(t2);
    var ch2 = el("div", "sx-chips"); avoid.forEach(function (g) { ch2.appendChild(el("span", "sx-chip dn", g.name + " · " + g.sym)) });
    c2.appendChild(ch2);
    box.appendChild(c2);

    // alt görünüm seçimi
    var seg = el("div", "sx-seg");
    [["sektor", "Sektörler"], ["hisse", "Hisseler"], ["risk", "Risk & Boyut"]].forEach(function (x) {
      var b = el("button", view === x[0] ? "on" : "", x[1]); b.onclick = function () { view = x[0]; render(box, ctx) }; seg.appendChild(b);
    });
    box.appendChild(seg);
    if (view === "sektor") sectors(box, G, gn);
    else if (view === "hisse") stocks(box, M, N, P);
    else risk(box, P, Q, M, hide);
    var ft = el("div", "note", "Veri: " + new Date(M.updated).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) +
      " (İstanbul) · kaynak " + Object.keys(M.sources || {}).map(function (k) { return k + " " + M.sources[k] }).join(", ") +
      (N.updated ? " · yorum " + N.updated : "") + ". " + (M.method || "") + " Yatırım tavsiyesi değildir.");
    box.appendChild(ft);
  }

  function sectors(box, G, gn) {
    var c = el("div", "sx-card");
    G.forEach(function (g) {
      var row = el("div", "sx-row"), r1 = el("div", "sx-r1"), nm = el("div", "sx-nm", (g.rank ? g.rank + ". " : "") + g.name);
      nm.appendChild(el("small", "", g.sym)); r1.appendChild(nm);
      var v = (gn[g.sym] && gn[g.sym].view) || g.verdict; r1.appendChild(el("span", "sx-v " + vcls(v), v)); row.appendChild(r1);
      var r2 = el("div", "sx-r2"), rs = g.rs || {}, tr = g.trend || {};
      r2.appendChild(el("span", cls(rs.m1), "1A " + sp(rs.m1)));
      r2.appendChild(el("span", cls(rs.m3), "3A " + sp(rs.m3)));
      r2.appendChild(el("span", "sx-dots", dots(tr.points || 0)));
      r2.appendChild(el("span", "sx-q " + (QCLS[g.quadrant] || ""), g.quadrant || "–"));
      if (g.stale) r2.appendChild(el("span", "warn", "eski"));
      row.appendChild(r2);
      var d = el("div", "sx-det");
      d.appendChild(el("div", "", "Göreli güç (SPY'ye göre puan): 1H " + sp(rs.w) + " · 1A " + sp(rs.m1) + " · 3A " + sp(rs.m3) + " · 6A " + sp(rs.m6) + " · bileşik " + sp(rs.score)));
      d.appendChild(el("div", "", "Fiyat " + n(g.close, 2) + " (" + sp(g.chg, 2) + "%) · RSI " + n(g.rsi, 0) + " · haftalık RSI " + n(g.rsi_w, 0) + " · ATR %" + n(g.atr_pct, 1)));
      (tr.checks || []).forEach(function (k) { d.appendChild(el("div", k[1] ? "up" : "dn", (k[1] ? "✓ " : "✗ ") + k[0])) });
      if (gn[g.sym] && gn[g.sym].note) d.appendChild(el("div", "sx-note", gn[g.sym].note));
      if (g.bank) d.appendChild(el("div", "warn", "Banka kuralı: bu gruptan hisse önerilmez, yalnız piyasa okuması için."));
      row.appendChild(d);
      row.onclick = function () { row.classList.toggle("open") };
      c.appendChild(row);
    });
    box.appendChild(c);
    box.appendChild(el("div", "note", "Çeyrek: Lider = 3A ve 1A'da SPY'den güçlü · Toparlanan = 3A zayıf ama 1A güçlü (erken dönüş) · Zayıflayan = 3A güçlü ama 1A zayıf (kâr al) · Geride = ikisi de zayıf. Noktalar: 7 trend koşulundan (5 günlük + 2 haftalık) kaçı sağlanıyor."));
  }

  function stocks(box, M, N, P) {
    var S = M.stocks || {}, held = (P && P.portfolio) || {}, sn = N.stocks || {};
    var list = Object.keys(S).sort(function (a, b) {
      var ha = held[a] ? 1 : 0, hb = held[b] ? 1 : 0; if (ha !== hb) return hb - ha;
      return ((S[b].rs || {}).score || -999) - ((S[a].rs || {}).score || -999);
    });
    var c = el("div", "sx-card");
    list.forEach(function (t) {
      var s = S[t], row = el("div", "sx-row"), r1 = el("div", "sx-r1"), nm = el("div", "sx-nm", t);
      nm.appendChild(el("small", "", (held[t] ? "elimde · " : "") + (s.group_name || s.group || "")));
      r1.appendChild(nm);
      var v = (sn[t] && sn[t].view) || s.verdict; r1.appendChild(el("span", "sx-v " + vcls(v), v)); row.appendChild(r1);
      var r2 = el("div", "sx-r2"), rs = s.rs || {}, tr = s.trend || {};
      r2.appendChild(el("span", "", n(s.close, 2) + " (" + sp(s.chg, 2) + "%)"));
      r2.appendChild(el("span", cls(rs.score), "RS " + sp(rs.score)));
      r2.appendChild(el("span", "sx-dots", dots(tr.points || 0)));
      r2.appendChild(el("span", "", tr.label || "–"));
      row.appendChild(r2);
      var d = el("div", "sx-det");
      d.appendChild(el("div", "", "SPY'ye göre: 1A " + sp(rs.m1) + " · 3A " + sp(rs.m3) + " · bileşik " + sp(rs.score) +
        (s.rs_group ? " · kendi grubuna (" + s.group + ") göre " + sp(s.rs_group.score) : "")));
      d.appendChild(el("div", "", "RSI " + n(s.rsi, 0) + " (haftalık " + n(s.rsi_w, 0) + ") · ADX " + n(s.adx, 0) + " · ATR " + n(s.atr, 2) + " (%" + n(s.atr_pct, 1) + ")"));
      d.appendChild(el("div", "", "ATR tabanlı stop önerisi: " + n(s.stop_atr, 2) + " (fiyattan 2×ATR ya da 3A tepeden 3×ATR, yüksek olan)"));
      (tr.checks || []).forEach(function (k) { d.appendChild(el("div", k[1] ? "up" : "dn", (k[1] ? "✓ " : "✗ ") + k[0])) });
      if (sn[t] && sn[t].note) d.appendChild(el("div", "sx-note", sn[t].note));
      row.appendChild(d); row.onclick = function () { row.classList.toggle("open") };
      c.appendChild(row);
    });
    box.appendChild(c);
  }

  function risk(box, P, Q, M, hide) {
    if (!P) { box.appendChild(el("div", "empty", "Portföy kilitli; risk hesabı için parolayla aç.")); return }
    var b = book(P, Q, M), c = el("div", "sx-card");
    c.appendChild(el("div", "sx-t", "Pozisyon riski"));
    b.rows.sort(function (x, y) { return (y.risk || 0) - (x.risk || 0) }).forEach(function (r) {
      var row = el("div", "sx-row"); row.style.cursor = "default";
      var r1 = el("div", "sx-r1"); r1.appendChild(el("div", "sx-nm", r.t + " · %" + n(r.w, 1)));
      r1.appendChild(el("span", "sx-v " + (r.below ? "dn" : ""), r.below ? "stop altında" : "stopa %" + n(r.stop ? (r.px - r.stop) / r.px * 100 : null, 1)));
      row.appendChild(r1);
      row.appendChild(el("div", "sx-r2", "Stop " + n(r.stop, 2) + " (" + r.stopSrc + ") · stopta kayıp " + (hide ? "*****" : "$" + n(r.risk, 0)) + " = portföyün %" + n(b.eq ? (r.risk || 0) / b.eq * 100 : 0, 1)));
      c.appendChild(row);
    });
    c.appendChild(el("div", "sx-s", "Toplam ısı %" + n(b.heatPct, 1) + " · öneri: işlem başına %1–1,5, toplam ≤ %6"));
    box.appendChild(c);

    // pozisyon büyüklüğü hesaplayıcı
    var S = (M && M.stocks) || {}, c2 = el("div", "sx-card");
    c2.appendChild(el("div", "sx-t", "Pozisyon büyüklüğü"));
    c2.appendChild(el("div", "sx-s", "Stopa kadar kayıp portföyün seçtiğin yüzdesini geçmesin; tek hisse en çok %20, nakitten fazla değil."));
    var g = el("div", "sx-calc");
    function field(lbl, input) { var l = el("label", "", lbl); l.appendChild(input); g.appendChild(l); return input }
    var sel = field("Hisse", el("select")); Object.keys(S).sort().forEach(function (t) { var o = el("option", "", t); o.value = t; sel.appendChild(o) });
    var rp = field("Risk % (işlem başına)", el("input")); rp.type = "number"; rp.step = "0.25"; rp.min = "0.25";
    try { rp.value = localStorage.getItem(RISK_PCT_KEY) || "1" } catch (e) { rp.value = "1" }
    var en = field("Giriş fiyatı", el("input")); en.type = "number"; en.step = "0.01";
    var stp = field("Stop", el("input")); stp.type = "number"; stp.step = "0.01";
    c2.appendChild(g);
    var out = el("div", "sx-out"); c2.appendChild(out);
    function fill() { var s = S[sel.value] || {}; en.value = s.close || ""; stp.value = s.stop_atr || ""; calc() }
    function calc() {
      try { localStorage.setItem(RISK_PCT_KEY, rp.value) } catch (e) {}
      var e = +en.value, s = +stp.value, pr = +rp.value / 100;
      out.textContent = "";
      if (!(e > 0) || !(s > 0) || s >= e) { out.appendChild(el("div", "warn", "Stop giriş fiyatının altında olmalı.")); return }
      var riskUsd = b.eq * pr, perShare = e - s, sh = Math.floor(riskUsd / perShare);
      var capW = Math.floor(b.eq * 0.20 / e), capC = Math.floor(b.cash / e), fin = Math.max(0, Math.min(sh, capW, capC));
      var why = fin === sh ? "risk sınırı" : fin === capW ? "%20 tek hisse sınırı" : "eldeki nakit";
      out.appendChild(el("div", "", "Önerilen: " + fin + " adet ≈ " + (hide ? "*****" : "$" + n(fin * e, 0)) + " (belirleyen: " + why + ")"));
      out.appendChild(el("div", "sx-s", "Stopa mesafe %" + n(perShare / e * 100, 1) + " · stopta kayıp " + (hide ? "*****" : "$" + n(fin * perShare, 0)) +
        " = portföyün %" + n(b.eq ? fin * perShare / b.eq * 100 : 0, 2) + " · hedef için en az 2R: " + n(e + 2 * perShare, 2)));
      var s0 = S[sel.value];
      if (s0 && /^(Uzak|Azalt)/.test(s0.verdict)) out.appendChild(el("div", "dn", "Dikkat: " + sel.value + " şu an '" + s0.verdict + "' (momentum zayıf)."));
    }
    sel.onchange = fill; [rp, en, stp].forEach(function (x) { x.oninput = calc });
    fill();
    box.appendChild(c2);
  }

  window.SectorView = { render: render, strip: strip, book: book };
})();
