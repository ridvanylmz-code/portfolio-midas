"""MCP get-ohlcv çıktısını (rows/bars JSON; dosyaya düşmüş .txt) pickle'a çevirir.
Kullanım:
  python3 veri.py <mcp_cikti.txt> <SEMBOL> <1D|1h|4h> [abd|bist]
Çıktı: $TA_DATA (varsayılan data/) altında SEMBOL_<tf>.pkl  (sütunlar o,h,l,c,v,dt)
BIST 4h verisi ayrıca günlüğe derlenir (SEMBOL_1D.pkl); ABD 1h verisi lib.load içinde günlüğe derlenir.
Notlar: BIST'te hacim gelmez (v=0). ABD 1h'da seans dışı barlar olabilir; normal seans 09:30–16:00 ET süzülür.
"""
import sys, os, json, pandas as pd
def oku(f):
    t=open(f).read(); j=json.loads(t)
    if isinstance(j,list) and j and isinstance(j[0],dict) and 'text' in j[0]: j=json.loads(j[0]['text'])
    bars=j['bars'] if 'bars' in j else j
    if isinstance(bars,dict):  # columns formatı
        bars=[dict(zip(bars.keys(),v)) for v in zip(*bars.values())]
    d=pd.DataFrame(bars).rename(columns={'open':'o','high':'h','low':'l','close':'c','volume':'v','time':'t'})
    d['v']=pd.to_numeric(d.get('v',0),errors='coerce').fillna(0)
    return d.sort_values('t').drop_duplicates('t')
def main(f,sym,tf,piy='abd'):
    P=os.environ.get('TA_DATA','data/'); os.makedirs(P,exist_ok=True)
    tz='America/New_York' if piy=='abd' else 'Europe/Istanbul'
    d=oku(f); d['dt']=pd.to_datetime(d.t,unit='s',utc=True).dt.tz_convert(tz)
    if piy=='abd' and tf in('1h','4h'):
        m=d.dt.dt.hour*60+d.dt.dt.minute; d=d[(m>=570)&(m<960)]
    d=d[['o','h','l','c','v','dt']].reset_index(drop=True)
    d.to_pickle(P+f'{sym}_{tf}.pkl'); print(sym,tf,len(d),d.dt.iloc[0],'→',d.dt.iloc[-1],'son kapanış',d.c.iloc[-1])
    if piy=='bist' and tf=='4h':
        d['date']=d.dt.dt.date
        g=d.groupby('date').agg(o=('o','first'),h=('h','max'),l=('l','min'),c=('c','last'),v=('v','sum')).reset_index()
        g['dt']=pd.to_datetime(g['date']).dt.tz_localize(tz); g=g[['o','h','l','c','v','dt']]
        g.to_pickle(P+f'{sym}_1D.pkl'); print(sym,'1D (4s’ten)',len(g))
if __name__=='__main__': main(*sys.argv[1:])
