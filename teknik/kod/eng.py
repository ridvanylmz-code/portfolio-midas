import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
import json, math, random
IND=json.load(open('ind.json'))
HOL=[pd.Timestamp('2026-11-26'),pd.Timestamp('2026-12-25'),pd.Timestamp('2027-01-01')]
import os as _os
TODAY=pd.Timestamp(_os.environ.get('TA_TODAY',pd.Timestamp.today().strftime('%Y-%m-%d')))  # analiz günü: TA_TODAY=YYYY-MM-DD
def tdays(start,end):
    r=pd.bdate_range(start,end); return [x for x in r if x not in HOL]
def tadd(d0,n):
    r=pd.bdate_range(d0,periods=n*2+10)
    r=[x for x in r if x not in HOL]
    return r[n] if r[0]==pd.Timestamp(d0) else r[n-1]
def nexttd(d):
    d=pd.Timestamp(d)
    while d.weekday()>=5 or d in HOL: d+=pd.Timedelta(days=1)
    return d
ELLIOTT=False  # v2.4 (13.11.2026): A/B senaryo seviyeleri (aile 4-5) kesişim puanına girmez; True = v2.3 davranışı
FS={1:1,2:1.5,3:1,4:1,5:1.5,6:1,7:1,8:1}; GEO={1,2,3,4,5}
FN={1:'Fib düzeltme',2:'Fib uzatma',3:'Kanal/yelpaze',4:'Elliott A',5:'B senaryosu',6:'EMA',7:'Yapı',8:'Hacim/VWAP'}
def line_at(t1,p1,t2,p2,t,idx):
    i1,i2,i=idx.get_loc(t1),idx.get_loc(t2),len(idx)-1+ (0 if t is None else 0)
    return p1+(p2-p1)*(i-i1)/(i2-i1)
def build(s,cfg):
    d=load(s); idx=d.index; c=d.c.iloc[-1]; I=IND[s]; A=I['atr']
    L=[]  # (price,fam,label)
    for nm,p1,p2,rs in cfg['retr']:
        for r in rs: L.append((p2+r*(p1-p2),1,f'{nm} %{r*100:g}'))
    for nm,a0,a1,b,rs in cfg['ext']:
        for r in rs: L.append((b+r*(a1-a0),2,f'{nm} {r:g}'))
    # channel
    (t1,p1),(t2,p2),(t3,p3)=cfg['chan']; t1,t2,t3=map(pd.Timestamp,(t1,t2,t3))
    i1,i2,i3,it=idx.get_loc(t1),idx.get_loc(t2),idx.get_loc(t3),len(idx)-1
    sl=(p2-p1)/(i2-i1); base_t=p1+sl*(it-i1); w=p3-(p1+sl*(i3-i1))
    for r in [0,0.382,0.618,1,1.272,1.382,1.618]: L.append((base_t+r*w,3,f'Kanal {r:g}'))
    # fan
    (ta,pa),(tb,pb)=cfg['fan']; ia,ib=idx.get_loc(pd.Timestamp(ta)),idx.get_loc(pd.Timestamp(tb))
    for r,nm in [(0.382,'0,382'),(0.5,'0,5'),(0.618,'0,618'),(1/3,'1/3'),(2/3,'2/3')]:
        lev=pb+r*(pa-pb); L.append((pa+(lev-pa)*(it-ia)/(ib-ia),3,f'Yelpaze {nm}'))
    if ELLIOTT:
        for p in cfg['A']: L.append((p[0],4,'A: '+p[1]))
        for p in cfg['B']: L.append((p[0],5,'B: '+p[1]))
    E=I['E']
    for n in ['21','34','89','144','233']:
        if n in cfg.get('ema_skip',[]): continue
        L.append((E[n],6,f'EMA{n}'))
    for p in cfg['struct']: L.append((p[0],7,p[1]))
    # volume nodes + avwap
    from struct_ import vprofile, avwap
    if d.v.sum()>0:
        for pr,wt in vprofile(d): L.append((pr,8,f'Hacim düğümü ({wt:g})'))
    av={}
    for nm,dt in cfg['avwap']:
        v=avwap(d,dt); av[nm]=v; L.append((v,8,f'ÇVWAP {nm}'))
    L=[(round(p,4),f,l) for p,f,l in L if abs(p-c)<=4.5*A]
    return d,c,A,L,av
def dedupe(levels):
    # merge levels within 0.1%: keep highest score fam, keep labels
    lv=sorted(levels); out=[]
    for p,f,l in lv:
        if out and abs(p-out[-1][0])/p<0.001:
            q=out[-1]
            if FS[f]>FS[q[1]] or (FS[f]==FS[q[1]] and f in (6,7,8) and q[1] not in (6,7,8)): out[-1]=(p,f,l+' ≈ '+q[2])
            else: out[-1]=(q[0],q[1],q[2]+' ≈ '+l)
        else: out.append((p,f,l))
    return out
def score(cl):
    fams={}
    for p,f,l in cl: fams.setdefault(f,[]).append((p,l))
    geo=0;
    if 2 in fams and 5 in fams and min(abs(a-b)/a for a,_ in fams[2] for b,_ in fams[5])<0.003:
        geo+=2; used={2,5}
    else: used=set()
    for f in fams:
        if f in GEO and f not in used: geo+=FS[f]
    geo=min(geo,3); ind=sum(1 for f in fams if f in (6,7,8))
    return geo,ind,fams
def cluster(levels,A,price,tolf=0.3,wmax=0.4):  # v2.2 (07.11.2026; v2.1: wmax=0.6)
    tol=lambda p:max(tolf*A,0.015*p)
    def chains(lv):
        if not lv: return []
        out=[]; g=[lv[0]]
        for x in lv[1:]:
            if x[0]-g[-1][0]<=tol(x[0]): g.append(x)
            else: out.append(g); g=[x]
        out.append(g); return out
    def split(g):
        if g[-1][0]-g[0][0]<=wmax*A: return [g]
        best=None
        for i in range(len(g)):
            sub=[x for x in g[i:] if x[0]-g[i][0]<=wmax*A]
            ge,ind,_=score(sub); sc=ge+ind+0.01*len(sub)
            if best is None or sc>best[0]: best=(sc,sub)
        sub=best[1]; lo,hi=sub[0][0],sub[-1][0]
        left=[x for x in g if x[0]<lo]; right=[x for x in g if x[0]>hi]
        r=[sub]
        for part in (left,right):
            for ch in chains(part): r+=split(ch)
        return r
    res=[]
    for ch in chains(sorted(levels)): res+=split(ch)
    return res
def zones_v2(L,A,price,mode):
    out=[]
    for cl in cluster(dedupe(L),A,price):
        ge,ind,fams=score(cl); tot=ge+ind
        if tot>=4 and ind>=2: g='KRİTİK'
        elif tot>=3 and ind>=1: g='ÖNEMLİ'
        else: continue
        lo,hi=min(p for p,_,_ in cl),max(p for p,_,_ in cl)
        role='direnç' if lo>price else ('destek' if hi<price else 'pivot (fiyat içinde)')
        g2=g
        if mode=='Savunma' and role=='destek': g2={'KRİTİK':'ÖNEMLİ','ÖNEMLİ':'izleme'}[g]
        out.append(dict(lo=lo,hi=hi,geo=ge,ind=ind,score=tot,grade=g,grade_adj=g2,role=role,point=(hi-lo)<0.3*A and g=='KRİTİK',
            comp='; '.join(f"{FN[f]}: "+', '.join(f"{l} {p:.2f}" for p,l in v) for f,v in sorted(fams.items()))))
    return out
