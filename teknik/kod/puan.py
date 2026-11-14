"""Nesnel puanlama: kesişim bölgeleri ve zaman pencereleri, rastgele (şans) karşılaştırmasıyla.

Kullanım:  python3 puan.py bolgeler.csv pencereler.csv data/  [--n 500] [--seed 20261113]
Girdi:
  bolgeler.csv   analiz,ref,hisse,alt,ust,guc        (ref = analizde kullanılan son kapanış günü)
  pencereler.csv analiz,ref,hisse,bas,son,olay       (olay: dip / tepe / iki)
  data/HISSE.csv d,o,h,l,c                           (günlük bar)
Kurallar (yöntem dosyası bölüm 7a):
  Bölge rolü analiz kapanışına göre: üstte direnç, altta destek, içinde pivot.
  Dokunma: ref sonrası H=7 bar içinde bar aralığı bölgeye değer.
  Dokunduktan sonraki 4 bar içinde:
    ✓  beklenen yönde 1 ATR tepki (direnç: alt − 1 ATR'ye iner; destek: üst + 1 ATR'ye çıkar; pivot: iki yönden biri)
    ✗  önce bölgenin öte yanında 0,15 ATR'den fazla günlük kapanış (kırılım)
    ½  ikisi de yok;  'bekliyor': 4 bar dolmadı.
  Pencere: k=2 bar sağ/sol yerel dip/tepe ve 5 bar içinde 1 ATR tepki = pivot.
    ✓ beklenen türde pivot pencereye ±2 işlem günü yakın; ½ yalnız ters türde; ✗ pivot yok.
  Şans: aynı genişlikte rastgele bölgeler (fiyatın ±4 ATR'si) ve aynı uzunlukta rastgele pencereler, N tekrar.
"""
import sys, argparse, random
import numpy as np, pandas as pd

H, TEPKI_BAR, TEPKI_ATR, KIRILIM_ATR, TOL = 7, 4, 1.0, 0.15, 2


def atr14(df):
    pc = df.c.shift()
    tr = pd.concat([df.h - df.l, (df.h - pc).abs(), (df.l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False).mean()


def yukle(klasor, hisse):
    df = pd.read_csv(f"{klasor}/{hisse}.csv", parse_dates=["d"])
    df["atr"] = atr14(df)
    return df.reset_index(drop=True)


def ref_index(df, ref):
    return int(df.index[df.d <= pd.Timestamp(ref)][-1])


def bolge_puan(df, r, alt, ust):
    """Bir bölgeyi puanla: ('dokunmadi'|'✓'|'½'|'✗'|'bekliyor', rol)."""
    p0, atr = df.c[r], df.atr[r]
    rol = "direnc" if alt > p0 else "destek" if ust < p0 else "pivot"
    son = len(df) - 1
    for i in range(r + 1, min(r + H, son) + 1):
        if df.l[i] <= ust and df.h[i] >= alt:
            break
    else:
        return ("dokunmadi" if r + H <= son else "bekliyor"), rol
    for j in range(i, min(i + TEPKI_BAR, son) + 1):
        asagi = df.l[i:j + 1].min() <= alt - TEPKI_ATR * atr
        yukari = df.h[i:j + 1].max() >= ust + TEPKI_ATR * atr
        if rol == "direnc":
            if df.c[j] > ust + KIRILIM_ATR * atr and not asagi:
                return "✗", rol
            if asagi:
                return "✓", rol
        elif rol == "destek":
            if df.c[j] < alt - KIRILIM_ATR * atr and not yukari:
                return "✗", rol
            if yukari:
                return "✓", rol
        elif asagi or yukari:
            return "✓", rol
    return ("½" if i + TEPKI_BAR <= son else "bekliyor"), rol


def pivotlar(df, r):
    """ref sonrası teyitli dip/tepe pivotları: {index: 'dip'|'tepe'}."""
    out = {}
    for k in range(max(r - 2, 2), len(df) - 2):
        atr = df.atr[r]
        sonra = slice(k + 1, min(k + 6, len(df)))
        if df.l[k] == df.l[k - 2:k + 3].min() and df.h[sonra].max() - df.l[k] >= TEPKI_ATR * atr:
            out[k] = "dip"
        if df.h[k] == df.h[k - 2:k + 3].max() and df.h[k] - df.l[sonra].min() >= TEPKI_ATR * atr:
            out[k] = "tepe" if k not in out else "iki"
    return out


def pencere_puan(df, piv, i0, i1, olay):
    if i1 + TOL + 2 > len(df) - 1:
        bulunan = [t for k, t in piv.items() if i0 - TOL <= k <= i1 + TOL]
        if not bulunan:
            return "bekliyor"
    else:
        bulunan = [t for k, t in piv.items() if i0 - TOL <= k <= i1 + TOL]
    if not bulunan:
        return "✗"
    if olay == "iki" or any(t in (olay, "iki") for t in bulunan):
        return "✓"
    return "½"


def oran(sonuclar):
    s = [x for x in sonuclar if x in ("✓", "½", "✗")]
    if not s:
        return None, 0
    return (s.count("✓") + 0.5 * s.count("½")) / len(s), len(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bolgeler"); ap.add_argument("pencereler"); ap.add_argument("data")
    ap.add_argument("--n", type=int, default=500); ap.add_argument("--seed", type=int, default=20261113)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    B = pd.read_csv(a.bolgeler); P = pd.read_csv(a.pencereler)
    cache = {}
    def veri(h):
        if h not in cache:
            cache[h] = yukle(a.data, h)
        return cache[h]

    # --- Bölgeler
    satir, gercek, dok_g = [], [], []
    for _, z in B.iterrows():
        df = veri(z.hisse); r = ref_index(df, z.ref)
        s, rol = bolge_puan(df, r, z.alt, z.ust)
        satir.append(dict(analiz=z.analiz, hisse=z.hisse, bolge=f"{z.alt}–{z.ust}", guc=z.guc, rol=rol, sonuc=s))
        if s != "bekliyor":
            dok_g.append(s != "dokunmadi"); gercek.append(s)
    bt = pd.DataFrame(satir)
    sans_isabet, sans_dok = [], []
    for _ in range(a.n):
        sonuc, dok = [], []
        for _, z in B.iterrows():
            df = veri(z.hisse); r = ref_index(df, z.ref)
            p0, atr, w = df.c[r], df.atr[r], z.ust - z.alt
            m = rnd.uniform(p0 - 4 * atr, p0 + 4 * atr)
            s, _ = bolge_puan(df, r, m - w / 2, m + w / 2)
            if s != "bekliyor":
                dok.append(s != "dokunmadi"); sonuc.append(s)
        sans_isabet.append(oran(sonuc)[0]); sans_dok.append(np.mean(dok))
    g_isabet, g_n = oran(gercek)
    sans_isabet = np.array([x for x in sans_isabet if x is not None])

    # --- Pencereler
    psat, gp = [], []
    for _, w in P.iterrows():
        df = veri(w.hisse); r = ref_index(df, w.ref); piv = pivotlar(df, r)
        i0 = int(df.index[df.d >= pd.Timestamp(w.bas)][0]) if (df.d >= pd.Timestamp(w.bas)).any() else len(df)
        i1s = df.index[df.d <= pd.Timestamp(w.son)]; i1 = int(i1s[-1]) if len(i1s) else i0
        s = pencere_puan(df, piv, i0, max(i1, i0), w.olay)
        psat.append(dict(analiz=w.analiz, hisse=w.hisse, pencere=f"{w.bas[5:]}→{w.son[5:]}", olay=w.olay, sonuc=s))
        gp.append(s)
    sans_p = []
    for _ in range(a.n):
        sonuc = []
        for _, w in P.iterrows():
            df = veri(w.hisse); r = ref_index(df, w.ref); piv = pivotlar(df, r)
            i0 = int(df.index[df.d >= pd.Timestamp(w.bas)][0]) if (df.d >= pd.Timestamp(w.bas)).any() else len(df)
            i1s = df.index[df.d <= pd.Timestamp(w.son)]; L = max(int(i1s[-1]) if len(i1s) else i0, i0) - i0
            ust = len(df) - 1 - TOL - 2 - L
            if ust < r + 1:
                continue
            b = rnd.randint(r + 1, ust)
            sonuc.append(pencere_puan(df, piv, b, b + L, w.olay))
        sans_p.append(oran(sonuc)[0])
    sans_p = np.array([x for x in sans_p if x is not None])
    pt = pd.DataFrame(psat)
    gp_isabet, gp_n = oran(gp)

    pd.set_option("display.width", 200); pd.set_option("display.max_rows", 200)
    print(bt.to_string(index=False)); print()
    print(pt.to_string(index=False)); print()
    def q(x): return f"%{100 * x:.0f}"
    print("ÖZET")
    print(f"Bölge dokunma oranı: gerçek {q(np.mean(dok_g))} · şans ort. {q(np.mean(sans_dok))}")
    print(f"Bölge isabeti (dokunulanlarda): gerçek {q(g_isabet)} (n={g_n}) · şans ort. {q(sans_isabet.mean())} "
          f"· gerçekten iyi şans oranı {q((sans_isabet >= g_isabet).mean())} (tek yönlü p)")
    for guc in ["KRİTİK", "ÖNEMLİ", "İzleme"]:
        o, n = oran(bt[bt.guc == guc].sonuc.tolist()); print(f"  {guc}: {q(o) if o is not None else '—'} (n={n})")
    for rol in ["direnc", "destek", "pivot"]:
        o, n = oran(bt[bt.rol == rol].sonuc.tolist()); print(f"  {rol}: {q(o) if o is not None else '—'} (n={n})")
    print(f"Zaman penceresi: gerçek {q(gp_isabet) if gp_isabet is not None else '—'} (n={gp_n}) · şans ort. "
          f"{q(sans_p.mean()) if len(sans_p) else '—'} · p {q((sans_p >= gp_isabet).mean()) if len(sans_p) and gp_isabet is not None else '—'}")
    bt.to_csv("puan_bolgeler.csv", index=False); pt.to_csv("puan_pencereler.csv", index=False)


if __name__ == "__main__":
    main()
