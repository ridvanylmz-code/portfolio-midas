/* "Bugün" ana ekranı: iki portföy, piyasa durumu, defter ve seçim kaydı tek sayfada. ES5; DOM textContent ile kurulur,
   veriyle innerHTML kullanılmaz. Her dosya bağımsız yüklenir: gelmeyen dosya yalnız kendi bölümünü düşürür.
   Şifreli dosyalar yalnız window.Vault.open ile açılır (düz JSON olduğu gibi geçer). */
(function(){
  "use strict";
  /* Piyasa ayarları ve market.json adresleri tg.html / bist/tg.html içindeki APP_CFG ile AYNI kalmalı. */
  var RAW="https://raw.githubusercontent.com/ridvanylmz-code/portfolio-midas/";
  var MK=[
    {k:"us",name:"ABD",cur:"$",dir:"",tz:"America/New_York",from:570,to:960,market:RAW+"market-data/market.json"},
    {k:"bist",name:"BIST",cur:"₺",dir:"bist/",tz:"Europe/Istanbul",from:600,to:1090,market:RAW+"market-bist-data/market-bist.json"}
  ];
  var S={us:{},bist:{}};   /* S[k].P/Q/M: undefined = bekliyor, null = alınamadı */
  var DEFTER, PICKS;       /* aynı: undefined bekliyor, null alınamadı */
  var ACC=[["midas_tr","Midas-TR","TRY"],["info_tr","Info-TR","TRY"],["midas_usd","Midas-USD","USD"],["ibkr","IBKR","USD"]];
  var GRP={tl:{name:"TL TOPLAM",accs:["midas_tr","info_tr"],cur:"TRY"},usd:{name:"USD TOPLAM",accs:["midas_usd","ibkr"],cur:"USD"}};

  var $=function(id){return document.getElementById(id)};
  function el(tag,c,t){var e=document.createElement(tag);if(c)e.className=c;if(t!==undefined)e.textContent=t;return e}
  function num(n,d){return n.toLocaleString("tr-TR",{minimumFractionDigits:d,maximumFractionDigits:d})}
  function sgn(n){return n>=0?"+":"−"}
  function pc(n,d){return "%"+sgn(n)+num(Math.abs(n),d===undefined?1:d)}
  function cls(n){return n>0?"up":n<0?"dn":""}
  function pad2(n){return (n<10?"0":"")+n}
  function fmtT(ms){var o={};  /* İstanbul saati: gg.aa ss:dd (app.js fmtT ile aynı) */
    new Intl.DateTimeFormat("tr-TR",{timeZone:"Europe/Istanbul",hourCycle:"h23",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}).formatToParts(new Date(ms)).forEach(function(p){o[p.type]=p.value});
    return o.day+"."+o.month+" "+o.hour+":"+o.minute}
  function trDate(ds){var p=ds.split("-");return p[2]+"."+p[1]+"."+p[0]}

  /* tutar gizleme: app.js ile aynı tercih (pm_hide); tutarlar *****, yüzdeler ve fiyatlar açık kalır */
  var hide=false;
  try{hide=localStorage.getItem("pm_hide")==="1"}catch(e){}
  document.body.classList.toggle("hide",hide);
  function mk(s){return hide?"*****":s}
  $("eye").addEventListener("click",function(){
    hide=!hide; document.body.classList.toggle("hide",hide);
    try{localStorage.setItem("pm_hide",hide?"1":"0")}catch(e){}
    render();
  });

  function load(url,vault){
    return fetch(url+(url.indexOf("?")<0?"?":"&")+"t="+Date.now(),{cache:"no-store"}).then(function(r){
      if(!r.ok)throw new Error(url+" "+r.status);return r.json()}).then(function(j){
      return vault&&window.Vault?Vault.open(j):j}).catch(function(){return null});
  }

  /* ---------- piyasa saati ve veri yaşı (app.js marketOpenNow / renderStatus ile aynı mantık) ---------- */
  function marketOpen(m){
    try{
      var o={}; new Intl.DateTimeFormat("en-US",{timeZone:m.tz,weekday:"short",hour:"2-digit",minute:"2-digit",hourCycle:"h23"})
        .formatToParts(new Date()).forEach(function(p){o[p.type]=p.value});
      if(o.weekday==="Sat"||o.weekday==="Sun")return false;
      var mn=(+o.hour)*60+(+o.minute); return mn>=m.from&&mn<m.to;
    }catch(e){var q=S[m.k].Q;return !!(q&&q.market_open)}
  }
  function ageTxt(ms){var mn=Math.floor(ms/6e4);return mn<60?mn+" dk":Math.floor(mn/60)+" sa "+(mn%60)+" dk"}
  function today(m){return new Date().toLocaleDateString("en-CA",{timeZone:m.tz})}

  /* ---------- seviyeler (scripts/common.py levels_for / zone_of ile aynı kural) ---------- */
  function levels(P,t){
    var pos=P.portfolio[t], c=(P.position_levels||{})[t]||{}, a=P.alerts||{}, s=c.stop_loss, g=c.target;
    if(s==null&&a.stop_loss_pct!=null)s=pos.cost_basis*(1+a.stop_loss_pct/100);
    if(g==null&&a.target_pct!=null)g=pos.cost_basis*(1+a.target_pct/100);
    return {stop:s==null?null:+s,target:g==null?null:+g};
  }
  function zone(P,t){
    var z=(P.buy_zones||{})[t], o={};
    if(z==null)return o;
    if(typeof z==="number")return {below:z};
    if(z.below!=null)o.below=+z.below;
    if(z.above!=null)o.above=+z.above;
    return o;
  }
  function price(m,t){var x=S[m.k].Q&&S[m.k].Q.quotes&&S[m.k].Q.quotes[t];return x&&+x.c>0?+x.c:null}

  /* ---------- yapılacaklar ---------- */
  var KINDS=[["stop","Stop kırıldı","dn"],["near","Stopa yakın","warn"],["target","Hedefte","up"],["buy","Alım bölgesinde","up"],["break","Kırılım","up"],["earn","Bilanço","warn"]];
  function actions(){
    var by={}, any=false;
    KINDS.forEach(function(k){by[k[0]]=[]});
    MK.forEach(function(m){
      var P=S[m.k].P, M=S[m.k].M; if(!P||!S[m.k].Q)return; any=true;
      var pf=P.portfolio||{}, held=Object.keys(pf).filter(function(t){return +pf[t].shares>0});
      var watch=[]; (P.watchlist||[]).concat(Object.keys(P.buy_zones||{})).forEach(function(t){if(watch.indexOf(t)<0)watch.push(t)});
      function add(kind,t,px,lvl,lab){by[kind].push({m:m,t:t,px:px,lvl:lvl,lab:lab})}
      held.forEach(function(t){
        var px=price(m,t), lv=levels(P,t); if(px===null)return;
        if(lv.stop!==null&&px<=lv.stop)add("stop",t,px,lv.stop,"Stop");
        else if(lv.stop!==null&&px<=lv.stop*1.03)add("near",t,px,lv.stop,"Stop");
        if(lv.target!==null&&px>=lv.target)add("target",t,px,lv.target,"Hedef");
      });
      watch.forEach(function(t){
        var px=price(m,t), z=zone(P,t); if(px===null)return;
        if(z.below!==undefined&&px<=z.below)add("buy",t,px,z.below,"Bölge");
        if(z.above!==undefined&&px>=z.above)add("break",t,px,z.above,"Kırılım");
      });
      var st=(M&&M.stocks)||{};
      held.concat(watch.filter(function(t){return held.indexOf(t)<0})).forEach(function(t){
        var d=st[t]&&st[t].earn_next; if(!d)return;
        var days=Math.round((Date.parse(d+"T12:00:00Z")-Date.parse(today(m)+"T12:00:00Z"))/864e5);
        if(days>=0&&days<=3)add("earn",t,price(m,t),null,days===0?"bugün":days+" gün sonra");
      });
    });
    return any?by:null;
  }

  /* ---------- bölümler ---------- */
  function section(title,id,badge){
    var h=el("div","sec",title); h.id=id;
    if(badge!==undefined)h.appendChild(el("span","badge",badge));
    $("app").appendChild(h);
  }
  function box(h){var b=el("div","box"); if(h)b.appendChild(el("h3","",h)); return b}
  function kv(b,k,v,c){var r=el("div","kv"); r.appendChild(el("span","",k)); r.appendChild(el("span",c||"",v)); b.appendChild(r); return r}

  function renderStatus(){
    var rows=MK.filter(function(m){return S[m.k].Q!==undefined}); if(!rows.length)return;
    section("Veri durumu","s-durum");
    var cols=el("div","cols");
    rows.forEach(function(m){
      var Q=S[m.k].Q, b=box(m.name), open=marketOpen(m);
      if(!Q){kv(b,"Fiyatlar","alınamadı","stale"); cols.appendChild(b); return}
      var upd=Q.updated?new Date(Q.updated):null, age=upd&&!isNaN(upd.getTime())?Date.now()-upd.getTime():null;
      var stale=age!==null&&(open?age>45*6e4:age>24*36e5);
      kv(b,"Piyasa",open?"Açık":"Kapalı");
      kv(b,"Son güncelleme",upd&&age!==null?fmtT(upd.getTime())+" · "+ageTxt(age)+" önce":"–",stale?"stale":"");
      cols.appendChild(b);
    });
    $("app").appendChild(cols);
  }

  function renderActions(){
    var by=actions(); if(!by)return;
    var n=0; KINDS.forEach(function(k){n+=by[k[0]].length});
    section("Yapılacaklar","s-yap",String(n));
    if(!n){$("app").appendChild(el("div","mut","Bugün yapılacak bir şey yok")); return}
    KINDS.forEach(function(k){by[k[0]].forEach(function(r){
      var row=el("div","act"+(k[0]==="stop"?" dn":"")), l=el("div","l"), rr=el("div","r");
      var tk=el("div","tk",r.t); l.appendChild(tk);
      var tl=el("div","sub"); tl.appendChild(el("span","chipx "+k[2],k[1])); tl.appendChild(el("span","chipx",r.m.name)); l.appendChild(tl);
      if(r.lvl===null){
        rr.appendChild(el("div","tk",r.px===null?"–":r.m.cur+num(r.px,2)));
        rr.appendChild(el("div","sub","Bilanço "+r.lab));
      }else{
        rr.appendChild(el("div","tk",r.m.cur+num(r.px,2)));
        rr.appendChild(el("div","sub "+k[2],r.lab+" "+r.m.cur+num(r.lvl,2)+" · "+pc((r.px/r.lvl-1)*100)));
      }
      row.appendChild(l); row.appendChild(rr); $("app").appendChild(row);
    })});
  }

  function renderRegime(){
    var ms=MK.filter(function(m){var s=S[m.k];return s.P&&s.M&&s.M.regime&&window.SectorView}); if(!ms.length)return;
    section("Rejim ve nakit","s-rejim");
    var cols=el("div","cols");
    ms.forEach(function(m){
      var s=S[m.k], r=s.M.regime, lo=r.cash_target[0], hi=r.cash_target[1], b=SectorView.book(s.P,s.Q,s.M);
      var bx=box(m.name), pos=b.cashPct<lo?["bandın altında","dn"]:b.cashPct>hi?["bandın üstünde","warn"]:["bandın içinde","up"];
      kv(bx,"Rejim",r.label+(r.borderline?" (sınırda)":""));
      kv(bx,"Puan",r.score+"/"+r.max);
      kv(bx,"Hedef nakit","%"+lo+"–"+hi);
      kv(bx,"Nakit","%"+num(b.cashPct,1)+" · "+mk(m.cur+num(b.cash,0)));
      kv(bx,"Durum",pos[0],pos[1]);
      cols.appendChild(bx);
    });
    $("app").appendChild(cols);
  }

  /* Defter: son gün değerleri. Grup toplamı için taşıma kuralı docs/defter/index.html build() ile BİREBİR AYNI kalmalı
     (o gün kaydı olmayan hesap son bilinen değeriyle toplanır; değişim/yüzde yalnız gerçek kayıtlardan). Sayfa kendi
     global D'sine bağlı olduğu için burada yalnız gereken kısım kopyalandı (grafik/endeks/kur hesapları yok). */
  function ledger(D){
    var prev={}, last={}, rows=[];
    (D.days||[]).forEach(function(x){
      var r={d:x.d,a:{}};
      Object.keys(x.a||{}).forEach(function(k){
        var st=(D.accounts[k]||{}).start; if(st&&x.d<st)return;
        var e=x.a[k], p=prev[k];
        var pct=(p&&p.v&&e.c!=null)?e.c/p.v:null;
        var A0=D.accounts[k]||{}, R0=A0.cur==="TRY"?(e.r!=null?e.r:(e.s==="x"?0:(A0.reserve||0))):0;
        r.a[k]={v:e.v,c:e.c,pct:pct,pv:p?p.v:null,tot:(A0.cur==="TRY"&&e.s==="x"&&e.h)?e.h:e.v+R0};
        prev[k]=e;
      });
      Object.keys(GRP).forEach(function(g){
        var accs=GRP[g].accs, es=accs.map(function(a){return r.a[a]}).filter(Boolean); if(!es.length)return;
        var ok=es.filter(function(e){return e.pct!=null}), nu=0, de=0;
        ok.forEach(function(e){nu+=e.c;de+=e.pv});
        var v=0, tot=0, carry=[];
        accs.forEach(function(a){var e=r.a[a];if(e){v+=e.v;tot+=e.tot}else if(last[a]){v+=last[a].e.v;tot+=last[a].e.tot;carry.push(a)}});
        r[g]={v:v,tot:tot,c:ok.length?nu:null,pct:de?nu/de:null,carry:carry};
      });
      Object.keys(r.a).forEach(function(k){last[k]={d:x.d,e:r.a[k]}});
      rows.push(r);
    });
    return rows;
  }
  function accName(k){for(var i=0;i<ACC.length;i++)if(ACC[i][0]===k)return ACC[i][1];return k}
  function money(v,cur){return (cur==="USD"?"$":"₺")+num(v,0)}
  function chg(c,pct,cur){
    if(c==null)return ["–",""];
    return [(c>0?"▲ ":c<0?"▼ ":"■ ")+sgn(c)+mk(money(Math.abs(c),cur))+(pct==null?"":" · "+pc(pct*100,2)),cls(c)];
  }
  function renderLedger(){
    if(!DEFTER||!DEFTER.days||!DEFTER.days.length)return;
    var rows=ledger(DEFTER), lastRow=rows[rows.length-1];
    section("Hesaplar","s-hesap",trDate(lastRow.d));
    var cols=el("div","cols");
    Object.keys(GRP).forEach(function(g){
      var r=null; for(var i=rows.length-1;i>=0;i--)if(rows[i][g]){r=rows[i];break}
      if(!r)return;
      var G=GRP[g], e=r[g], bx=box(G.name+" · "+trDate(r.d)), c=chg(e.c,e.pct,G.cur);
      kv(bx,"Toplam",mk(money(e.v,G.cur)));
      kv(bx,"Günlük değişim",c[0],c[1]);
      G.accs.forEach(function(a){
        var x=null,xd=null; for(var j=rows.length-1;j>=0;j--)if(rows[j].a[a]){x=rows[j].a[a];xd=rows[j].d;break}
        if(!x)return;
        var cc=chg(x.c,x.pct,G.cur);
        kv(bx,accName(a)+(xd!==lastRow.d?" ⚠ "+trDate(xd).slice(0,5):""),mk(money(x.v,G.cur))+" · "+cc[0],cc[1]);
      });
      if(e.carry.length)bx.appendChild(el("div","sub warn","⚠ "+e.carry.map(accName).join(", ")+": bu gün girilmedi, son değer toplama taşındı"));
      cols.appendChild(bx);
    });
    $("app").appendChild(cols);
    var a=el("a","sub","Ayrıntı: Defter →"); a.href="defter/index.html"; a.style.display="inline-block"; a.style.margin="6px 4px 0"; $("app").appendChild(a);
  }

  function renderPicks(){
    if(!PICKS)return;
    var list=PICKS.picks||[];
    section("Seçim başarısı","s-secim");
    if(!list.length){$("app").appendChild(el("div","mut","Henüz kayıt yok")); return}
    var Q=S.us.Q&&S.us.Q.quotes||{}, closed=[], open=[];
    list.forEach(function(p){
      if(!(+p.in_price>0))return;
      if(p.out_date&&+p.out_price>0)closed.push({t:p.ticker,r:(+p.out_price/+p.in_price-1)*100});
      else if(!p.out_date)open.push({t:p.ticker,r:Q[p.ticker]&&+Q[p.ticker].c>0?(+Q[p.ticker].c/+p.in_price-1)*100:null});
    });
    var b=box();
    if(closed.length){
      var wins=closed.filter(function(x){return x.r>0}).length, avg=closed.reduce(function(s,x){return s+x.r},0)/closed.length;
      kv(b,"Kapanan seçim",String(closed.length));
      kv(b,"İsabet oranı","%"+num(wins/closed.length*100,0)+" ("+wins+"/"+closed.length+")");
      kv(b,"Ortalama getiri",pc(avg),cls(avg));
    }else kv(b,"Kapanan seçim","0");
    open.forEach(function(x){kv(b,x.t+" (açık)",x.r===null?"–":pc(x.r),x.r===null?"":cls(x.r))});
    $("app").appendChild(b);
  }

  function render(){
    var app=$("app"); app.textContent="";
    var d=new Date(); $("today").textContent=d.toLocaleDateString("tr-TR",{timeZone:"Europe/Istanbul",weekday:"long",day:"numeric",month:"long"});
    renderStatus(); renderActions(); renderRegime(); renderLedger(); renderPicks();
    var pend=DEFTER===undefined||PICKS===undefined||MK.some(function(m){var s=S[m.k];return s.P===undefined||s.Q===undefined||s.M===undefined});
    var msg=$("msg"); msg.textContent=pend?"Yükleniyor…":(app.children.length?"":"Hiçbir veri alınamadı.");
    msg.style.display=msg.textContent?"":"none";
  }

  MK.forEach(function(m){
    var s=S[m.k];
    load(m.dir+"data/portfolio.json",true).then(function(j){s.P=j;render()});
    load(m.dir+"data/quotes.json").then(function(j){s.Q=j;render()});
    load(m.market).then(function(j){s.M=j;render()});
  });
  load("defter/data/defter.json",true).then(function(j){DEFTER=j;render()});
  load("data/picks_log.json").then(function(j){PICKS=j;render()});
  render();
  setInterval(render,60000);
})();
