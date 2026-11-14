#!/usr/bin/env python3
"""Haftalık teknik analiz — tek çalıştırıcı (yöntem v2.4).

Kurulum:  git clone https://github.com/ridvanylmz-code/portfolio-midas.git && cd portfolio-midas
          pip install pandas numpy --break-system-packages   (gerekirse)

Akış (ayrıntı: teknik/OTURUM.md):
  1) python3 teknik/haftalik.py veri  [--klasor <araç sonucu klasörü>]
       MCP get-ohlcv çıktılarını (dosyaya düşen .txt) bulur, sembol/aralığı kendisi tanır → teknik/is/data/
  2) python3 teknik/haftalik.py puan --pazar abd
       Geçen analizin bölgelerini puan.py ile puanlar (şans 500 tekrar) → kısa özet + is/puan_ozet_<pazar>.txt
  3) python3 teknik/haftalik.py analiz --pazar abd --cfg teknik/cfg/abd_YYYYMMDD.py --tarih YYYY-MM-DD
       ind/struct/run (BIST: indb/runb) → kısa özet + is/plan_<pazar>_<tarih>.json (otomatik öneri: bölgeler,
       B/A tetik ve hedefleri, salınım emirleri, sigorta, çekirdek stop, alarmlar). Claude yalnız planı düzeltir
       (gerçek durum, adet, notlar, geçen haftanın sonuçları).
  4) python3 teknik/haftalik.py yayinla --plan teknik/is/plan_<pazar>_<tarih>.json
       bolgeler.csv / cizgiler.csv / Pine kodu / pano JSON'ları / repo panosu (docs/teknik/data) / haftalık defter
       bölümü / alarm listesi üretir. Claude: git commit+push, update-pine-script, alarmlar, project_write (local_path).
  Yardımcı: python3 teknik/haftalik.py pozisyon --pazar abd --since YYYY-MM-DD   (gh ile iş akışı günlükleri → adetler)
            python3 teknik/haftalik.py alarm-sil --liste <list-alerts çıktısı> --pazar abd   (eski Claude alarm ID'leri)
"""
import argparse, glob, json, os, pickle, re, shutil, subprocess, sys, datetime as dt

KOK = os.path.dirname(os.path.abspath(__file__))
KOD = os.path.join(KOK, 'kod'); VERI = os.path.join(KOK, 'veri'); IS = os.path.join(KOK, 'is')
REPO = os.path.dirname(KOK); DOCS = os.path.join(REPO, 'docs', 'teknik', 'data')
DATA = os.path.join(IS, 'data') + '/'
os.environ['TA_DATA'] = DATA
sys.path[:0] = [IS, KOD]

PAZAR = {
    'abd': dict(hisseler=['RKLB', 'CRWV', 'SGML', 'WYFI'], endeks='SPY', para='USD', exch='NASDAQ',
                ek=['SPY', 'UFO', 'SMH', 'LIT', 'WGMI'], ind='ind.py', struct='struct_.py', run='run.py',
                cfg='cfg.py', indjson='ind.json', res='res.pkl'),
    'bist': dict(hisseler=['BIENY', 'SASA', 'SMRTG', 'MIATK'], endeks='XU100', para='TRY', exch='BIST',
                 ek=['XU100', 'XTAST', 'XKMYA', 'XUSIN', 'XBLSM'], ind='indb.py', struct=None, run='runb.py',
                 cfg='cfgb.py', indjson='indb.json', res='resb.pkl'),
}
BIST = set(PAZAR['bist']['hisseler'])


def tr(x, nd=2):
    """Türkçe sayı: 61.53 → '61,53'; 10'un altında 3 haneye kadar."""
    if x is None: return '—'
    if abs(x) < 10: s = ('%.3f' % x).rstrip('0')
    else: s = '%.*f' % (nd, x)
    s = s.rstrip('.')
    if '.' in s and len(s.split('.')[1]) == 1: s += '0'
    return s.replace('.', ',')


def kos(cmd, log):
    env = dict(os.environ, PYTHONPATH=IS + ':' + KOD, TA_DATA=DATA)
    with open(log, 'w') as f:
        r = subprocess.run([sys.executable] + cmd, cwd=IS, env=env, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        print(open(log).read()[-3000:]); sys.exit(f'HATA: {" ".join(cmd)} (log: {log})')


# ---------------------------------------------------------------- veri
def cmd_veri(a):
    os.makedirs(DATA, exist_ok=True)
    import veri as V
    kl = a.klasor or max(glob.glob('/root/.claude/projects/*/*/tool-results') + glob.glob('/tmp/claude-tool-results'),
                         key=os.path.getmtime, default=None)
    if not kl: sys.exit('Araç sonucu klasörü bulunamadı: --klasor ver')
    dosyalar = sorted(glob.glob(os.path.join(kl, '*ohlcv*')), key=os.path.getmtime)
    gor = {}
    for f in dosyalar:
        try:
            t = json.loads(open(f).read()); t = json.loads(t[0]['text']) if isinstance(t, list) else t
            ex, sym = t['symbol'].split(':'); iv = t['interval']
        except Exception as e:
            print('atlandı', os.path.basename(f), e); continue
        gor[(sym, iv)] = (f, 'bist' if ex.startswith('BIST') else 'abd')   # aynı sembolde en yeni dosya kalır
    import io, contextlib
    for (sym, iv), (f, pz) in sorted(gor.items()):
        with contextlib.redirect_stdout(io.StringIO()):
            V.main(f, sym, iv, pz)
    from lib import load
    syms = sorted({s for s, _ in gor})
    for s in syms:
        try:
            d = load(s)
        except Exception:
            continue
        d.reset_index().rename(columns={'date': 'd'})[['d', 'o', 'h', 'l', 'c', 'v']].to_csv(DATA + f'{s}.csv', index=False)
        print(f'{s:6} {len(d):5} gün  son {d.index[-1].date()}  kapanış {d.c.iloc[-1]:.2f}  ({", ".join(i for x, i in gor if x == s)})')


# ---------------------------------------------------------------- puan
def cmd_puan(a):
    import pandas as pd
    H = PAZAR[a.pazar]['hisseler']
    B = pd.read_csv(os.path.join(VERI, 'bolgeler.csv')); B = B[B.hisse.isin(H)]
    an = a.analiz or B.analiz.max()
    if a.analiz != 'hepsi': B = B[B.analiz == an]
    P = pd.read_csv(os.path.join(VERI, 'pencereler.csv')); P = P[P.hisse.isin(H) & ((P.analiz == an) | (a.analiz == 'hepsi'))]
    os.makedirs(IS, exist_ok=True)
    B.to_csv(os.path.join(IS, '_b.csv'), index=False); P.to_csv(os.path.join(IS, '_p.csv'), index=False)
    log = os.path.join(IS, f'puan_{a.pazar}.log')
    kos([os.path.join(KOD, 'puan.py'), '_b.csv', '_p.csv', DATA, '--n', str(a.n)], log)
    t = open(log).read()
    satir = [l for l in t.splitlines() if re.search(r'(✓|✗|½|dokunmadi|bekliyor)$', l.strip())]
    ozet = t[t.find('ÖZET'):]
    kisa = [re.sub(r'\s+', ' ', l.strip()) for l in satir]
    out = f'Puanlanan analiz: {an} ({a.pazar})\n' + '\n'.join(kisa) + '\n' + ozet
    open(os.path.join(IS, f'puan_ozet_{a.pazar}.txt'), 'w').write(out); print(out)
    if a.analiz != 'hepsi' and not a.yalniz_son:   # birikimli karne (tüm analizler) → teknik/veri/karne_<pazar>.txt
        Bh = pd.read_csv(os.path.join(VERI, 'bolgeler.csv')); Bh = Bh[Bh.hisse.isin(H)]
        Bh.to_csv(os.path.join(IS, '_b.csv'), index=False); P.iloc[0:0].to_csv(os.path.join(IS, '_p.csv'), index=False)
        kos([os.path.join(KOD, 'puan.py'), '_b.csv', '_p.csv', DATA, '--n', str(min(a.n, 200))], log + '.hepsi')
        t2 = open(log + '.hepsi').read(); oz2 = t2[t2.find('ÖZET'):].split('Zaman penceresi')[0].strip()
        kar = (f'# Karne — {a.pazar.upper()} (puan.py, {dt.date.today()})\n\nSon analiz ({an}):\n' + ozet.split('Zaman penceresi')[0].strip()
               + f'\n\nBirikimli ({Bh.analiz.min()} – {Bh.analiz.max()}, şans 200 tekrar):\n' + oz2 + '\n')
        open(os.path.join(VERI, f'karne_{a.pazar}.txt'), 'w').write(kar); print('\n' + kar)


# ---------------------------------------------------------------- analiz + öneri
def oneri(s, R, I, d):
    """Salınım kurallarından otomatik öneri (yöntem 10). Claude adet ve istisnaları düzeltir."""
    c, A, mod = R['c'], R['A'], I['mode']
    nd = 3 if c < 2 else 2
    for z in R['Z']: z['lo'], z['hi'] = round(z['lo'], nd), round(z['hi'], nd)
    Z = [z for z in R['Z'] if abs((z['lo'] + z['hi']) / 2 - c) <= 4 * A]
    Z.sort(key=lambda z: abs((z['lo'] + z['hi']) / 2 - c))
    ana, uzak = Z[:5], Z[5:]
    g = lambda z: {'izleme': 'İzleme'}.get(z['grade_adj'], z['grade_adj'])
    rol = lambda z: 'direnç' if z['role'] == 'direnç' else ('destek' if z['role'] == 'destek' else 'pivot')
    bol = [dict(alt=round(z['lo'], 3), ust=round(z['hi'], 3), guc=g(z), puan=z['score'], rol=rol(z),
                dusuruldu=z['grade'] != z['grade_adj'], not_=z['comp'][:160]) for z in sorted(ana, key=lambda z: -z['lo'])]
    dir_ = sorted([z for z in Z if z['role'] == 'direnç'], key=lambda z: z['lo'])
    sup = sorted([z for z in Z if z['role'] == 'destek'], key=lambda z: -z['hi'])
    piv = [z for z in Z if z['role'] not in ('direnç', 'destek')]
    a3h, a3l = float(d.h.iloc[-3:].max()), float(d.l.iloc[-3:].min())
    E = []
    sig = None
    if dir_:
        z1 = dir_[0]
        E += [dict(tip='sat', emir='1 porsiyon sat', fiyat=round(z1['lo'], 2), kaynak=f"{g(z1)} {tr(z1['lo'])}–{tr(z1['hi'])} alt",
                   kosul='1s RSI 70 / CCI +100 aşağı teyidi'),
              dict(tip='sat', emir='1 porsiyon daha sat', fiyat=round((z1['lo'] + z1['hi']) / 2, 2),
                   kaynak=f"{g(z1)} {tr(z1['lo'])}–{tr(z1['hi'])} ortası", kosul='Bölge ortası')]
        sig, kay = z1['hi'] + 0.15 * A, f"{tr(z1['hi'])} + 0,15 ATR"
        ust = [z for z in dir_ if z['grade'] == 'KRİTİK' and z['lo'] > z1['hi'] and z['lo'] - sig <= 1.5 * A]
        if ust:   # 1,5 ATR içinde KRİTİK direnç → sigorta onun üstüne (bir kez; yeni sigorta yine bir KRİTİK bölgenin içine düşerse bir kez daha)
            z1 = ust[0]; sig, kay = z1['hi'] + 0.15 * A, f"{tr(z1['hi'])} + 0,15 ATR (üstteki KRİTİK direnç)"
            ic = [z for z in dir_ if z['grade'] == 'KRİTİK' and z['lo'] <= sig <= z['hi']]
            if ic: z1 = ic[0]; sig, kay = z1['hi'] + 0.15 * A, f"{tr(z1['hi'])} + 0,15 ATR (üst üste KRİTİK direnç)"
        E.append(dict(tip='sigorta', emir='Sigorta', fiyat=round(sig, 2), kaynak=kay,
                      kosul='Kapanış üstündeyse satılan ticaret porsiyonlarının yarısını ertesi gün geri al'))
    # geri alım
    geri = None
    if mod == 'Savunma':
        k = [z for z in sup if z['grade_adj'] == 'KRİTİK'] + [z for z in piv if z['grade'] == 'KRİTİK']
        if k:
            z = k[0]; lo, hi = (z['lo'], (z['lo'] + z['hi']) / 2) if z in piv else (z['lo'], z['hi']); geri = (z, lo, hi, 'yarım')
    else:
        k = [z for z in sup if z['grade_adj'] in ('KRİTİK', 'ÖNEMLİ')]
        if k: z = k[0]; geri = (z, z['lo'], z['hi'], 'yarım; 4s ST yeşilse tamamla')
    if geri:
        z, lo, hi, boy = geri
        E.append(dict(tip='al', emir=f'Sattığını geri al ({boy.split(";")[0]})', fiyat=round(hi, 2), metin=f'{tr(lo)}–{tr(hi)}',
                      kaynak=f"{g(z)} {tr(z['lo'])}–{tr(z['hi'])}", kosul=f'Limit yok; bölgede 1s RSI 30 üstüne → {boy}. Yalnız satılmış porsiyon'))
    else:
        E.append(dict(tip='not', emir='Sattığını geri al', fiyat=None, metin='Yok', kaynak='', kosul=f'{mod}: KRİTİK destek yok'))
    # çekirdek stop
    kr = [z for z in sup + piv if z['grade'] == 'KRİTİK']
    if geri and geri[0] in kr:
        alt = [z for z in kr if z['hi'] < geri[0]['lo']]
        sz = max(alt, key=lambda z: z['hi']) if alt else geri[0]
    elif kr: sz = max(kr, key=lambda z: z['hi'])
    elif sup: sz = min(sup, key=lambda z: z['lo'])
    else: sz = None
    stop = round(sz['lo'] - 0.15 * A, 2) if sz else None
    # B / A
    bz = [z for z in sorted(sup + piv, key=lambda z: -z['hi']) if (z['lo'] + z['hi']) / 2 < a3l]
    az = [z for z in dir_ if z['lo'] > a3h]
    rng = lambda z: f"{tr(z['lo'])}–{tr(z['hi'])}" if z else '—'
    B = dict(tetik=round(a3l, 2), h1=rng(bz[0]) if bz else '—', h2=rng(bz[1]) if len(bz) > 1 else '—',
             alarm=round(bz[0]['hi'], 2) if bz else None)
    Aa = dict(tetik=round(a3h, 2), h1=rng(az[0]) if az else '—', h2=rng(az[1]) if len(az) > 1 else '—')
    if B['alarm']:
        E.append(dict(tip='uyari', emir='B hedefi 1 (uyarı)', fiyat=B['alarm'], metin=B['h1'], kaynak=B['h1'],
                      kosul=f"{tr(B['tetik'])} altı kapanış B tetiği; hedef 2 {B['h2']}"))
    if stop:
        E.append(dict(tip='stop', emir='1 porsiyon çekirdek sat (kapanış)', fiyat=stop, kaynak=f"{tr(sz['lo'])} − 0,15 ATR",
                      kosul='Günlük kapanış altındaysa ertesi gün; RSI ≤ 25 / z ≤ −2,5 ise bir kez ertele, 5 işlem günü son sınır'))
    E.append(dict(tip='not', emir='Kenardaki porsiyon', fiyat=None, metin='Kullanma' if mod == 'Savunma' else 'Bir alt KRİTİK destekte',
                  kaynak='', kosul=mod))
    for e in E:
        e.setdefault('metin', tr(e['fiyat']) if e['fiyat'] else '')
        e['adet'] = None
    al = []
    for e in E:
        if e['tip'] in ('sat', 'sigorta', 'al', 'uyari', 'stop') and e['fiyat']:
            if e['tip'] == 'sat' and e is not E[0]: continue          # yalnız ilk satış alarmı
            yon = 'cross_up' if e['tip'] in ('sat', 'sigorta') else 'cross_down'
            al.append(dict(fiyat=e['fiyat'], yon=yon, ad=f"{s} {tr(e['fiyat'])} — {e['emir']}", mesaj=f"{e['kaynak']}. {e['kosul']}"))
    E3 = I['E']
    bag = (f"{mod} · RSI {tr(I['rsi'],1)} · ADX {tr(I['adx'],1)} (+DI {tr(I['pdi'],1)} / −DI {tr(I['mdi'],1)}) · "
           f"EMA21 {tr(E3['21'])} / 34 {tr(E3['34'])} / 89 {tr(E3['89'])} / 144 {tr(E3['144'])} / 233 {tr(E3['233'])} · "
           f"MACDh {tr(I.get('hist',0),2)} · haftalık RSI {tr(I['w_rsi'],1)}, MACDh {tr(I['w_hist'],2)} · "
           f"RS {I['rs'].lower()} (21g %{tr(I['rs21'],1)}, 63g %{tr(I['rs63'],1)}) · z {tr(I['z'],2)}, {I['nev']} olay 10g %{tr(I['f10'] or 0,1)} · "
           f"4s ST {I['st_4h'][0]} {tr(I['st_4h'][1])} / günlük {I['st_d'][0]} {tr(I['st_d'][1])} · {I['nbars']} bar")
    return dict(kapanis=round(c, 3), atr=round(A, 4), mod=mod, bolgeler=bol,
                uzak=[f"{g(z)} {tr(z['lo'])}–{tr(z['hi'])}" for z in uzak], B=B, A=Aa,
                sigorta=round(sig, 2) if sig else None, stop=stop, emirler=E, alarmlar=al, baglam=bag,
                v1=' · '.join(f"{g_} {tr(x)}–{tr(y)}" for x, y, g_, *_ in R.get('v1', [])),
                gercek='', bilanco='', notlar='')


def cmd_analiz(a):
    P = PAZAR[a.pazar]; os.makedirs(IS, exist_ok=True)
    shutil.copy(a.cfg, os.path.join(IS, P['cfg']))
    if a.pazar == 'bist': shutil.copy(a.cfg, os.path.join(IS, 'cfg.py'))   # v1t içe aktarımı için
    os.environ['TA_TODAY'] = a.tarih
    kos([os.path.join(KOD, P['ind'])], os.path.join(IS, f"log_ind_{a.pazar}.txt"))
    if a.pazar == 'bist': shutil.copy(os.path.join(IS, 'indb.json'), os.path.join(IS, 'ind.json'))
    if P['struct']: kos([os.path.join(KOD, P['struct'])], os.path.join(IS, f"log_struct_{a.pazar}.txt"))
    kos([os.path.join(KOD, P['run'])], os.path.join(IS, f"log_run_{a.pazar}.txt"))
    IND = json.load(open(os.path.join(IS, P['indjson']))); RES = pickle.load(open(os.path.join(IS, P['res']), 'rb'))
    from lib import load, ema, adx
    e = load(P['endeks']); ec = e.c
    e89, e233 = ema(ec, 89).iloc[-1], ema(ec, 233).iloc[-1]
    rej = f"{P['endeks']} {tr(ec.iloc[-1])} · EMA89 {tr(e89)} · EMA233 {tr(e233)}"
    if a.pazar == 'bist':
        ax, pdi, mdi = adx(e); rej += f" · ADX {tr(ax.iloc[-1],1)} (+DI {tr(pdi.iloc[-1],1)} / −DI {tr(mdi.iloc[-1],1)})"
    ref = None; plan = dict(pazar=a.pazar, tarih=a.tarih, surum='v2.4', rejim=rej + ' → (Claude: risk-on / nötr / risk-off)',
                            hisseler={}, onceki_sonuclar={}, notlar='')
    print(rej)
    st = json.load(open(os.path.join(IS, 'struct.json'))) if P['struct'] else {}
    for s in P['hisseler']:
        d = load(s); ref = str(d.index[-1].date()); I = IND[s]
        I['E'] = {str(k): v for k, v in I['E'].items()}
        o = oneri(s, RES[s], I, d); plan['hisseler'][s] = o
        print(f"\n## {s} {tr(o['kapanis'])} · ATR {tr(o['atr'])} · {o['mod']} · RS {I['rs']} · son 3 gün {tr(o['A']['tetik'])} / {tr(o['B']['tetik'])}")
        for b in o['bolgeler']:
            print(f"  {b['guc']:7} {tr(b['alt'])}–{tr(b['ust'])} {b['rol']:7} {tr(b['puan'],1)}{' (düşürüldü)' if b['dusuruldu'] else ''} | {b['not_'][:110]}")
        if o['uzak']: print('  uzak:', ' · '.join(o['uzak']))
        print(f"  B: <{tr(o['B']['tetik'])} → {o['B']['h1']} / {o['B']['h2']}   A: >{tr(o['A']['tetik'])} → {o['A']['h1']} / {o['A']['h2']}")
        print('  emir:', ' | '.join(f"{x['tip']} {x['metin']}" for x in o['emirler'] if x['fiyat']))
        if s in st:
            g = st[s]; print('  boşluk:', [(x[0][:1], x[2], x[3]) for x in g['gaps']][-3:], '· hacim:', g['vp'][:3])
    plan['ref'] = ref
    yol = os.path.join(IS, f"plan_{a.pazar}_{a.tarih.replace('-', '')}.json")
    json.dump(plan, open(yol, 'w'), ensure_ascii=False, indent=1, default=float)
    print(f'\nPlan taslağı: {yol}  (gercek / adet / bilanco / notlar / onceki_sonuclar alanlarını doldur)')


# ---------------------------------------------------------------- yayinla
def cmd_yayinla(a):
    import pandas as pd
    p = json.load(open(a.plan)); pz = p['pazar']; T = p['tarih']; H = list(p['hisseler']); para = PAZAR[pz]['para']
    sym = lambda h: f"{PAZAR[pz]['exch']}:{h}"
    os.makedirs(IS, exist_ok=True); cikti = []
    # 1) bolgeler.csv + cizgiler.csv
    bf = os.path.join(VERI, 'bolgeler.csv'); B = pd.read_csv(bf)
    B = B[~((B.analiz == T) & B.hisse.isin(H))]
    yeni = [dict(analiz=T, ref=p['ref'], hisse=h, alt=b['alt'], ust=b['ust'], guc=b['guc']) for h in H for b in p['hisseler'][h]['bolgeler']]
    pd.concat([B, pd.DataFrame(yeni)]).to_csv(bf, index=False)
    cf = os.path.join(VERI, 'cizgiler.csv'); C = pd.read_csv(cf); C = C[~C.hisse.isin(H)]
    ek = [dict(hisse=h, fiyat=x, tur=t) for h in H for x, t in [(p['hisseler'][h]['sigorta'], 'SIG'), (p['hisseler'][h]['stop'], 'STP')] if x]
    pd.concat([pd.DataFrame(ek), C]).to_csv(cf, index=False)
    # 2) Pine
    import pine
    v, t = pine.veri(bf, cf); kod = pine.SABLON.replace('__VERI__', v).replace('__TARIH__', t)
    open(os.path.join(IS, 'bolgeler.pine'), 'w').write(kod); cikti.append('is/bolgeler.pine')
    # 3) seviyeler + tahminler (repo: teknik/veri)
    sf = os.path.join(VERI, 'pano_seviyeler.json'); S = [r for r in json.load(open(sf)) if not (r.get('hafta') == T and r['hisse'] in H)]
    for h in H:
        o = p['hisseler'][h]; rows = []
        for b in o['bolgeler']:
            tur = {'direnç': 'hedef', 'pivot': 'donus'}.get(b['rol'], 'destek')
            for lv, k in [(b['ust'], 'üst'), (b['alt'], 'alt')]:
                rows.append(dict(seviye=lv, etiket=f"Konfluens ({b['guc']}, {tr(b['puan'],1)}): {tr(b['alt'])}–{tr(b['ust'])} {k} — {b['rol']}",
                                 tur=tur, alt=b['alt'], ust=b['ust'], guc=b['guc']))
        if o['sigorta']: rows.append(dict(seviye=o['sigorta'], etiket=f"Sigorta (kapanış) {tr(o['sigorta'])}", tur='tetik'))
        rows.append(dict(seviye=o['A']['tetik'], etiket=f"A tetiği: {tr(o['A']['tetik'])} üstü kapanış → {o['A']['h1']}, sonra {o['A']['h2']}", tur='tetik'))
        rows.append(dict(seviye=o['B']['tetik'], etiket=f"B tetiği: {tr(o['B']['tetik'])} altı kapanış → {o['B']['h1']}, sonra {o['B']['h2']}", tur='asagi'))
        if o['stop']: rows.append(dict(seviye=o['stop'], etiket=f"Çekirdek stop (kapanış) {tr(o['stop'])}", tur='stop'))
        rows.sort(key=lambda r: -r['seviye'])
        for i, r in enumerate(rows, 1): S.append(dict(id=f"{h}-{T.replace('-','')}-{i:02d}", hisse=h, sembol=sym(h), sira=i, hafta=T, **r))
    json.dump(S, open(sf, 'w'), ensure_ascii=False, indent=1)
    tf = os.path.join(VERI, 'pano_tahminler.json'); TT = json.load(open(tf))
    for r in TT:
        if r['id'] in p.get('onceki_sonuclar', {}): r['sonuc'], r['isabet'] = p['onceki_sonuclar'][r['id']]
    TT = [r for r in TT if not (r.get('hafta') == T and r['hisse'] in H)]
    for h in H:
        o = p['hisseler'][h]
        don = ' · '.join(f"{b['guc']}{'↓' if b['dusuruldu'] else ''} {tr(b['alt'])}–{tr(b['ust'])} {b['rol']} ({tr(b['puan'],1)})" for b in o['bolgeler'])
        if o['uzak']: don += ' · uzak ' + ' / '.join(o['uzak'])
        TT.append(dict(id=f'{T}-{h}', hafta=T, surum=p['surum'], sembol=sym(h), hisse=h, para=para, analiz_fiyati=o['kapanis'],
                       ana_senaryo=f"B: {tr(o['B']['tetik'])} altı kapanış → {o['B']['h1']}, sonra {o['B']['h2']} / A: {tr(o['A']['tetik'])} üstü kapanış → {o['A']['h1']}, sonra {o['A']['h2']}",
                       olasilik='—', alt_senaryo=o.get('notlar', ''), donus_bolgesi=don, tetik=o['A']['tetik'], stop=o['stop'],
                       hedef1=f"B: {o['B']['h1']} / A: {o['A']['h1']}", hedef2=f"B: {o['B']['h2']} / A: {o['A']['h2']}",
                       zaman='—', momentum=f"{p['surum']} · {p['rejim']} · {o['baglam']}", sonuc='', isabet='—'))
    json.dump(TT, open(tf, 'w'), ensure_ascii=False, indent=1)
    # 4) salınım (adetli: artifact pano + Proje kopyası; adetsiz: repo)
    rows = []
    for h in H:
        o = p['hisseler'][h]; bil = o.get('bilanco', '')
        rows.append(dict(id=f'{h}-00', hisse=h, sira=0, mod=o['mod'], emir='Gerçek durum (repo)', tip='not', fiyat=None,
                         fiyat_metin=o.get('gercek', ''), kosul=o.get('gercek_kosul', ''), kaynak=o.get('gercek_kaynak', 'Repo'), hafta=T, bilanco=bil))
        for i, e in enumerate(o['emirler'], 1):
            em = e['emir'] + (f" ({e['adet']} adet)" if e.get('adet') else '')
            rows.append(dict(id=f'{h}-{i:02d}', hisse=h, sira=i, mod=o['mod'], emir=em, tip=e['tip'], fiyat=e['fiyat'],
                             fiyat_metin=e.get('metin') or tr(e['fiyat']), kosul=e['kosul'], kaynak=e['kaynak'], hafta=T, bilanco=bil))
    sys.argv = ['yayinla.py']; ns = {}
    src = open(os.path.join(KOD, 'yayinla.py')).read().split('rows = []')[0]
    exec(src.replace('src, data, out = sys.argv[1:4]', '').replace('S = json.load(open(src))', ''), ns)
    temiz = []
    for r in rows:
        if r['sira'] == 0: continue
        rr = {k: r.get(k) for k in ['id', 'hisse', 'sira', 'mod', 'fiyat', 'fiyat_metin', 'kaynak', 'hafta', 'bilanco']}
        rr['tip'] = ns['tip'](r); rr['emir'] = ns['temiz'](r['emir']) or r['emir']; rr['kosul'] = ns['temiz'](r['kosul']); temiz.append(rr)
    os.makedirs(DOCS, exist_ok=True)
    rs = os.path.join(DOCS, 'salinim.json'); mf = os.path.join(DOCS, 'meta.json')
    rep = [r for r in (json.load(open(rs)) if os.path.exists(rs) else []) if r['hisse'] not in H] + temiz
    rep.sort(key=lambda r: (r['hisse'] in BIST, r['hisse'], r['sira']))
    json.dump(rep, open(rs, 'w'), ensure_ascii=False, indent=1)
    meta = json.load(open(mf)) if os.path.exists(mf) else {'hisseler': {}}
    meta['guncelleme'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    for h in H:
        meta['hisseler'][h] = dict(pazar='bist' if h in BIST else 'us', atr=p['hisseler'][h]['atr'], atr_tarih=p['ref'], plan=T, mod=p['hisseler'][h]['mod'],
                                   bilanco=p['hisseler'][h].get('bilanco', ''))
    meta['hisseler'] = dict(sorted(meta['hisseler'].items()))
    json.dump(meta, open(mf, 'w'), ensure_ascii=False, indent=1); cikti.append('docs/teknik/data/salinim.json + meta.json')
    # 5) alarm listesi
    AL = [dict(x, sembol=sym(h), ad=x['ad'] + f" ({p['surum']} {T[8:10]}.{T[5:7]})") for h in H for x in p['hisseler'][h]['alarmlar']]
    json.dump(AL, open(os.path.join(IS, f'alarmlar_{pz}.json'), 'w'), ensure_ascii=False, indent=1); cikti.append(f'is/alarmlar_{pz}.json ({len(AL)} alarm)')
    af = os.path.join(VERI, 'alarmlar.json'); ALL = [x for x in (json.load(open(af)) if os.path.exists(af) else []) if x['sembol'].split(':')[1] not in H] + AL
    json.dump(ALL, open(af, 'w'), ensure_ascii=False, indent=1)
    dz = os.path.join(VERI, 'defter_dizin.json'); DZ = [x for x in (json.load(open(dz)) if os.path.exists(dz) else []) if not (x['tarih'] == T and x['pazar'] == pz)]
    DZ.append(dict(tarih=T, pazar=pz, surum=p['surum'], dosya=f"claude/defter/{T}_{pz}.md")); DZ.sort(key=lambda x: x['tarih'], reverse=True)
    json.dump(DZ, open(dz, 'w'), ensure_ascii=False, indent=1)
    # 6) haftalık defter bölümü
    po = os.path.join(IS, f'puan_ozet_{pz}.txt')
    md = [f"# Hafta {T} — {pz.upper()} (yöntem {p['surum']}; {p['ref']} kapanışı)\n", f"**Rejim:** {p['rejim']}\n"]
    if p.get('notlar'): md.append(p['notlar'] + '\n')
    if os.path.exists(po): md.append('**Karne (`puan.py`):**\n```\n' + open(po).read().strip() + '\n```\n')
    if p.get('onceki_sonuclar'):
        md.append('**Geçen haftanın senaryo sonuçları:**\n'); md += [f"- {k}: {v[0]} — **{v[1]}**" for k, v in p['onceki_sonuclar'].items()]; md.append('')
    md.append('| Hisse | Kapanış | B (önce) | A | Bölgeler | Sigorta | Çekirdek stop | Bağlam |\n|---|---|---|---|---|---|---|---|')
    for r in TT:
        if r['hafta'] == T and r['hisse'] in H:
            o = p['hisseler'][r['hisse']]
            md.append(f"| {r['hisse']} | {tr(o['kapanis'])} | {tr(o['B']['tetik'])} altı → {o['B']['h1']} / {o['B']['h2']} | {tr(o['A']['tetik'])} üstü → {o['A']['h1']} / {o['A']['h2']} | {r['donus_bolgesi']} | {tr(o['sigorta'])} | {tr(o['stop'])} | {o['baglam']} |")
    md.append('\n**v1 bölgeleri (kontrol):** ' + ' — '.join(f"{h} {p['hisseler'][h]['v1']}" for h in H) + '\n')
    md.append('## Salınım emirleri\n\n| Hisse | Mod | Emir | Tip | Fiyat | Koşul | Kaynak |\n|---|---|---|---|---|---|---|')
    md += [f"| {r['hisse']} | {r['mod']} | {r['emir']} | {r['tip']} | {r['fiyat_metin']} | {r['kosul']} | {r['kaynak']} |" for r in rows]
    yol = os.path.join(IS, f"defter_{pz}_{T.replace('-','')}.md"); open(yol, 'w').write('\n'.join(md) + '\n'); cikti.append(yol.replace(KOK + '/', '') + f'  → Proje claude/defter/{T}_{pz}.md')
    kisa_defter(p, rows, rep, meta, DZ); izleme(meta, ALL)
    cikti += ['is/tahmin_defteri.md  → Proje claude/tahmin_defteri.md', 'is/izleme_listesi.md  → Proje claude/izleme_listesi.md']
    print('Üretildi:\n  ' + '\n  '.join(cikti))
    print('Repo değişiklikleri: teknik/veri/{bolgeler.csv,cizgiler.csv,pano_seviyeler.json,pano_tahminler.json}, docs/teknik/data/')


HISSE_TABLO = [('BIENY', 'BIST', 'Yapı ürünleri (seramik)', 'BIST:XTAST'), ('RKLB', 'NASDAQ', 'Uzay / roket', 'NASDAQ:UFO'),
               ('CRWV', 'NASDAQ', 'Yapay zekâ bulut altyapısı', 'NASDAQ:SMH'), ('SGML', 'NASDAQ', 'Lityum madenciliği', 'AMEX:LIT'),
               ('SASA', 'BIST', 'Polyester / kimya', 'BIST:XKMYA'), ('SMRTG', 'BIST', 'Güneş enerjisi ekipmanı', 'BIST:XUSIN (zayıf vekil)'),
               ('MIATK', 'BIST', 'Yazılım / güvenlik', 'BIST:XBLSM'), ('WYFI', 'NASDAQ', 'Yapay zekâ veri merkezi (WhiteFiber)', 'NASDAQ:WGMI')]


def kisa_defter(p, rows, rep, meta, DZ):
    """claude/tahmin_defteri.md: dizin + son hafta (bu pazar adetli, diğer pazar repodan adetsiz) + karne. Her hafta baştan üretilir (kısa)."""
    T, pz = p['tarih'], p['pazar']
    md = [f"# Tahmin Defteri — kısa (otomatik, {T})\n",
          "`teknik/haftalik.py yayinla` her analizde bu dosyayı baştan üretir; elle düzenlenmez. Haftalık ayrıntı `claude/defter/<tarih>_<pazar>.md` dosyalarında (Proje), "
          "tablo verisi repoda (`teknik/veri/pano_tahminler.json`, `pano_seviyeler.json`, `docs/teknik/data/salinim.json`). 14.11.2026 öncesi: `claude/tahmin_defteri_arsiv.md`, `_arsiv_2.md`.\n",
          "## Dizin\n", "| Tarih | Pazar | Yöntem | Dosya |", "|---|---|---|---|"]
    md += [f"| {x['tarih']} | {x['pazar'].upper()} | {x['surum']} | `{x['dosya']}` |" for x in DZ[:12]]
    md += ['', f"## Güncel plan — {pz.upper()} ({T}, adetli)\n", f"**Rejim:** {p['rejim']}\n",
           '| Hisse | Kapanış | Mod | B (önce) | A | Sigorta | Çekirdek stop | Gerçek durum |', '|---|---|---|---|---|---|---|---|']
    for h, o in p['hisseler'].items():
        md.append(f"| {h} | {tr(o['kapanis'])} | {o['mod']} | {tr(o['B']['tetik'])} altı → {o['B']['h1']} / {o['B']['h2']} | {tr(o['A']['tetik'])} üstü → {o['A']['h1']} / {o['A']['h2']} | {tr(o['sigorta'])} | {tr(o['stop'])} | {o.get('gercek','')} |")
    md += ['', '| Hisse | Emir | Tip | Fiyat | Koşul |', '|---|---|---|---|---|']
    md += [f"| {r['hisse']} | {r['emir']} | {r['tip']} | {r['fiyat_metin']} | {r['kosul']} |" for r in rows if r['sira'] > 0 and r['fiyat'] is not None]
    diger = [r for r in rep if r['hisse'] not in p['hisseler']]
    if diger:
        md += ['', f"## Güncel plan — diğer pazar (repodan, adetsiz; plan tarihi {max(r['hafta'] for r in diger)})\n", '| Hisse | Emir | Tip | Fiyat | Koşul |', '|---|---|---|---|---|']
        md += [f"| {r['hisse']} | {r['emir']} | {r['tip']} | {r['fiyat_metin']} | {r['kosul']} |" for r in diger if r.get('fiyat') is not None]
    for k in ('abd', 'bist'):
        f = os.path.join(VERI, f'karne_{k}.txt')
        if os.path.exists(f): md += ['', '## ' + open(f).read().lstrip('# ').strip().replace('\n', '\n\n', 1)]
    open(os.path.join(IS, 'tahmin_defteri.md'), 'w').write('\n'.join(md) + '\n')


def izleme(meta, ALL):
    md = [f"# İzleme Listesi (otomatik, {meta['guncelleme'][:10]})\n",
          '`teknik/haftalik.py yayinla` her analizde baştan üretir. Pano: repo `docs/teknik/` (Telegram “📐 Teknik Plan”) ve artifact pano.\n',
          '## Hisseler\n', '| Hisse | Borsa | Sektör | Sektör ETF/endeksi | Mod | Plan | Bilanço |', '|---|---|---|---|---|---|---|']
    for h, b, sek, etf in HISSE_TABLO:
        m = meta['hisseler'].get(h, {})
        md.append(f"| {h} | {b} | {sek} | {etf} | {m.get('mod','')} | {m.get('plan','')} | {m.get('bilanco','') or '—'} |")
    md += ['', 'Endeksler: ABD `AMEX:SPY` + `CBOE:VIX`; BIST `BIST:XU100`. Sektör korelasyonu ayda bir (`ind.py` çıktısı `cor`).', '',
           '## Claude alarmları (adlarında “(v2.x …)” — haftalıkta `alarm-sil` ile silinir)\n', '| Sembol | Seviye | Yön | Ad |', '|---|---|---|---|']
    md += [f"| {x['sembol']} | {tr(x['fiyat'])} | {'↑' if x['yon'] == 'cross_up' else '↓'} | {x['ad']} |" for x in ALL]
    md += ['', '## Grafik', '', 'Bölgeler “Claude Kesişim Bölgeleri” Pine göstergesiyle (`USER;1a93bd48668a4240a5176742bd31f615`), layout Günlük_2. Grafikteki gösterge eski sürüme sabitlenebilir: kod güncellenince yeni sürüm gelmezse göstergeyi yeniden ekle.']
    open(os.path.join(IS, 'izleme_listesi.md'), 'w').write('\n'.join(md) + '\n')


def cmd_pozisyon(a):
    """Repo iş akışı günlüklerinden (update-position*.yml) son işlemler ve güncel adetler. gh erişimi gerekir."""
    wf = 'update-position.yml' if a.pazar == 'abd' else 'update-position-bist.yml'
    r = subprocess.run(['gh', 'run', 'list', '-R', 'ridvanylmz-code/portfolio-midas', '--workflow', wf, '-L', str(a.limit),
                        '--json', 'databaseId,createdAt,conclusion'], capture_output=True, text=True)
    if r.returncode: sys.exit('gh erişimi yok: ' + r.stderr.strip()[:200])
    son, islem = {}, []
    for run in sorted(json.loads(r.stdout), key=lambda x: x['createdAt']):
        if run['createdAt'][:10] < a.since or run['conclusion'] != 'success': continue
        log = subprocess.run(['gh', 'run', 'view', str(run['databaseId']), '-R', 'ridvanylmz-code/portfolio-midas', '--log'], capture_output=True, text=True).stdout
        for l in log.splitlines():
            m = re.search(r'(ALIŞ|SATIŞ) (\w+): (\d+) adet @ \$?([\d.,]+)', l)
            if m: islem.append((run['createdAt'][:16], m.group(1), m.group(2), int(m.group(3)), m.group(4)))
            m = re.search(r'Yeni pozisyon: (\d+) adet, ort\. maliyet \$?([\d.,]+)|Kalan: (\d+) adet \(maliyet \$?([\d.,]+)', l)
            if m and islem: son[islem[-1][2]] = (int(m.group(1) or m.group(3)), m.group(2) or m.group(4))
            m = re.search(r'Nakit: \$?([\d.,]+)', l)
            if m: son['_nakit'] = m.group(1)
    for x in islem: print(*x)
    print('\nSon durum:', json.dumps(son, ensure_ascii=False))
    json.dump(dict(islemler=islem, son=son), open(os.path.join(IS, f'pozisyon_{a.pazar}.json'), 'w'), ensure_ascii=False, indent=1)


def cmd_alarm_sil(a):
    t = json.loads(open(a.liste).read()); t = json.loads(t[0]['text']) if isinstance(t, list) else t
    H = PAZAR[a.pazar]['hisseler']
    ids = [x['alert_id'] for x in t['alerts'] if re.search(r'\(v2\.\d', x.get('name') or '') and any(x['symbol'].endswith(':' + h) for h in H)]
    print(json.dumps(ids))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='k', required=True)
    x = sp.add_parser('veri'); x.add_argument('--klasor')
    x = sp.add_parser('puan'); x.add_argument('--pazar', required=True, choices=PAZAR); x.add_argument('--analiz'); x.add_argument('--n', type=int, default=500); x.add_argument('--yalniz-son', action='store_true')
    x = sp.add_parser('analiz'); x.add_argument('--pazar', required=True, choices=PAZAR); x.add_argument('--cfg', required=True); x.add_argument('--tarih', required=True)
    x = sp.add_parser('yayinla'); x.add_argument('--plan', required=True)
    x = sp.add_parser('pozisyon'); x.add_argument('--pazar', required=True, choices=PAZAR); x.add_argument('--since', required=True); x.add_argument('--limit', type=int, default=40)
    x = sp.add_parser('alarm-sil'); x.add_argument('--liste', required=True); x.add_argument('--pazar', required=True, choices=PAZAR)
    a = ap.parse_args()
    {'veri': cmd_veri, 'puan': cmd_puan, 'analiz': cmd_analiz, 'yayinla': cmd_yayinla, 'pozisyon': cmd_pozisyon, 'alarm-sil': cmd_alarm_sil}[a.k](a)
