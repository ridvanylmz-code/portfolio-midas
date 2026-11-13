/* Telegram mini uygulaması: ABD (tg.html) ve BIST (bist/tg.html) için TEK kod. Sayfaya özgü her şey window.APP_CFG'de
   (sayfa kendi satır içi betiğinde tanımlar). ES5; DOM textContent ile kurulur, veriyle innerHTML kullanılmaz. */
(function(){
  var CFG=window.APP_CFG, TX=CFG.txt;
  try{
    var tg=window.Telegram&&window.Telegram.WebApp;
    if(tg){tg.ready();tg.expand();try{if(tg.disableVerticalSwipes)tg.disableVerticalSwipes()}catch(e){}
      try{tg.setHeaderColor("#0a0d14");tg.setBackgroundColor("#0a0d14");}catch(e){}}
  }catch(e){}

  var mode="all", sub="momentum", cur=null, P=null, Q=null, A=null, INTRA=null, BARS=null, H=null, M=null, NOTES=null, TRENDD=null;
  var PEND={a:true,i:true,m:true,b:true};  /* arka planda yüklenen dosyalar: true = henüz gelmedi */
  if(CFG.urls.trend)PEND.t=true;  /* ayrı trend dosyası yalnız ABD'de */
  function techPending(){return PEND.m||PEND.b||PEND.i||PEND.t}
  function isHeld(t){return !!(P&&P.portfolio&&P.portfolio[t])}
  function isWatched(t){return !!(P&&P.watchlist&&P.watchlist.indexOf(t)>=0)}
  function hasInfo(t){return !!((A&&A.tickers&&A.tickers[t])||isHeld(t)||isWatched(t))}
  function addKV(box,k,v,c){var row=el("div","kv");row.appendChild(el("span","",k));row.appendChild(el("span",c||"",v));box.appendChild(row);return row}
  /* Ön/kapanış sonrası fiyatı: quotes.json'daki ext alanı güncelse (3 saat) fiyat/değişim onunla gösterilir; kapanış korunur. */
  function eff(q){
    var e=q&&q.ext; if(!e||!(+e.p>0))return q;
    if(!(Date.now()-new Date(e.t).getTime()<3*3600e3))return q;
    var base=e.sess==="pre"?+q.c:(+q.pc||+q.c); if(!(base>0))return q;
    var o={}; for(var k in q)o[k]=q[k];
    o.c=+e.p; o.d=o.c-base; o.dp=(o.c/base-1)*100; o.pc=base; o.extp=e.sess; o.close=+q.c; return o;
  }
  function extTag(x){return x&&x.extp?(x.extp==="pre"?" 🌅":" 🌙"):""}
  var SESS_ICO={pre:"🌅",regular:"☀️",post:"🌙",kapali:"⏸"};
  function arrow(d){return d==="up"?["▲","up"]:d==="down"?["▼","dn"]:["■","warn"]}
  function renderIntraday(box,t){
    var hd=el("div","sub","Gün içi sinyaller"); hd.style.margin="4px 0 2px"; box.appendChild(hd);
    if(PEND.i){box.appendChild(el("div","sub","Yükleniyor…"));return}
    var e=INTRA&&INTRA.tickers&&INTRA.tickers[t];
    if(!e){box.appendChild(el("div","sub",TX.intraEmpty));return}
    var h=e.h4, m=e.m15, w=e.elliott, a;
    var pl=!!CFG.plain, st=pl?e.st15:null;  /* sade dil: BIST trend dosyası (4S/15dk Trend + 15dk Tamam yada Devam) */
    var dirTxt=function(d){return d==="up"?"yükseliş":d==="down"?"düşüş":"yatay"};
    var ago=function(v){return pl?(v!==null&&v!==undefined):v!==null};
    if(h){a=arrow(h.dir);
      if(pl){addKV(box,"4S Trend",a[0]+" "+dirTxt(h.dir),a[1]);
        addKV(box,"   değerler",num(h.ema8,2)+" / "+num(h.ema20,2)+(ago(h.cross_bars_ago)?" · kesişim "+h.cross_bars_ago+" mum önce":""),a[1])}
      else{addKV(box,"4s trend (EMA 8 / 20)",a[0]+" "+num(h.ema8,2)+" / "+num(h.ema20,2),a[1]);
        addKV(box,"   fark",(h.diff>=0?"+":"−")+num(Math.abs(h.diff),2)+(ago(h.cross_bars_ago)?" · kesişim "+h.cross_bars_ago+" mum önce":""),a[1])}
    }
    if(m){a=arrow(m.dir);
      if(pl){addKV(box,"15dk Trend",a[0]+" "+dirTxt(m.dir),a[1]);
        addKV(box,"   değerler",num(m.ema34,2)+" / "+num(m.ema89,2)+(ago(m.cross_bars_ago)?" · kesişim "+m.cross_bars_ago+" mum önce":""),a[1])}
      else{addKV(box,"15dk kısa vade (EMA 34 / 89)",a[0]+" "+dirTxt(m.dir),a[1]);
        addKV(box,"   değerler",num(m.ema34,2)+" / "+num(m.ema89,2)+(ago(m.cross_bars_ago)?" · kesişim "+m.cross_bars_ago+" mum önce":""),a[1])}
    }
    if(st){a=st.dir==="up"?["▲ Devam","up"]:["▼ Tamam","dn"];
      addKV(box,"15dk Tamam yada Devam",a[0],a[1]);
      addKV(box,"   çizgi",num(st.line,2)+" · fiyata %"+num(+st.dist_pct,1)+" uzak"+(st.bars_since_flip!==null&&st.bars_since_flip!==undefined?" · "+st.bars_since_flip+" mumdur bu yönde":""),a[1]);
    }
    if(w){a=w.bias==="up"?["▲","up"]:w.bias==="down"?["▼","dn"]:["■","warn"];
      addKV(box,pl?"Elliott (4S, muhtemel)":"Elliott (4s, muhtemel)",a[0]+" "+w.label,a[1]);
    }
    var when=INTRA.updated?new Date(INTRA.updated).toLocaleString("tr-TR",{timeZone:"Europe/Istanbul",hour12:false,day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"–";
    var n=el("div","sub",(SESS_ICO[INTRA.session]||"")+" Veri: "+when+" (İstanbul)"+(e.stale?" · bu hisse eski":"")+" · "+(pl?"Yahoo Finance 15dk (gecikmeli), yalnızca normal seans mumları":"Twelve Data 15dk, "+(INTRA.prepost?"ön/sonrası dahil":"yalnızca normal seans mumları"))+"."); n.style.margin="6px 0 12px"; box.appendChild(n);
  }
  var $=function(id){return document.getElementById(id)};
  var usd=function(n){return CFG.cur+n.toLocaleString("tr-TR",{minimumFractionDigits:2,maximumFractionDigits:2})};
  var num=function(n,d){return n.toLocaleString("tr-TR",{minimumFractionDigits:d,maximumFractionDigits:d})};
  var sgn=function(n){return n>=0?"+":"−"};
  var cls=function(n){return n>=0?"up":"dn"};
  function el(tag,c,t){var e=document.createElement(tag);if(c)e.className=c;if(t!==undefined)e.textContent=t;return e}
  var TRMON=["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"];
  function fmtT(ms){var o={};  /* İstanbul saati: gg.aa ss:dd */
    new Intl.DateTimeFormat("tr-TR",{timeZone:"Europe/Istanbul",hourCycle:"h23",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}).formatToParts(new Date(ms)).forEach(function(p){o[p.type]=p.value});
    return o.day+"."+o.month+" "+o.hour+":"+o.minute}
  function dayTxt(iso){var y=+iso.slice(0,4);return (+iso.slice(8,10))+" "+TRMON[+iso.slice(5,7)-1]+(y!==new Date().getFullYear()?" "+y:"")}
  function pad2(n){return (n<10?"0":"")+n}
  /* Yazılı teknik bloğun tarihi: technical_date (ISO) varsa o; yoksa ilk satırın başındaki "9 Eki" gibi tarih (gelecekte olmayan en yakın gün). */
  function techDate(d){
    var iso=null, s=d&&d.technical_date, today=new Date().toLocaleDateString("en-CA");
    if(typeof s==="string"&&/^\d{4}-\d{2}-\d{2}/.test(s))iso=s.slice(0,10);
    else{
      var m=String(((d&&d.technical)||[])[0]||"").match(/^\s*(\d{1,2}) (Oca|Şub|Mar|Nis|May|Haz|Tem|Ağu|Eyl|Eki|Kas|Ara)(?![a-zçğıöşü])/);
      if(m){var y=+today.slice(0,4), mo=TRMON.indexOf(m[2])+1;
        iso=y+"-"+pad2(mo)+"-"+pad2(+m[1]); if(iso>today)iso=(y-1)+"-"+pad2(mo)+"-"+pad2(+m[1])}
    }
    if(!iso)return null;
    return {iso:iso,txt:dayTxt(iso),days:Math.floor((Date.parse(today+"T12:00:00Z")-Date.parse(iso+"T12:00:00Z"))/864e5)};
  }
  function load(name,optional){
    return fetch("data/"+name+"?t="+Date.now(),{cache:"no-store"}).then(function(r){
      if(!r.ok)throw new Error(name+" "+r.status);return r.json()}).catch(function(e){
      if(optional)return null;throw e}).then(function(j){return window.Vault?Vault.open(j):j});
  }
  function momCls(s){s=(s||"").toLowerCase();
    if(s.indexOf("güçlü")===0)return "up"; if(s.indexOf("zayıf")===0)return "dn"; return "warn"}
  function riskCls(s){s=(s||"").toLowerCase();
    if(s.indexOf("yüksek")===0)return "dn"; if(s.indexOf("düşük")===0)return "up"; return "warn"}

  /* ---------- sekmeler ---------- */
  function showTab(t){
    if(CFG.tabs.indexOf(t)<0)t="portfoy";
    if(t==="poz"&&CFG.poz)loadPoz();
    [].forEach.call(document.querySelectorAll(".tab"),function(s){s.classList.toggle("on",s.id==="t-"+t)});
    [].forEach.call($("nav").children,function(b){b.classList.toggle("on",b.getAttribute("data-t")===t)});
    try{history.replaceState(null,"","#"+t)}catch(e){}
    window.scrollTo(0,0);
  }
  $("nav").addEventListener("click",function(e){
    var b=e.target.closest("button"); if(b)showTab(b.getAttribute("data-t"));
  });

  /* ---------- portföy ---------- */
  /* tutar gizleme: tutarlar, adet ve maliyet *****; yüzdeler ve fiyatlar açık kalır */
  var hide=false;
  try{hide=localStorage.getItem("pm_hide")==="1"}catch(e){}
  document.body.classList.toggle("hide",hide);
  function mk(s){return hide?"*****":s}
  // Yazılı notlardaki ortalama maliyet rakamlarını gizler ("maliyetin (78,82) altında" -> "maliyetin ***** altında")
  /* Analiz metinlerinde {cost:T} {stop:T} {target:T} {shares:T}: değerler şifreli portföyden doldurulur (public dosyada sayı yok). */
  function tok(s){return String(s).replace(/\{(cost|stop|target|shares):([A-Z0-9.\-]+)\}/g,function(_,k,t){
    var pos=P&&P.portfolio&&P.portfolio[t], lv=(P&&P.position_levels||{})[t]||{}, v=null;
    if(k==="cost"&&pos)v=pos.cost_basis; else if(k==="shares"&&pos)v=pos.shares;
    else if(k==="stop")v=lv.stop_loss; else if(k==="target")v=lv.target;
    if(v===null||v===undefined)return "–";
    return k==="shares"?num(+v,0):usd(+v)})}
  function mc(s){s=tok(s);return hide?String(s).replace(/(maliyet[a-zçğıöşü]*\s*)\(?\$?\d+(?:[.,]\d+)*\)?/gi,"$1*****"):s}
  $("eye").addEventListener("click",function(){
    hide=!hide; document.body.classList.toggle("hide",hide);
    try{localStorage.setItem("pm_hide",hide?"1":"0")}catch(e){}
    if(P){renderPortfolio();renderAnaliz();renderSector();if(!CFG.perfFromRows)renderPerf();if(POZ)renderPoz()}
  });

  function trendChip(t){
    if(CFG.stateChips){  /* BIST: trend dosyasındaki 4S/15dk durumu (Bullish/Bearish/Karışık) */
      var e=INTRA&&INTRA.tickers&&INTRA.tickers[t]; if(!e||!e.state||e.state==="n/a")return null;
      var L={bullish:["Bullish","up"],bearish:["Bearish","dn"],mixed:["Karışık","warn"]}[e.state]; if(!L)return null;
      return el("span","chipx "+L[1],L[0]);
    }
    var s=M&&M.stocks&&M.stocks[t]; if(!s||!s.trend)return null;
    var p=s.trend.points, c=p>=5?"up":p<=2?"dn":"warn";
    return el("span","chipx "+c,s.trend.label+" "+p+"/7");
  }
  function levelBar(t,price){
    var lv=(P.position_levels||{})[t]||{}, st=lv.stop_loss, tg=lv.target;
    if(st==null||tg==null||!(tg>st))return null;
    var w=el("div","lvl"), tr=el("div","tr"), mkr=el("i","mk");
    var f=Math.max(0,Math.min(1,(price-st)/(tg-st))); mkr.style.left="calc("+(f*100)+"% - 1px)";
    tr.appendChild(mkr); w.appendChild(tr);
    var lb=el("div","lb"); lb.appendChild(el("span",price<=st?"dn":"","Stop "+usd(+st)+(price<=st?" ⚠ kırıldı":" · %"+num((price-st)/price*100,1)+" uzak")));
    lb.appendChild(el("span","","Hedef "+usd(+tg)+" · %"+num((tg-price)/price*100,1))); w.appendChild(lb);
    return w;
  }
  /* Piyasa açık mı: tarayıcı saatinden, seans APP_CFG.mkt'de (ABD 09:30–16:00 New York, BIST 10:00–18:10 İstanbul; tatil takvimi yok).
     Veri yaşı Q.updated'dan. */
  var MKT=CFG.mkt;
  function marketOpenNow(){
    try{
      var o={}; new Intl.DateTimeFormat("en-US",{timeZone:MKT.tz,weekday:"short",hour:"2-digit",minute:"2-digit",hourCycle:"h23"})
        .formatToParts(new Date()).forEach(function(p){o[p.type]=p.value});
      if(o.weekday==="Sat"||o.weekday==="Sun")return false;
      var m=(+o.hour)*60+(+o.minute); return m>=MKT.from&&m<MKT.to;
    }catch(e){return !!(Q&&Q.market_open)}
  }
  function ageTxt(ms){var m=Math.floor(ms/6e4);return "⚠ Veri "+Math.floor(m/60)+" sa "+(m%60)+" dk eski"}
  function renderStatus(){
    if(!P)return;
    var q=(Q&&Q.quotes)||{}, open=marketOpenNow(), upd=Q&&Q.updated?new Date(Q.updated):null;
    var age=upd&&!isNaN(upd.getTime())?Date.now()-upd.getTime():null, stale=age!==null&&(open?age>45*6e4:age>24*36e5);
    var ex=Object.keys(P.portfolio||{}).map(function(t){return q[t]}).filter(function(x){return x&&x.extp})[0];
    var foot=$("foot"); foot.textContent=(open?"Piyasa Açık":"Piyasa Kapalı")+(ex?" · "+(ex.extp==="pre"?"🌅 ön piyasa fiyatı":"🌙 kapanış sonrası fiyat"):"")+
      (upd?" · Son güncelleme "+fmtT(upd.getTime()):"");
    if(stale)foot.appendChild(el("span","stale"," · "+ageTxt(age)));
    foot.appendChild(document.createTextNode(" · Gecikmeli veri"));
    var bar=$("stale"); bar.textContent=""; if(stale&&open)bar.appendChild(el("div","stalebar",ageTxt(age)));
  }
  function renderPortfolio(){
    var pf=P.portfolio||{}, q=(Q&&Q.quotes)||{};
    var rows=[], posVal=0, cost=0, dayPnl=0;
    Object.keys(pf).forEach(function(t){
      var s=+pf[t].shares||0, cb=+pf[t].cost_basis||0;
      if(!s)return;
      var x=q[t]||{}, c=+x.c||0;
      var v=s*c, cs=s*cb, pnl=v-cs, d=s*(+x.d||0);
      posVal+=v; cost+=cs; dayPnl+=d;
      rows.push({t:t,s:s,cb:cb,c:c,v:v,pnl:pnl,pct:cs?pnl/cs*100:0,dp:+x.dp||0,d:d,x:x});
    });
    rows.sort(function(a,b){return b.v-a.v});
    var cash=+P.cash||0, total=posVal+cash;

    $("total").textContent=mk(usd(total));
    var pill=$("pnl"), val, pct;
    if(mode==="day"){val=dayPnl;pct=(posVal-dayPnl)?dayPnl/(posVal-dayPnl)*100:0}
    else{val=posVal-cost;pct=cost?(posVal-cost)/cost*100:0}
    pill.className="pill "+cls(val);
    pill.textContent=(val>=0?"▲ ":"▼ ")+sgn(val)+mk(usd(Math.abs(val)))+"  (%"+sgn(pct)+num(Math.abs(pct),2)+")";

    $("cnt").textContent=rows.length;
    var list=$("list"); list.textContent="";
    rows.forEach(function(r){
      var card=el("div","card"), l=el("div","l"), rr=el("div","r");
      var tk=el("div","tk",r.t); tk.appendChild(el("small","",mk(num(r.s,r.s%1?2:0)+" adet")));
      l.appendChild(tk);
      var tl=el("div","sub"), ch=trendChip(r.t); if(ch)tl.appendChild(ch);
      tl.appendChild(document.createTextNode("ağırlık %"+num(total?r.v/total*100:0,1))); l.appendChild(tl);
      l.appendChild(el("div","sub","Maliyet "+mk(usd(r.cb))));
      l.appendChild(el("div","sub "+cls(r.dp),usd(r.c)+"  ("+sgn(r.dp)+num(Math.abs(r.dp),2)+"%)"+extTag(r.x)));
      if(r.x&&r.x.extp)l.appendChild(el("div","sub","Kapanış "+usd(r.x.close)));
      var dv=mode==="day"?r.d:r.pnl, dpct=mode==="day"?r.dp:r.pct;
      rr.appendChild(el("div","val",mk(usd(r.v))));
      rr.appendChild(el("div","sub "+cls(dv),sgn(dv)+mk(usd(Math.abs(dv)))));
      rr.appendChild(el("div","sub "+cls(dv),"%"+sgn(dpct)+num(Math.abs(dpct),2)));
      card.appendChild(l); card.appendChild(rr);
      var lvb=levelBar(r.t,r.c); if(lvb)card.appendChild(lvb);
      var lv0=(P.position_levels||{})[r.t]||{}; if(lv0.stop_loss!=null&&r.c<=lv0.stop_loss)card.classList.add("broken");
      if(hasInfo(r.t)){card.style.cursor="pointer";
        card.addEventListener("click",function(){openAnaliz(r.t)})}
      list.appendChild(card);
    });
    if(!rows.length&&TX.emptyPortfolio)list.appendChild(el("div","empty",TX.emptyPortfolio));
    $("cash").textContent=mk(usd(cash))+(total?"  ·  %"+num(cash/total*100,1):"");
    renderStatus();
    if(CFG.perfFromRows)renderPerf(rows,total,cost);
    if(!$("defterBtn")){var db=el("a","","📒 Portföy Defteri (4 hesap) →");db.id="defterBtn";db.href=CFG.defterHref;
      db.style.cssText="display:block;margin:10px 0 4px;padding:10px 12px;border:1px solid rgba(62,224,143,.35);border-radius:10px;color:#3ee08f;text-decoration:none;font-weight:600;text-align:center";
      $("foot").parentNode.insertBefore(db,$("foot"))}
    if(window.Vault&&Vault.unlocked()&&!$("lockBtn")){var lb=el("a","","🔒 Kilitle");lb.id="lockBtn";lb.href="#";
      lb.style.cssText="display:block;margin-top:6px;color:inherit;opacity:.7;text-decoration:underline";
      lb.onclick=function(e){e.preventDefault();Vault.forget()};$("foot").parentNode.insertBefore(lb,$("foot").nextSibling)}
  }
  $("seg").addEventListener("click",function(e){
    var m=e.target.getAttribute&&e.target.getAttribute("data-m"); if(!m||!P)return;
    mode=m; [].forEach.call($("seg").children,function(b){b.classList.toggle("on",b.getAttribute("data-m")===m)});
    renderPortfolio();
  });

  /* ---------- pozisyonlar: hesap bazında adet / maliyet / değer (şifreli dosyalar tarayıcıda açılır) ---------- */
  var POZ=null, pozLoading=null;
  var RAW="https://raw.githubusercontent.com/ridvanylmz-code/portfolio-midas/main/";
  function pozRows(pos,quotes,costKey){
    var out=[];
    Object.keys(pos||{}).forEach(function(t){
      var p=pos[t]||{}, s=+p.shares||0; if(!s)return;
      var cb=p[costKey]==null?null:+p[costKey], x=quotes[t]||{}, px=+x.c||+p.last||0;
      out.push({t:t,s:s,cb:cb,v:px?s*px:null});
    });
    return out.sort(function(a,b){return (b.v||0)-(a.v||0)});
  }
  /* IBKR: Flex 'Open Positions' (defter.json → ibkr_pos_detail; eski kayıtta yalnız adet: ibkr_positions) */
  function ibkrRows(d){
    if(!d)return null; var det=d.ibkr_pos_detail, q=d.ibkr_positions, pos={};
    if(det)Object.keys(det).forEach(function(t){pos[t]={shares:det[t].shares,cost:det[t].cost,last:det[t].mark}});
    else if(q)Object.keys(q).forEach(function(t){pos[t]={shares:q[t],cost:null}});
    else return null;
    return pozRows(pos,(Q&&Q.quotes)||{},"cost");
  }
  function loadPoz(){
    if(POZ||pozLoading||!P)return;
    var j=function(u){return fetch(u+"?t="+Date.now(),{cache:"no-store"}).then(function(r){return r.ok?r.json():null})
      .catch(function(){return null}).then(function(o){return o&&window.Vault?Vault.open(o):o})};
    pozLoading=Promise.all([j("bist/data/portfolio.json"),j("bist/data/quotes.json"),j(RAW+"defter/info_portfolio.json"),j("defter/data/defter.json")]).then(function(r){
      var bq=(r[1]&&r[1].quotes)||{};
      POZ=[{n:"Midas-USD",rows:pozRows(P.portfolio,(Q&&Q.quotes)||{},"cost_basis")},
           {n:"IBKR",rows:ibkrRows(r[3])},
           {n:"Midas-TR",rows:r[0]?pozRows(r[0].portfolio,bq,"cost_basis"):null},
           {n:"Info-TR",rows:r[2]?pozRows(r[2].positions,bq,"cost"):null}];
      pozLoading=null; renderPoz();
    });
  }
  function renderPoz(){
    var box=$("pozBody"); box.textContent="";
    POZ.forEach(function(g){
      var h=el("div","sec",g.n); if(g.rows)h.appendChild(el("span","badge",String(g.rows.length))); box.appendChild(h);
      if(!g.rows){box.appendChild(el("div","empty","Veri okunamadı"));return}
      if(!g.rows.length){box.appendChild(el("div","empty","Pozisyon yok"));return}
      var wrap=el("div","box"), tb=el("table","ptbl"), hr=el("tr"), tot=0, miss=false;
      ["Hisse","Adet","Maliyet","Değer"].forEach(function(k){hr.appendChild(el("th","",k))}); tb.appendChild(hr);
      g.rows.forEach(function(r){
        var tr=el("tr"); tr.appendChild(el("td","",r.t));
        tr.appendChild(el("td","",mk(num(r.s,r.s%1?2:0))));
        tr.appendChild(el("td","",r.cb==null?"–":mk(num(r.cb,2))));
        tr.appendChild(el("td","",r.v==null?"fiyat yok":mk(num(r.v,2))));
        if(r.v==null)miss=true; else tot+=r.v; tb.appendChild(tr);
      });
      var tt=el("tr","tot"); tt.appendChild(el("td","","Toplam")); tt.appendChild(el("td")); tt.appendChild(el("td"));
      tt.appendChild(el("td","",mk(num(tot,2))+(miss?"*":""))); tb.appendChild(tt);
      wrap.appendChild(tb); box.appendChild(wrap);
    });
  }

  /* ---------- takip ---------- */
  function renderWatch(){
    var q=(Q&&Q.quotes)||{}, wl=(P.watchlist||[]).slice(), box=$("wl"); box.textContent="";
    if(!wl.length){box.appendChild(el("div","empty","Takip listesi boş"));return}
    var MS=(M&&M.stocks)||{};
    wl.sort(function(a,b){return ((MS[b]&&MS[b].rs&&MS[b].rs.score)||-999)-((MS[a]&&MS[a].rs&&MS[a].rs.score)||-999)});
    wl.forEach(function(t){
      var x=q[t]||{}, row=el("div","wl2"), has=hasInfo(t), s=MS[t], d=(A&&A.tickers&&A.tickers[t])||{};
      var a=el("div","a"), b=el("b","",t); if(has)b.appendChild(el("small","","analiz ›"));
      a.appendChild(b);
      a.appendChild(el("span", x.c?cls(+x.dp||0):"sub", x.c?(usd(+x.c)+"  "+sgn(+x.dp||0)+num(Math.abs(+x.dp||0),2)+"%"+extTag(x)):"–"));
      row.appendChild(a);
      var line=el("div","b"), ch=trendChip(t); if(ch)line.appendChild(ch);
      if(CFG.stateChips&&s&&s.trend){var tp0=s.trend.points; line.appendChild(el("span","chipx "+(tp0>=5?"up":tp0<=2?"dn":"warn"),"Günlük "+tp0+"/7"))}
      var bits=[];
      if(s&&s.rs&&s.rs.score!=null)bits.push("RS "+(s.rs.score>0?"+":"−")+num(Math.abs(s.rs.score),1));
      if(s&&s.verdict)bits.push(s.verdict);
      // adil değer (analist hedefi) ve bilanço tarihi analiz dosyasından
      var tp=d.fundamental&&d.fundamental.target_price, tgt=(typeof tp==="number"&&tp>0)?tp:0;
      if(!tgt&&CFG.targetFromText){var fv=(d.fundamental&&d.fundamental.fair_value)||"", m1=fv.match(/hedefi \$([\d.]+,?\d*)/);  // sayısal alan yoksa metinden
        if(m1)tgt=+m1[1].replace(/\./g,"").replace(",",".")||0}
      if(tgt>0&&x.c)bits.push("hedefe %"+(tgt>=x.c?"+":"−")+num(Math.abs(tgt/x.c*100-100),0));
      // bilanço: önce market.json earn_next (aşağıda); yoksa analiz metninden
      if(!(s&&s.earn_next)){
      var er=((d.fundamental&&d.fundamental.metrics)||[]).filter(function(k){return /bilanço/i.test(k[0])})[0];
      if(er){var MON={Oca:0,"Şub":1,Mar:2,Nis:3,May:4,Haz:5,Tem:6,"Ağu":7,Eyl:8,Eki:9,Kas:10,Ara:11},mm=String(er[1]).match(/(\d{1,2}) (\S{3}) (\d{4})/);
        if(mm&&MON[mm[2]]!==undefined){var dd=Math.ceil((new Date(+mm[3],MON[mm[2]],+mm[1])-new Date())/864e5);if(dd>=0)bits.push("bilanço "+dd+" gün")}}
      }
      var zz=(P.buy_zones||{})[t]; if(zz!=null){if(typeof zz==="number")zz={below:zz};
        bits.push("🎯 alarm "+(zz.below!=null?"≤"+usd(+zz.below):"")+(zz.above!=null?" ≥"+usd(+zz.above):""))}
      if(s&&s.earn_next){var ed=Math.ceil((new Date(s.earn_next+"T12:00:00Z")-new Date())/864e5);if(ed>=0&&ed<=7)bits.push("📅 bilanço "+ed+" gün")}
      if(s&&s.ema20&&s.close)bits.push(CFG.plain?(s.close>=s.ema20?"20 günlük çizginin üstünde (geri çekilmede giriş "+num(s.ema20,2)+")":"giriş için 20 günlük çizgi ("+num(s.ema20,2)+") üstü kapanış")
        :(s.close>=s.ema20?"EMA20 üstünde (geri çekilmede giriş "+num(s.ema20,2)+")":"giriş için EMA20 ("+num(s.ema20,2)+") üstü kapanış"));
      line.appendChild(document.createTextNode(bits.join(" · ")));
      row.appendChild(line);
      if(has){row.style.cursor="pointer";row.addEventListener("click",function(){openAnaliz(t)})}
      box.appendChild(row);
    });
  }

  /* ---------- haber satırı (Analiz → Haber) ---------- */
  function newsItem(n){
    var a=el("a","news"); a.textContent="";
    var url=(n.url||""); if(url.indexOf("https://")===0){a.href=url;a.target="_blank";a.rel="noopener noreferrer"}
    a.appendChild(el("div","",n.title||""));
    a.appendChild(el("div","d",(n.date||"")+(n.src?" · "+n.src:"")));
    return a;
  }
  /* ---------- analiz ---------- */
  /* 'Göstergeler ne anlatır?' sözlüğü: ABD (EMA/SMA/Supertrend) ve sade dil (BIST) */
  var GLOSS_US=[["EMA / SMA","Hareketli ortalama. Fiyat ortalamanın üstündeyse o zaman diliminde alıcılar baskın. Kısa ortalamanın uzunu yukarı kesmesi trend dönüşü işaretidir."],
       ["RSI","0-100 arası ivme. 70 üstü aşırı alım, 30 altı aşırı satım; 50 üstü alıcı, altı satıcı baskısı."],
       ["MACD","İki ortalama farkı. Sinyal çizgisinin üstüne çıkması ivmenin yukarı döndüğünü gösterir."],
       ["ADX","Trendin gücü (yönü değil). 20 altı trend yok, 25 üstü güçlü trend."],
       ["Supertrend","ATR'ye göre çizilen iz süren çizgi. Fiyat çizginin altına inince yön düşüşe döner; geçici stop gibi okunur."],
       ["ATR stop","Hissenin günlük ortalama oynaklığına (ATR) göre stop: günlük kapanışın 2×ATR aşağısı. Takip eden stop yalnız kapanışla ve yalnız yukarı taşınır."],
       ["Elliott","Fiyatın 5 itki + 3 düzeltme dalgası yaptığı varsayımı. Kural tabanlı tahmindir, kesin sayım değildir; tek başına al/sat sinyali değildir."],
       ["Zaman dilimi uyumu","Haftalık ve günlük yön trendi, 4s ve 15dk giriş zamanlamasını gösterir. Hepsi aynı yöndeyse sinyal güçlüdür."]
  ];
  var GLOSS_PLAIN=[["Ortalama çizgileri","Fiyatın son N günün ortalamasına göre konumu. Fiyat çizginin üstündeyse o zaman diliminde alıcılar baskın; kısa çizginin uzunu yukarı kesmesi trend dönüşü işaretidir."],
       ["RSI","0-100 arası ivme. 70 üstü aşırı alım, 30 altı aşırı satım; 50 üstü alıcı, altı satıcı baskısı."],
       ["MACD","İki ortalama farkı. Sinyal çizgisinin üstüne çıkması ivmenin yukarı döndüğünü gösterir."],
       ["ADX","Trendin gücü (yönü değil). 20 altı trend yok, 25 üstü güçlü trend."],
       ["15dk Tamam yada Devam","Fiyatı izleyen çizgi. Fiyat çizginin altına inince 'Tamam', üstüne çıkınca 'Devam'; geçici stop gibi okunur."],
       ["ATR stop","Hissenin günlük ortalama oynaklığına (ATR) göre stop: günlük kapanışın 2×ATR aşağısı. Takip eden stop yalnız kapanışla ve yalnız yukarı taşınır."],
       ["Elliott","Fiyatın 5 itki + 3 düzeltme dalgası yaptığı varsayımı. Kural tabanlı tahmindir, kesin sayım değildir; tek başına al/sat sinyali değildir."],
       ["Zaman dilimi uyumu","Haftalık ve günlük yön trendi, 4S ve 15dk giriş zamanlamasını gösterir. Hepsi aynı yöndeyse sinyal güçlüdür."]
  ];
  function openAnaliz(t){cur=t;renderAnaliz();showTab("analiz")}
  function renderAnaliz(){
    var T=(A&&A.tickers)||{}, chips=$("chips"), body=$("abody");
    var hl=Object.keys((P&&P.portfolio)||{}), wl=((P&&P.watchlist)||[]).filter(function(t){return hl.indexOf(t)<0});
    var keys=hl.concat(wl);
    chips.textContent=""; body.textContent="";
    $("anote").textContent=A&&A.note?A.note+(A.updated?" (Yazılı analiz: "+A.updated+")":""):"";
    if(!keys.length){body.appendChild(el("div","empty","Henüz elde tutulan ya da takip edilen hisse yok"));return}
    if(!cur||keys.indexOf(cur)<0)cur=keys[0];
    [["Elimde",hl],["Takip",wl]].forEach(function(g){
      if(!g[1].length)return;
      var grp=el("div","chipg"); grp.appendChild(el("span","chipl",g[0]));
      g[1].forEach(function(t){
        var c=el("button","chip"+(t===cur?" on":""),t);
        c.addEventListener("click",function(){cur=t;renderAnaliz()});
        grp.appendChild(c);
      });
      chips.appendChild(grp);
    });
    [].forEach.call($("sub").children,function(b){b.classList.toggle("on",b.getAttribute("data-s")===sub)});
    var d=T[cur]||{}, q=((Q&&Q.quotes)||{})[cur]||{}, box=el("div","body");
    var noText=!T[cur]&&sub!=="teknik";

    if(sub!=="teknik"&&PEND.a){
      box.appendChild(el("div","empty","Yükleniyor…"));
    }else if(noText){
      box.appendChild(el("div","sub","Bu hisse için henüz yazılı analiz yok (sadece Teknik sekmesinde veri var)."));
    }else if(sub==="momentum"){
      var m=d.momentum||{};
      box.appendChild(el("div","big "+momCls(m.status),m.status||"–"));
      box.appendChild(el("div","",mc(m.text||"")));
      if(typeof d.momentum_date==="string"&&/^\d{4}-\d{2}-\d{2}/.test(d.momentum_date)){var md=el("div","sub","Analiz tarihi: "+dayTxt(d.momentum_date.slice(0,10)));md.style.marginTop="8px";box.appendChild(md)}
    }else if(sub==="teknik"){
      if(q.c){
        var chg=usd(+q.c)+" ("+sgn(+q.dp||0)+num(Math.abs(+q.dp||0),2)+"%)", tq=q.t?" · "+fmtT(+q.t*1000):"";
        if(q.extp){
          addKV(box,(q.extp==="pre"?"Ön piyasa fiyatı":"Kapanış sonrası fiyat")+(q.ext&&q.ext.t?" · "+fmtT(new Date(q.ext.t).getTime()):""),chg,cls(+q.dp||0));
          addKV(box,"Kapanış"+tq,usd(+q.close));
        }else addKV(box,"Son fiyat"+tq,chg,cls(+q.dp||0));
        addKV(box,"Gün aralığı",usd(+q.l)+" – "+usd(+q.h));
      }
      if(techPending())box.appendChild(el("div","empty","Yükleniyor…"));
      else if(window.TechView){
        var tc={M:M,BARS:BARS,INTRA:INTRA,TREND:CFG.urls.trend?TRENDD:INTRA,P:P,tz:MKT.tz};
        for(var tk in (CFG.tech||{}))tc[tk]=CFG.tech[tk];
        TechView.render(box,cur,tc);
      }
      function det(title,open){var x=document.createElement("details");x.className="tx-d";if(open)x.open=true;x.appendChild(el("summary","",title));box.appendChild(x);return x}
      if((d.technical||[]).length){
        var td=techDate(d), old=td&&td.days>7;  // 7 günden eski yazılı teknik blok kapalı ve "ESKİ" işaretli
        var wn=det(old?TX.written+" — ESKİ ("+td.txt+")":TX.written+" ("+(td?td.txt:(A&&A.updated||""))+")");
        if(old)wn.firstChild.style.color="var(--warn)";
        var ul=el("ul"); d.technical.forEach(function(s){ul.appendChild(el("li","",mc(s)))}); wn.appendChild(ul);
      }
      var raw=det(TX.intraTitle);
      renderIntraday(raw,cur);
      var gl=det("Göstergeler ne anlatır?");
      (CFG.plain?GLOSS_PLAIN:GLOSS_US)
      .forEach(function(k){var r=el("div","kv");r.appendChild(el("span","",k[0]));r.appendChild(el("span","",k[1]));r.lastChild.style.fontWeight="400";gl.appendChild(r)});
    }else if(sub==="temel"){
      ((d.fundamental&&d.fundamental.metrics)||[]).forEach(function(kv){
        var k=el("div","kv"); k.appendChild(el("span","",kv[0])); k.appendChild(el("span","",kv[1])); box.appendChild(k)});
      if(d.fundamental&&d.fundamental.fair_value){
        var f=el("div","kv"); f.appendChild(el("span","","Adil değer")); var fvt=d.fundamental.fair_value, tpv=d.fundamental.target_price;
        if(typeof tpv==="number"&&tpv>0&&+q.c>0){var gp=(tpv/+q.c-1)*100; fvt+=" (güncel fiyata göre %"+sgn(gp)+num(Math.abs(gp),0)+")"}
        f.appendChild(el("span","",fvt)); box.appendChild(f)}
      if(d.dilution){
        var r=el("div","kv"); r.appendChild(el("span","","Sermaye artırımı riski (12 ay)"));
        r.appendChild(el("span",riskCls(d.dilution.risk),d.dilution.risk)); box.appendChild(r);
        var tx=el("div","sub",d.dilution.text||""); tx.style.marginTop="8px"; box.appendChild(tx)}
    }else if(sub==="haber"){
      box.style.padding="0"; box.style.overflow="hidden";
      var items=d.news||[]; if(!items.length)box.appendChild(el("div","empty","Haber yok"));
      items.forEach(function(n){box.appendChild(newsItem(n))});
    }
    body.appendChild(box);
  }
  $("sub").addEventListener("click",function(e){
    var s=e.target.getAttribute&&e.target.getAttribute("data-s"); if(!s)return; sub=s; renderAnaliz();
  });

  /* ---------- başlat ---------- */
  function loadRaw(u){return fetch(u+"?t="+Date.now(),{cache:"no-store"}).then(function(r){return r.ok?r.json():null}).catch(function(){return null})}
  /* Performans kartı. perfFromRows (BIST): toplam/maliyet renderPortfolio satırlarından; ABD: kendisi hesaplar (kotasyon yoksa maliyet fiyatı). */
  function renderPerf(rows,total,cost){
    if(!window.PerfView||!P||!H)return;
    if(!CFG.perfFromRows){
      var q=(Q&&Q.quotes)||{}, v=0, c=0;
      Object.keys(P.portfolio||{}).forEach(function(t){var p=P.portfolio[t],px=+(q[t]&&q[t].c)||p.cost_basis;v+=p.shares*px;c+=p.shares*p.cost_basis});
      total=v+(+P.cash||0); cost=c;
    }
    try{PerfView.render($("perfBox"),{H:H,P:P,Q:Q,hide:hide,total:total,cost:cost,cur:CFG.cur,
      today:new Date().toLocaleDateString("en-CA",{timeZone:MKT.tz})})}
    catch(e){$("perfBox").textContent="Performans hatası: "+e.message}
  }
  function renderSector(){
    if(PEND.m)return;
    if(!window.SectorView)return;
    var ctx={M:M,N:NOTES,P:P,Q:Q,hide:hide,bench:CFG.sector.bench,cur:CFG.cur,picksNote:CFG.sector.picksNote};
    try{SectorView.render($("sbody"),ctx);SectorView.strip($("riskStrip"),P,Q,M,hide,ctx)}
    catch(e){$("sbody").textContent="Sektör görünümü hatası: "+e.message}
  }
  function renderAll(){renderPortfolio();renderWatch();renderAnaliz();renderSector();if(!CFG.perfFromRows)renderPerf()}
  /* İsteğe bağlı dosyalar arka planda yüklenir: gelmeyen dosya sayfayı bozmaz, gelen dosya ilgili görünümü yeniler. */
  function bg(p,key,set){
    p.then(set,function(){}).catch(function(){}).then(function(){PEND[key]=false;try{renderAll()}catch(e){}});
  }
  Promise.all([load("portfolio.json"),load("quotes.json")]).then(function(r){
    P=r[0];Q=r[1];
    if(Q&&Q.quotes)Object.keys(Q.quotes).forEach(function(t){Q.quotes[t]=eff(Q.quotes[t])});
    renderAll();
    showTab((location.hash||"").replace("#",""));
    setInterval(renderStatus,60000);
    bg(load("history.json",true),"h",function(j){H=j});
    bg(loadRaw(CFG.urls.market),"m",function(j){M=j});
    bg(load("analysis.json",true),"a",function(j){A=j});
    bg(loadRaw(CFG.urls.intra),"i",function(j){INTRA=j});
    bg(loadRaw(CFG.urls.bars),"b",function(j){BARS=j});
    if(CFG.urls.trend)bg(loadRaw(CFG.urls.trend),"t",function(j){TRENDD=j});
    bg(load("sector_notes.json",true),"n",function(j){NOTES=j});
  }).catch(function(e){
    $("pnl").textContent="veri alınamadı";
    $("msg").appendChild(el("div","err","Veri okunamadı: "+e.message));
  });
})();
