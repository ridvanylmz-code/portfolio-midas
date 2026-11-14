import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from eng import *; from cfg import CFG; import pickle
def sq9(p):
    k=0
    while p*10**k<100: k+=1
    while p*10**k>=1000: k-=1
    r=math.sqrt(p*10**k); out=[]
    for n in [0.5,1,1.5,2]:
        for sgn in (1,-1): out.append(((r+sgn*n)**2)/10**k)
    return out
def v1_zones(s,cfg,L2,A,c,d):
    I=IND[s]; L=[]
    fam_map={1:1,2:2,3:3}
    for p,f,l in L2:
        if f in (1,2,3): L.append((p,f,l))
        elif f in (4,5): L.append((p,9,l))
        elif f==7: L.append((p,8 if 'Darvas' not in l else 7,l))
        elif f==8 and 'Hacim' in l: L.append((p,8,l))
    for n in [20,50,200]: L.append((ema(d.c,n).iloc[-1],6,f'EMA{n}'))
    pv=[p for _,p in [(0,cfg['A'][-1][0])]]+[x[0] for x in cfg['struct'][-8:]]+[c]
    pv=list(dict.fromkeys([round(x,3) for x in pv]))[:7]
    for p in pv:
        for q in sq9(p): L.append((q,4,f'Sq9({p:g})'))
    # Gann angles from main low (A invalidation) with speed of last decline
    (tA,pA),(tB,pB)=cfg['fan']; days=(pd.Timestamp(tB)-pd.Timestamp(tA)).days; sp=abs(pA-pB)/days
    dd=(TODAY-pd.Timestamp(tB)).days
    for nm,m in [('1x1',1),('2x1',2),('1x2',.5),('1x3',1/3),('1x4',.25)]: L.append((pB+m*sp*dd,5,f'Gann {nm} ({pB:g})'))
    L=[x for x in L if abs(x[0]-c)<=4*A]
    lv=sorted(L); tol=lambda p:max(0.5*A,0.015*p); groups=[]; g=[lv[0]]
    for x in lv[1:]:
        if x[0]-g[-1][0]<=tol(x[0]): g.append(x)
        else: groups.append(g); g=[x]
    groups.append(g); Z=[]
    for g in groups:
        while g:
            if g[-1][0]-g[0][0]>A:
                best=max(([x for x in g[i:] if x[0]-g[i][0]<=A] for i in range(len(g))),key=lambda sub:len({f for _,f,_ in sub}))
                sub=best; g=[x for x in g if x not in sub]
            else: sub=g; g=[]
            fams={f for _,f,_ in sub}
            if len(fams)>=3:
                lo,hi=min(x[0] for x in sub),max(x[0] for x in sub)
                gr='KRİTİK' if len(fams)>=4 and len(fams-{4})>=3 else 'ÖNEMLİ'
                Z.append((lo,hi,gr,len(fams),len(fams-{4})))
    Z=sorted(Z,key=lambda z:abs((z[0]+z[1])/2-c))[:3]
    return sorted(Z)
def time_windows(s,cfg,d):
    src=[]; last=d.index[-1]; horizon=tadd(TODAY,30)
    for dt,nm in cfg['piv_time']:
        dt=pd.Timestamp(dt); td=[x for x in tdays(dt,horizon)]
        for n in [5,8,13,21,34,55,89,144]:
            if n<len(td) and td[n]>TODAY and td[n]<=horizon: src.append((td[n],f'Fib {n}g ({nm})'))
        for n in [30,45,60,90,120,144,180,360]:
            t=nexttd(dt+pd.Timedelta(days=n))
            if TODAY<t<=horizon: src.append((t,f'Gann {n}gt ({nm})'))
    for a,b,st,nm in cfg['dur']:
        n=len(tdays(a,b))-1
        for r in [0.618,1.0,1.618,2.618]:
            t=tadd(pd.Timestamp(st),max(1,round(n*r)))
            if TODAY<t<=horizon: src.append((t,f'Süre {r:g}×{n}g ({nm})'))
    src.append((pd.Timestamp(cfg['earn']),cfg['earn_txt']))
    src=sorted(src); W=[]
    days=tdays(tadd(TODAY,1),horizon)
    for i in range(len(days)):
        win=days[i:i+4]
        inn=[x for x in src if win[0]<=x[0]<=win[-1]]
        if len(inn)>=3: W.append((win[0],win[-1],inn))
    # merge overlapping, keep max
    M=[]
    for w in W:
        if M and w[0]<=M[-1][1]:
            if len(w[2])>len(M[-1][2]): M[-1]=w
        else: M.append(w)
    # trim window to span of sources
    M=[(min(x[0] for x in w[2]),max(x[0] for x in w[2]),w[2]) for w in M]
    return src,M
