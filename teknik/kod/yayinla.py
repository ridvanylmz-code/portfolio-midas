"""Pano verisini repo için hazırla: adet/nakit/gerçek durum çıkarılır (repo herkese açık).
Kullanım: python3 yayinla.py pano_salinim.json data_klasoru(HISSE.csv, ATR için) cikti_klasoru
"""
import json, re, sys, datetime as dt
import pandas as pd
src, data, out = sys.argv[1:4]
S = json.load(open(src))
def tip(r):
    e = (r.get('emir') or '').lower()
    if r.get('fiyat') is None: return 'not'
    if r.get('tip') and r['tip'] != 'not': return r['tip']
    if 'sigorta' in e: return 'sigorta'
    if 'kenardaki' in e: return 'yedek'
    if re.search(r'uyarı|b hedefi', e): return 'uyari'
    if 'çekirdek stop' in e or ('çekirdek sat' in e and 'ertelenen' not in e): return 'stop'
    if re.search(r'geri al|\bal\b', e): return 'al'
    if re.search(r'\bsat\b', e): return 'sat'
    return 'uyari'
ADET = re.compile(r'\s*\(?\b\d[\d.]*\s*adet\b[^);,]*\)?|\s*\(\d[\d.]*\)|\s*\d[\d.]*\s*\+\s*\d[\d.]*\s*=?\s*\d*[\d.]*\s*adet', re.I)
def temiz(t):
    t = ADET.sub('', t or '')
    t = re.sub(r'(ABD|BIST) nakit [^;,)]*', '', t)
    t = re.sub(r'(Kalan|Ticaret)[^;.]*=\s*[^;.]*', '', t)
    return re.sub(r'\s{2,}', ' ', t).strip(' ;,')
rows = []
for r in S:
    if r.get('sira') == 0 or 'gerçek durum' in (r.get('emir') or '').lower(): continue
    rr = {k: r.get(k) for k in ['id', 'hisse', 'sira', 'mod', 'fiyat', 'fiyat_metin', 'kaynak', 'hafta', 'bilanco']}
    rr['tip'] = tip(r); rr['emir'] = temiz(r.get('emir')) or r.get('emir'); rr['kosul'] = temiz(r.get('kosul'))
    rows.append(rr)
BIST = {'BIENY', 'SASA', 'SMRTG', 'MIATK', 'GMSTR', 'ALTIN', 'TCELL', 'THYAO'}
meta = {'guncelleme': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'hisseler': {}}
for h in sorted({r['hisse'] for r in rows}):
    df = pd.read_csv(f'{data}/{h}.csv'); pc = df.c.shift()
    tr = pd.concat([df.h - df.l, (df.h - pc).abs(), (df.l - pc).abs()], axis=1).max(axis=1)
    atr = float(tr.ewm(alpha=1/14, adjust=False).mean().iloc[-1])
    hf = max(r['hafta'] for r in rows if r['hisse'] == h)
    meta['hisseler'][h] = dict(pazar='bist' if h in BIST else 'us', atr=round(atr, 4), atr_tarih=str(df.d.iloc[-1]),
                               plan=hf, mod=next(r['mod'] for r in rows if r['hisse'] == h))
json.dump(rows, open(f'{out}/salinim.json', 'w'), ensure_ascii=False, indent=1)
json.dump(meta, open(f'{out}/meta.json', 'w'), ensure_ascii=False, indent=1)
for r in rows: print(r['id'], r['tip'], r['fiyat'], '|', r['emir'], '|', r['kosul'][:70])
