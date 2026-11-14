import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from eng import *; from cfg import CFG; from struct_ import gaps
RES={}
for s,cfg in CFG.items():
    d=load(s); I=IND[s]; A=I['atr']; c=d.c.iloc[-1]
    st=[]
    for t,ix,p in [q for q in zz(d.iloc[-260:],0.12)[:-1]]+[q for q in zz(d.iloc[-45:],0.05)[:-1] if q[1]>=d.index[-45]]:
        st.append((p,f"{'tepe' if t=='H' else 'dip'} {ix.strftime('%d.%m.%y')}"))
    for k,dt,lo,hi in gaps(d):
        st+= [(lo,f'boşluk {k} {dt:%d.%m} alt'),(hi,f'boşluk {k} {dt:%d.%m} üst')]
    st+=cfg['darvas']; cfg['struct']=st
    d,c,A,L,av=build(s,cfg)
    Z=zones_v2(L,A,c,I['mode'])
    RES[s]=dict(L=L,Z=Z,av=av,c=c,A=A)
    print(f'\n######## {s} c={c} ATR={A:.2f} mode={I["mode"]}  AVWAP:',{k:round(v,2) for k,v in av.items()})
    for z in Z: print(f" {z['grade']}->{z['grade_adj']} {z['lo']:.2f}–{z['hi']:.2f} {z['role']} geo{z['geo']} ind{z['ind']} = {z['score']}  | {z['comp']}")
from v1t import v1_zones,time_windows
for s,cfg in CFG.items():
    d=load(s); R_=RES[s]
    R_['v1']=v1_zones(s,cfg,R_['L'],R_['A'],R_['c'],d)
    src,W=time_windows(s,cfg,d); R_['tsrc']=src; R_['tw']=W
    print('\n==',s,'v1:',[(round(a,2),round(b,2),g,n,n2) for a,b,g,n,n2 in R_['v1']])
    for a,b,inn in W: print('  PENCERE',a.date(),'–',b.date(),len(inn),'|',' ; '.join(f"{x[0]:%d.%m} {x[1]}" for x in inn))
    print('  kaynaklar:',' ; '.join(f"{x[0]:%d.%m} {x[1]}" for x in src))
import pickle; pickle.dump(RES,open('res.pkl','wb'))
