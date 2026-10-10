/* Portföy performansı (kendi geçmişine göre): dönem getirileri, aylık tablo, işlem istatistikleri, nakit oranı,
   en büyük düşüş. Veri: history.json (şifre çözülmüş) + o anki toplam değer. Para giriş/çıkışları getiriden ayrılır
   (zaman ağırlıklı getiri: her gün (değer − o günkü net giriş) / önceki değer). Tüm metin textContent ile yazılır. */
(function () {
  "use strict";
  var MON = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
  function el(tag, c, t) { var e = document.createElement(tag); if (c) e.className = c; if (t !== undefined && t !== null) e.textContent = t; return e }
  function n(x, d) { return (x === null || x === undefined || isNaN(+x)) ? "–" : (+x).toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }) }
  function sgn(x) { return x > 0 ? "+" : x < 0 ? "−" : "" }
  var CUR = "$";
  function usd(x, hide) { return hide ? "*****" : sgn(x) + CUR + n(Math.abs(x), 0) }
  function pc(x) { return x === null || x === undefined ? "–" : sgn(x) + "%" + n(Math.abs(x), 2) }
  function cls(x) { return x > 0 ? "up" : x < 0 ? "dn" : "" }

  function css() {
    if (document.getElementById("perf-css")) return;
    var s = document.createElement("style"); s.id = "perf-css";
    s.textContent =
      ".pf-card{background:rgba(17,21,31,.82);border:1px solid var(--line,#1d2330);border-radius:16px;padding:14px;margin:10px 0}" +
      ".pf-h{display:flex;justify-content:space-between;align-items:baseline;gap:8px}.pf-t{font-size:18px;font-weight:700}" +
      ".pf-s{color:var(--mut,#7d8798);font-size:12.5px}" +
      ".pf-seg{display:flex;gap:4px;background:#1a2030;border-radius:12px;padding:3px;margin:10px 0;width:max-content;max-width:100%}" +
      ".pf-seg button{border:0;background:transparent;color:var(--mut,#7d8798);font:inherit;font-weight:600;padding:6px 11px;border-radius:9px;cursor:pointer}" +
      ".pf-seg button.on{background:#27304a;color:var(--txt,#e8ecf4)}" +
      ".pf-tb{width:100%;border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums}" +
      ".pf-tb th{color:var(--mut,#7d8798);font-weight:600;text-align:right;padding:6px 4px;border-bottom:1px solid var(--line,#1d2330)}" +
      ".pf-tb th:first-child,.pf-tb td:first-child{text-align:left}.pf-tb td{text-align:right;padding:7px 4px;border-bottom:1px solid var(--line,#1d2330)}" +
      ".pf-tb tr:last-child td{border-bottom:0}.pf-k{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}" +
      ".pf-k div{background:#151b28;border-radius:12px;padding:10px}.pf-k b{display:block;font-size:16px;margin-top:2px}" +
      ".pf-chart svg{width:100%;height:auto;display:block;margin-top:8px}";
    document.head.appendChild(s);
  }

  /* ---- hesaplar ---- */
  function series(H, P, liveTotal, today) {
    var snaps = ((H && H.snapshots) || []).slice().sort(function (a, b) { return a.date < b.date ? -1 : 1 });
    if (liveTotal && today) {
      var last = snaps[snaps.length - 1];
      var live = { date: today, value: liveTotal, cash: +(P && P.cash) || 0, live: true };
      if (last && last.date === today) snaps[snaps.length - 1] = Object.assign({}, last, live); else snaps.push(live);
    }
    var flows = {};
    ((H && H.transactions) || []).forEach(function (t) {
      if (t.undone) return;
      if (t.action === "deposit") flows[t.date] = (flows[t.date] || 0) + (+t.amount || 0);
      if (t.action === "withdraw") flows[t.date] = (flows[t.date] || 0) - (+t.amount || 0);
    });
    var idx = 1, peak = 1, mdd = 0;
    snaps.forEach(function (s, i) {
      if (i === 0) { s.idx = 1; s.flow = 0; } else {
        var prev = snaps[i - 1], f = 0;
        Object.keys(flows).forEach(function (d) { if (d > prev.date && d <= s.date) f += flows[d] });
        s.flow = f;
        var r = prev.value ? (s.value - f) / prev.value - 1 : 0;
        idx *= 1 + r; s.idx = idx;
      }
      peak = Math.max(peak, s.idx); s.dd = (s.idx / peak - 1) * 100; mdd = Math.min(mdd, s.dd);
      s.cashPct = s.value ? (+s.cash || 0) / s.value * 100 : null;
    });
    return { snaps: snaps, flows: flows, mdd: mdd };
  }

  function period(S, fromDate) {
    var sn = S.snaps; if (sn.length < 2) return null;
    var end = sn[sn.length - 1], start = null;
    for (var i = sn.length - 1; i >= 0; i--) { if (sn[i].date <= fromDate) { start = sn[i]; break } }
    if (!start) start = sn[0];
    if (start === end) return null;
    var flow = 0; sn.forEach(function (s) { if (s.date > start.date && s.date <= end.date) flow += s.flow || 0 });
    return { start: start, end: end, dv: end.value - start.value, flow: flow, gain: end.value - start.value - flow,
      twr: (end.idx / start.idx - 1) * 100, cashFrom: start.cashPct, cashTo: end.cashPct, partial: start === sn[0] && start.date > fromDate };
  }

  function iso(d) { return d.toISOString().slice(0, 10) }
  function trades(H) {
    var sells = ((H && H.transactions) || []).filter(function (t) { return t.action === "sell" && !t.undone && t.realized_pnl != null });
    var w = sells.filter(function (t) { return t.realized_pnl > 0 }), l = sells.filter(function (t) { return t.realized_pnl < 0 });
    var sw = w.reduce(function (s, t) { return s + t.realized_pnl }, 0), sl = l.reduce(function (s, t) { return s + t.realized_pnl }, 0);
    var byM = {};
    sells.forEach(function (t) { var m = t.date.slice(0, 7); byM[m] = byM[m] || { n: 0, w: 0, pnl: 0 }; byM[m].n++; if (t.realized_pnl > 0) byM[m].w++; byM[m].pnl += t.realized_pnl });
    var best = sells.slice().sort(function (a, b) { return b.realized_pnl - a.realized_pnl })[0], worst = sells.slice().sort(function (a, b) { return a.realized_pnl - b.realized_pnl })[0];
    return { n: sells.length, w: w.length, l: l.length, rate: sells.length ? w.length / sells.length * 100 : null,
      avgW: w.length ? sw / w.length : null, avgL: l.length ? sl / l.length : null, pf: sl ? sw / -sl : null,
      total: sw + sl, byM: byM, best: best, worst: worst };
  }

  /* ---- görünüm ---- */
  var view = "ozet";
  function render(box, ctx) {
    css(); box.textContent = "";
    var H = ctx.H, P = ctx.P, hide = ctx.hide; CUR = ctx.cur || "$";
    if (!H || !P) { return }
    var now = new Date(), today = ctx.today || iso(now);
    var S = series(H, P, ctx.total, today), sn = S.snaps;
    var c = el("div", "pf-card");
    var hd = el("div", "pf-h"); hd.appendChild(el("div", "pf-t", "Performans"));
    hd.appendChild(el("div", "pf-s", sn.length ? "kayıt: " + sn[0].date + " → bugün (" + sn.length + " gün)" : "")); c.appendChild(hd);
    var seg = el("div", "pf-seg");
    [["ozet", "Özet"], ["aylik", "Aylık"], ["islem", "İşlemler"]].forEach(function (x) {
      var b = el("button", view === x[0] ? "on" : "", x[1]); b.onclick = function () { view = x[0]; render(box, ctx) }; seg.appendChild(b);
    });
    c.appendChild(seg);
    if (sn.length < 2) { c.appendChild(el("div", "pf-s", "Performans için en az iki günlük kayıt gerekiyor.")); box.appendChild(c); return }
    if (view === "ozet") ozet(c, S, today, hide, ctx);
    else if (view === "aylik") aylik(c, S, hide, P);
    else islem(c, H, hide, P, ctx);
    c.appendChild(el("div", "pf-s", "Getiri, para yatırma/çekmeden arındırılmıştır (zaman ağırlıklı). Kayıt başlangıcından kısa dönemler '*' ile işaretli."));
    box.appendChild(c);
  }

  function ozet(c, S, today, hide, ctx) {
    var d = new Date(today + "T12:00:00Z");
    function back(days) { var x = new Date(d); x.setUTCDate(x.getUTCDate() - days); return iso(x) }
    var prevMonthEnd = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 0)), prevYearEnd = (d.getUTCFullYear() - 1) + "-12-31";
    var rows = [["Önceki gün", back(1)], ["1 hafta", back(7)], ["Bu ay", iso(prevMonthEnd)], ["3 ay", back(91)], ["Yılbaşından", prevYearEnd], ["Başlangıçtan", "0000-00-00"]];
    var tb = el("table", "pf-tb"), hr = el("tr");
    ["Dönem", "Kazanç", "Getiri", "Nakit oranı"].forEach(function (h) { hr.appendChild(el("th", "", h)) }); tb.appendChild(hr);
    rows.forEach(function (r) {
      var p = period(S, r[1]); if (!p) return;
      var tr = el("tr"); tr.appendChild(el("td", "", r[0] + (p.partial ? "*" : "")));
      tr.appendChild(el("td", cls(p.gain), usd(p.gain, hide)));
      tr.appendChild(el("td", cls(p.twr), pc(p.twr)));
      tr.appendChild(el("td", "", "%" + n(p.cashFrom, 1) + " → %" + n(p.cashTo, 1)));
      tb.appendChild(tr);
    });
    c.appendChild(tb);
    var sn = S.snaps, last = sn[sn.length - 1], dd = last.dd;
    var k = el("div", "pf-k");
    function kv(lbl, v, cl) { var x = el("div", "pf-s", lbl); x.appendChild(el("b", cl || "", v)); k.appendChild(x) }
    kv("En büyük düşüş (zirveden)", pc(S.mdd), "dn");
    kv("Şu an zirveden", pc(dd), dd < 0 ? "dn" : "up");
    var unreal = ctx.total && ctx.cost != null ? (ctx.total - (+ctx.P.cash || 0)) - ctx.cost : null;
    kv("Açık pozisyon K/Z", unreal === null ? "–" : usd(unreal, hide), cls(unreal));
    var t = trades(ctx.H); kv("Gerçekleşen K/Z", usd(t.total, hide), cls(t.total));
    var tgt = +(ctx.P.monthly_target || 0), mp = period(S, iso(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 0))));
    if (tgt && mp) kv("Aylık hedefe ilerleme", (hide ? "*****" : usd(mp.gain) + " / " + CUR + n(tgt, 0)) + " (" + sgn(mp.gain) + "%" + n(Math.abs(mp.gain / tgt * 100), 0) + ")", cls(mp.gain));
    kv("Hisse / nakit", "%" + n(100 - (last.cashPct || 0), 1) + " / %" + n(last.cashPct, 1));
    c.appendChild(k);
    chart(c, sn, hide);
  }

  function chart(c, sn, hide) {
    if (sn.length < 3) return;
    var W = 600, H = 170, L = 6, R = 50, T = 10, B = 18, svgNS = "http://www.w3.org/2000/svg";
    var vals = sn.map(function (s) { return s.value }), lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    var pad = (hi - lo) * 0.1 || hi * 0.02; lo -= pad; hi += pad;
    function x(i) { return L + i * (W - L - R) / (sn.length - 1) } function y(v) { return T + (hi - v) / (hi - lo) * (H - T - B) }
    function yc(v) { return T + (60 - Math.min(v, 60)) / 60 * (H - T - B) }
    function mk(tag, a) { var e = document.createElementNS(svgNS, tag); for (var k in a) e.setAttribute(k, a[k]); return e }
    var svg = mk("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Portföy değeri ve nakit oranı" });
    var d1 = "", d2 = "";
    sn.forEach(function (s, i) { d1 += (i ? "L" : "M") + x(i).toFixed(1) + " " + y(s.value).toFixed(1) + " "; if (s.cashPct != null) d2 += (d2 ? "L" : "M") + x(i).toFixed(1) + " " + yc(s.cashPct).toFixed(1) + " " });
    svg.appendChild(mk("path", { d: d2, fill: "none", stroke: "#f5b942", "stroke-width": 1.5, "stroke-dasharray": "4 3" }));
    svg.appendChild(mk("path", { d: d1, fill: "none", stroke: "#5aa9ff", "stroke-width": 2.2 }));
    [[hi, "start"], [lo, "start"]].forEach(function (p) { var t = mk("text", { x: W - R + 4, y: y(p[0]) + 4, fill: "#7d8798", "font-size": 12 }); t.textContent = hide ? "" : CUR + n(p[0] / 1000, 1) + " bin"; svg.appendChild(t) });
    [[0, "start"], [sn.length - 1, "end"]].forEach(function (p) { var t = mk("text", { x: x(p[0]), y: H - 3, fill: "#7d8798", "font-size": 12, "text-anchor": p[1] }); t.textContent = sn[p[0]].date.slice(5).split("-").reverse().join("."); svg.appendChild(t) });
    var w = el("div", "pf-chart"); w.appendChild(svg);
    var lg = el("div", "pf-s", "— mavi: toplam değer · kesikli sarı: nakit oranı (0–%60 ölçek)"); w.appendChild(lg);
    c.appendChild(w);
  }

  function aylik(c, S, hide, P) {
    var sn = S.snaps, months = {};
    sn.forEach(function (s, i) { var m = s.date.slice(0, 7); if (!months[m]) months[m] = { first: i, last: i }; months[m].last = i });
    var keys = Object.keys(months).sort().reverse(), tgt = +(P.monthly_target || 0);
    var tb = el("table", "pf-tb"), hr = el("tr");
    ["Ay", "Kazanç", "Getiri", "Hedef", "Nakit (ay sonu)"].forEach(function (h) { hr.appendChild(el("th", "", h)) }); tb.appendChild(hr);
    keys.forEach(function (m) {
      var e = sn[months[m].last], si = months[m].first > 0 ? months[m].first - 1 : months[m].first, s = sn[si];
      var flow = 0; sn.forEach(function (x) { if (x.date > s.date && x.date <= e.date) flow += x.flow || 0 });
      var gain = e.value - s.value - flow, twr = (e.idx / s.idx - 1) * 100;
      var tr = el("tr"); tr.appendChild(el("td", "", MON[+m.slice(5) - 1] + " " + m.slice(0, 4) + (si === months[m].first ? "*" : "")));
      tr.appendChild(el("td", cls(gain), usd(gain, hide))); tr.appendChild(el("td", cls(twr), pc(twr)));
      tr.appendChild(el("td", tgt && gain >= tgt ? "up" : "", tgt ? "%" + n(gain / tgt * 100, 0) : "–"));
      tr.appendChild(el("td", "", "%" + n(e.cashPct, 1))); tb.appendChild(tr);
    });
    c.appendChild(tb);
  }

  function islem(c, H, hide, P, ctx) {
    var t = trades(H), k = el("div", "pf-k");
    function kv(lbl, v, cl) { var x = el("div", "pf-s", lbl); x.appendChild(el("b", cl || "", v)); k.appendChild(x) }
    kv("Kapanan işlem", t.n + " (" + t.w + " kazanç / " + t.l + " kayıp)");
    kv("Kazanma oranı", t.rate === null ? "–" : "%" + n(t.rate, 0), t.rate >= 50 ? "up" : "dn");
    kv("Ort. kazanç / ort. kayıp", (t.avgW === null ? "–" : usd(t.avgW, hide)) + " / " + (t.avgL === null ? "–" : usd(t.avgL, hide)));
    kv("Kâr faktörü (kazanç ÷ kayıp)", t.pf === null ? "–" : n(t.pf, 2), t.pf >= 1 ? "up" : "dn");
    if (t.best) kv("En iyi işlem", t.best.ticker + " " + usd(t.best.realized_pnl, hide), cls(t.best.realized_pnl));
    if (t.worst) kv("En kötü işlem", t.worst.ticker + " " + usd(t.worst.realized_pnl, hide), cls(t.worst.realized_pnl));
    c.appendChild(k);
    var ms = Object.keys(t.byM).sort().reverse();
    if (ms.length) {
      var tb = el("table", "pf-tb"), hr = el("tr");
      ["Ay", "İşlem", "Kazanma", "Gerçekleşen"].forEach(function (h) { hr.appendChild(el("th", "", h)) }); tb.appendChild(hr);
      ms.forEach(function (m) {
        var x = t.byM[m], tr = el("tr");
        tr.appendChild(el("td", "", MON[+m.slice(5) - 1] + " " + m.slice(0, 4))); tr.appendChild(el("td", "", String(x.n)));
        tr.appendChild(el("td", "", "%" + n(x.w / x.n * 100, 0))); tr.appendChild(el("td", cls(x.pnl), usd(x.pnl, hide))); tb.appendChild(tr);
      });
      tb.style.marginTop = "10px"; c.appendChild(tb);
    }
    // açık pozisyonların kazanç/kayıp dağılımı
    var pos = (P && P.portfolio) || {}, q = (ctx.Q && ctx.Q.quotes) || {}, up = 0, dn = 0;
    Object.keys(pos).forEach(function (s) { var px = q[s] && q[s].c; if (px) { if (px >= pos[s].cost_basis) up++; else dn++ } });
    c.appendChild(el("div", "pf-s", "Açık pozisyonlar: " + up + " kârda, " + dn + " zararda."));
  }

  window.PerfView = { render: render, series: series, trades: trades };
})();
