/* Teknik görünüm: zaman dilimi sinyal tablosu + günlük mum grafiği (bağımlılıksız SVG).
   Veri: market.json (günlük/haftalık), bars.json (günlük mumlar), intraday.json (4s/15dk), trend.json (Supertrend 15dk).
   Stop/hedef portföyden (şifre çözülmüşse) gelir. Tüm metin textContent ile yazılır. */
(function () {
  "use strict";
  var SVGNS = "http://www.w3.org/2000/svg";
  function el(tag, c, t) { var e = document.createElement(tag); if (c) e.className = c; if (t !== undefined && t !== null) e.textContent = t; return e }
  function sv(tag, a) { var e = document.createElementNS(SVGNS, tag); for (var k in a) e.setAttribute(k, a[k]); return e }
  function n(x, d) { return (x === null || x === undefined || isNaN(+x)) ? "–" : (+x).toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }) }
  function arrow(up) { return up === null || up === undefined ? ["■", "warn"] : up ? ["▲", "up"] : ["▼", "dn"] }

  function css() {
    if (document.getElementById("tv-css")) return;
    var s = document.createElement("style"); s.id = "tv-css";
    s.textContent =
      ".tx-mx{width:100%;border-collapse:collapse;margin:6px 0 4px;font-size:13.5px;font-variant-numeric:tabular-nums}" +
      ".tx-mx td{padding:8px 4px;border-bottom:1px solid var(--line);vertical-align:top}.tx-mx tr:last-child td{border-bottom:0}" +
      ".tx-mx td:first-child{color:var(--mut);white-space:nowrap;width:70px}.tx-mx td:nth-child(2){font-weight:700;white-space:nowrap;width:92px}" +
      ".tx-mx td:last-child{color:#c9d1de}" +
      ".tx-sum{font-weight:700;margin:4px 0 8px}.tx-chart{margin:10px -4px 4px}.tx-chart svg{width:100%;height:auto;display:block}" +
      ".tx-leg{display:flex;flex-wrap:wrap;gap:10px;font-size:11.5px;color:var(--mut);margin:2px 2px 8px}" +
      ".tx-leg i{display:inline-block;width:12px;height:2px;margin-right:4px;vertical-align:middle}" +
      ".tx-rg{display:flex;gap:4px;margin:6px 0}.tx-rg button{border:1px solid var(--line);background:#151b28;color:var(--mut);border-radius:8px;padding:4px 10px;font:inherit;font-size:12px;cursor:pointer}" +
      ".tx-rg button.on{color:var(--txt);background:var(--on)}" +
      "details.tx-d{margin-top:10px;border-top:1px solid var(--line);padding-top:8px}details.tx-d summary{cursor:pointer;color:var(--acc);font-weight:600;font-size:13.5px;padding:4px 0}";
    document.head.appendChild(s);
  }

  function ema(v, k) { var out = [], a = 2 / (k + 1), e = null; for (var i = 0; i < v.length; i++) { if (i < k - 1) { out.push(null); continue } if (e === null) { var s = 0; for (var j = i - k + 1; j <= i; j++)s += v[j]; e = s / k } else e = v[i] * a + e * (1 - a); out.push(e) } return out }
  function sma(v, k) { var out = [], s = 0; for (var i = 0; i < v.length; i++) { s += v[i]; if (i >= k) s -= v[i - k]; out.push(i >= k - 1 ? s / k : null) } return out }

  /* ---- sinyal tablosu ---- */
  function matrix(box, t, ctx) {
    var s = ctx.M && ctx.M.stocks && ctx.M.stocks[t], it = ctx.INTRA && ctx.INTRA.tickers && ctx.INTRA.tickers[t],
      tr = ctx.TREND && ctx.TREND.tickers && ctx.TREND.tickers[t];
    var rows = [], ups = 0, known = 0;
    function add(lbl, up, txt, det) { var a = arrow(up); rows.push([lbl, a, txt, det]); if (up !== null && up !== undefined) { known++; if (up) ups++ } }
    if (s && s.trend) {
      var ck = {}; (s.trend.checks || []).forEach(function (k) { ck[k[0]] = k[1] });
      var wUp = ck["Fiyat > EMA20 (haftalık)"], wCross = ck["EMA20 > SMA50 (haftalık)"];
      add("Haftalık", wUp === undefined ? null : wUp, wUp ? "yükseliş" : wUp === false ? "düşüş" : "–",
        "Fiyat haftalık EMA20 " + (wUp ? "üstünde" : "altında") + (wCross === undefined ? "" : ", EMA20 " + (wCross ? ">" : "<") + " SMA50") + " · haftalık RSI " + n(s.rsi_w, 0));
      var dUp = s.trend.points >= 4;
      add("Günlük", s.trend.points === 3 ? null : dUp, s.trend.points + "/7 " + (s.trend.label || ""),
        "EMA20 " + n(s.ema20, 2) + " · SMA50 " + n(s.sma50, 2) + " · SMA200 " + n(s.sma200, 2) + " · RSI " + n(s.rsi, 0) +
        " · MACD " + (s.macd !== null && s.macd_sig !== null ? (s.macd > s.macd_sig ? "sinyal üstünde (olumlu)" : "sinyal altında (olumsuz)") : "–") + " · ADX " + n(s.adx, 0));
    }
    if (it && it.h4) add("4 saat", it.h4.dir === "up", it.h4.dir === "up" ? "yükseliş" : "düşüş",
      "EMA8 " + n(it.h4.ema8, 2) + " / EMA20 " + n(it.h4.ema20, 2) + (it.h4.cross_bars_ago != null ? " · kesişim " + it.h4.cross_bars_ago + " mum önce" : "") +
      (it.elliott && it.elliott.label ? " · Elliott: " + it.elliott.label : ""));
    if (it && it.m15) {
      var st = tr && tr.st15;
      add("15 dk", it.m15.dir === "up", it.m15.dir === "up" ? "yükseliş" : "düşüş",
        "EMA34 " + n(it.m15.ema34, 2) + " / EMA89 " + n(it.m15.ema89, 2) +
        (st ? " · Supertrend " + (st.dir === "up" ? "▲" : "▼") + " " + n(st.line, 2) : ""));
    }
    if (!rows.length) { box.appendChild(el("div", "sub", "Sinyal verisi yok")); return }
    var verdict = known ? (ups === known ? "Tüm zaman dilimleri yükselişte" : ups === 0 ? "Tüm zaman dilimleri düşüşte" :
      ups + "/" + known + " zaman dilimi yükselişte (karışık)") : "";
    box.appendChild(el("div", "tx-sum " + (ups === known ? "up" : ups === 0 ? "dn" : "warn"), verdict));
    var tb = el("table", "tx-mx");
    rows.forEach(function (r) {
      var tr0 = el("tr"); tr0.appendChild(el("td", "", r[0]));
      var c = el("td", r[1][1], r[1][0] + " " + r[2]); tr0.appendChild(c); tr0.appendChild(el("td", "", r[3])); tb.appendChild(tr0);
    });
    box.appendChild(tb);
    if (s && s.verdict) box.appendChild(el("div", "sub", "Sektör/RS görünümü: " + s.verdict + (s.group_name ? " · grup " + s.group_name : "") +
      " · SPY'ye göre RS " + (s.rs && s.rs.score != null ? (s.rs.score > 0 ? "+" : "") + n(s.rs.score, 1) : "–")));
  }

  /* ---- grafik ---- */
  var range = 120;
  function chart(box, t, ctx) {
    var B = ctx.BARS && ctx.BARS.bars && ctx.BARS.bars[t];
    if (!B || B.length < 30) { box.appendChild(el("div", "sub", "Grafik verisi henüz yok (Piyasa & Sektör iş akışı günlük mumları yazınca gelir).")); return }
    var wrap = el("div", "tx-chart"); box.appendChild(wrap);
    var rg = el("div", "tx-rg");
    [[60, "3A"], [120, "6A"], [180, "9A"]].forEach(function (x) {
      var b = el("button", range === x[0] ? "on" : "", x[1]); b.onclick = function () { range = x[0]; wrap.textContent = ""; draw() }; rg.appendChild(b);
    });
    box.insertBefore(rg, wrap);
    var s = ctx.M && ctx.M.stocks && ctx.M.stocks[t], lv = (ctx.P && ctx.P.position_levels || {})[t] || {},
      held = ctx.P && ctx.P.portfolio && ctx.P.portfolio[t];
    function draw() {
      [].forEach.call(rg.children, function (b, i) { b.className = [60, 120, 180][i] === range ? "on" : "" });
      var all = B.map(function (r) { return r[4] }), e20 = ema(all, 20), s50 = sma(all, 50);
      var off = Math.max(0, B.length - range), bars = B.slice(off);
      var lines = [];
      if (lv.stop_loss != null && held) lines.push([+lv.stop_loss, "#ff5c6c", "Stop " + n(lv.stop_loss, 2)]);
      if (lv.target != null && held) lines.push([+lv.target, "#3ddc84", "Hedef " + n(lv.target, 2)]);
      if (s && s.stop_atr) lines.push([+s.stop_atr, "#f5b942", "ATR stop " + n(s.stop_atr, 2)]);
      if (held && held.cost_basis) lines.push([+held.cost_basis, "#9aa6ba", "Maliyet"]);
      var lo = Infinity, hi = -Infinity;
      bars.forEach(function (r) { lo = Math.min(lo, r[3]); hi = Math.max(hi, r[2]) });
      lines.forEach(function (l) { if (l[0] > lo * 0.85 && l[0] < hi * 1.15) { lo = Math.min(lo, l[0]); hi = Math.max(hi, l[0]) } });
      var pad = (hi - lo) * 0.06; lo -= pad; hi += pad;
      var W = Math.max(300, Math.round(wrap.clientWidth || 360)), H = W < 500 ? 270 : 330, L = 4, R = 54, T = 8, Bm = 20,
        cw = (W - L - R) / bars.length;
      function y(v) { return T + (hi - v) / (hi - lo) * (H - T - Bm) }
      function x(i) { return L + i * cw + cw / 2 }
      var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": t + " günlük mum grafiği" });
      for (var g = 0; g <= 4; g++) {
        var v = lo + (hi - lo) * g / 4;
        svg.appendChild(sv("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: "#1d2330", "stroke-width": 1 }));
        var tx = sv("text", { x: W - R + 4, y: y(v) + 4, fill: "#7d8798", "font-size": 11 }); tx.textContent = n(v, v < 20 ? 2 : 0); svg.appendChild(tx);
      }
      bars.forEach(function (r, i) {
        var up = r[4] >= r[1], c = up ? "#3ddc84" : "#ff5c6c";
        svg.appendChild(sv("line", { x1: x(i), x2: x(i), y1: y(r[2]), y2: y(r[3]), stroke: c, "stroke-width": 1 }));
        var top = y(Math.max(r[1], r[4])), h = Math.max(1, Math.abs(y(r[1]) - y(r[4])));
        svg.appendChild(sv("rect", { x: x(i) - Math.max(1, cw * 0.35), y: top, width: Math.max(1.5, cw * 0.7), height: h, fill: c, opacity: up ? 0.9 : 0.85 }));
      });
      function path(arr, col, dash) {
        var d = "", first = true;
        for (var i = 0; i < bars.length; i++) { var v = arr[off + i]; if (v === null || v === undefined) continue; d += (first ? "M" : "L") + x(i).toFixed(1) + " " + y(v).toFixed(1) + " "; first = false }
        if (d) svg.appendChild(sv("path", { d: d, fill: "none", stroke: col, "stroke-width": 1.6, "stroke-dasharray": dash || "" }));
      }
      path(e20, "#5aa9ff"); path(s50, "#b58cff");
      var vis = lines.filter(function (l) { return l[0] >= lo && l[0] <= hi }).sort(function (a, b) { return y(a[0]) - y(b[0]) }), lastY = -99;
      vis.forEach(function (l) {
        svg.appendChild(sv("line", { x1: L, x2: W - R, y1: y(l[0]), y2: y(l[0]), stroke: l[1], "stroke-width": 1.2, "stroke-dasharray": "5 4" }));
        var ty = Math.max(y(l[0]) - 4, lastY + 13); lastY = ty;  // etiketler üst üste binmesin
        var tx = sv("text", { x: L + 4, y: ty, fill: l[1], "font-size": 11, "font-weight": 600, "paint-order": "stroke", stroke: "#0a0d14", "stroke-width": 3 });
        tx.textContent = l[2]; svg.appendChild(tx);
      });
      var last = bars[bars.length - 1], ly = y(last[4]);
      svg.appendChild(sv("rect", { x: W - R + 1, y: ly - 9, width: R - 2, height: 18, rx: 4, fill: last[4] >= last[1] ? "#1f6f45" : "#7a2832" }));
      var lt = sv("text", { x: W - R + 5, y: ly + 4, fill: "#fff", "font-size": 11, "font-weight": 700 }); lt.textContent = n(last[4], last[4] < 20 ? 2 : 1); svg.appendChild(lt);
      [[0, "start"], [bars.length - 1, "end"]].forEach(function (p) {
        var tx = sv("text", { x: x(p[0]), y: H - 6, fill: "#7d8798", "font-size": 11, "text-anchor": p[1] }); tx.textContent = bars[p[0]][0].slice(5).split("-").reverse().join("."); svg.appendChild(tx);
      });
      wrap.appendChild(svg);
      var leg = el("div", "tx-leg");
      [["#5aa9ff", "EMA20"], ["#b58cff", "SMA50"]].concat(lines.map(function (l) { return [l[1], l[2].split(" ")[0] + (l[2].indexOf("ATR") === 0 ? " stop" : "")] })).forEach(function (k) {
        var sp = el("span"); var i = el("i"); i.style.background = k[0]; sp.appendChild(i); sp.appendChild(document.createTextNode(k[1])); leg.appendChild(sp);
      });
      wrap.appendChild(leg);
    }
    draw();
  }

  function render(box, t, ctx) {
    css();
    matrix(box, t, ctx);
    chart(box, t, ctx);
  }

  window.TechView = { render: render };
})();
