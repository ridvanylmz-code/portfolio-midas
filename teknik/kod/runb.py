import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import eng, json
BIST_TATIL=['2026-10-29','2027-01-01']  # BIST resmi tatilleri; her analizde önümüzdeki 6 hafta için güncelle
eng.IND=json.load(open('indb.json')); eng.HOL=[eng.pd.Timestamp(x) for x in BIST_TATIL]
from eng import *; import eng as E2
from cfgb import CFG; from struct_ import gaps
import v1t; v1t.IND=E2.IND; v1t.HOL=E2.HOL
from v1t import v1_zones,time_windows
RES={}
for s,cfg in CFG.items():
    d=load(s); I=E2.IND[s]; A=I['atr']; c=d.c.iloc[-1]
    st=[(p,f"{'tepe' if t=='H' else 'dip'} {ix.strftime('%d.%m.%y')}") for t,ix,p in zz(d.iloc[-260:],0.12)[:-1]]
    st+=[(p,f"{'tepe' if t=='H' else 'dip'} {ix.strftime('%d.%m.%y')}") for t,ix,p in zz(d.iloc[-45:],0.05)[:-1] if ix>=d.index[-45]]
    for k,dt,lo,hi in gaps(d): st+=[(lo,f'boşluk {k} {dt:%d.%m} alt'),(hi,f'boşluk {k} {dt:%d.%m} üst')]
    st+=cfg['darvas']; cfg['struct']=st
    d,c,A,L,av=E2.build(s,cfg)
    Z=E2.zones_v2(L,A,c,'Savunma' if I['mode']=='Savunma' or True else I['mode'])  # risk-off: destekler düşer
    v1=v1_zones(s,cfg,L,A,c,d); src,W=time_windows(s,cfg,d)
    RES[s]=dict(L=L,Z=Z,c=c,A=A,v1=v1,tsrc=src,tw=W)
    print(f'\n######## {s} c={c} ATR={A:.3f} mode={I["mode"]}')
    for z in Z:
        if abs((z['lo']+z['hi'])/2-c)<=4*A: print(f" {z['grade']}->{z['grade_adj']} {z['lo']:.3f}–{z['hi']:.3f} {z['role']} {z['geo']}/{z['ind']}={z['score']} | {z['comp'][:520]}")
    print(' v1:',[(round(a,3),round(b,3),g) for a,b,g,*_ in v1])
    for a,b,inn in W: print('  PENCERE',a.date(),'–',b.date(),len(inn),'|',' ; '.join(f"{x[0]:%d.%m} {x[1]}" for x in inn))
import pickle; pickle.dump(RES,open('resb.pkl','wb'))
