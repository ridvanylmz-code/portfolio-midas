import pandas as pd, numpy as np
import os
P=os.environ.get('TA_DATA','data/')  # pickle klasörü
def load(sym):
    import os
    if os.path.exists(P+f'{sym}_1D.pkl'):
        d=pd.read_pickle(P+f'{sym}_1D.pkl')
    else:
        h=pd.read_pickle(P+f'{sym}_1h.pkl'); h['date']=h.dt.dt.date
        d=h.groupby('date').agg(o=('o','first'),h=('h','max'),l=('l','min'),c=('c','last'),v=('v','sum')).reset_index()
        d['dt']=pd.to_datetime(d['date'])
    d=d.copy(); d['date']=pd.to_datetime(d.dt.dt.date if hasattr(d.dt,'dt') else d['dt']).dt.normalize() if 'date' not in d else pd.to_datetime(d['date'])
    d=d.set_index('date')[['o','h','l','c','v']].astype(float)
    return d
def h4(sym):
    h=pd.read_pickle(P+f'{sym}_1h.pkl')
    h['date']=h.dt.dt.date; h['seg']=(h.dt.dt.hour*60+h.dt.dt.minute>=13*60+30).astype(int)
    g=h.groupby(['date','seg']).agg(o=('o','first'),h=('h','max'),l=('l','min'),c=('c','last'),v=('v','sum'),t=('dt','first')).reset_index()
    return g.set_index('t')[['o','h','l','c','v']]
def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def rma(s,n): return s.ewm(alpha=1/n,adjust=False).mean()
def rsi(c,n=14):
    d=c.diff(); up=rma(d.clip(lower=0),n); dn=rma(-d.clip(upper=0),n); return 100-100/(1+up/dn)
def atr(df,n=14):
    tr=pd.concat([df.h-df.l,(df.h-df.c.shift()).abs(),(df.l-df.c.shift()).abs()],axis=1).max(axis=1); return rma(tr,n)
def adx(df,n=14):
    up=df.h.diff(); dn=-df.l.diff()
    pdm=np.where((up>dn)&(up>0),up,0.); mdm=np.where((dn>up)&(dn>0),dn,0.)
    tr=pd.concat([df.h-df.l,(df.h-df.c.shift()).abs(),(df.l-df.c.shift()).abs()],axis=1).max(axis=1)
    a=rma(tr,n); pdi=100*rma(pd.Series(pdm,index=df.index),n)/a; mdi=100*rma(pd.Series(mdm,index=df.index),n)/a
    dx=100*(pdi-mdi).abs()/(pdi+mdi); return rma(dx,n),pdi,mdi
def macd(c):
    m=ema(c,12)-ema(c,26); s=ema(m,9); return m,s,m-s
def supertrend(df,n=10,m=2.0):
    a=atr(df,n); hl2=(df.h+df.l)/2; ub=hl2+m*a; lb=hl2-m*a
    fu=ub.copy(); fl=lb.copy(); dirn=pd.Series(1,index=df.index); st=pd.Series(np.nan,index=df.index)
    for i in range(1,len(df)):
        fu.iloc[i]=ub.iloc[i] if (ub.iloc[i]<fu.iloc[i-1] or df.c.iloc[i-1]>fu.iloc[i-1]) else fu.iloc[i-1]
        fl.iloc[i]=lb.iloc[i] if (lb.iloc[i]>fl.iloc[i-1] or df.c.iloc[i-1]<fl.iloc[i-1]) else fl.iloc[i-1]
        if dirn.iloc[i-1]==-1 and df.c.iloc[i]>fu.iloc[i-1]: dirn.iloc[i]=1
        elif dirn.iloc[i-1]==1 and df.c.iloc[i]<fl.iloc[i-1]: dirn.iloc[i]=-1
        else: dirn.iloc[i]=dirn.iloc[i-1]
        st.iloc[i]=fl.iloc[i] if dirn.iloc[i]==1 else fu.iloc[i]
    return dirn,st
def weekly(d):
    return d.resample('W-FRI').agg({'o':'first','h':'max','l':'min','c':'last','v':'sum'}).dropna()
def zigzag(d,thr):
    # thr: fraction
    piv=[]; trend=0; hi=d.h.iloc[0]; hii=d.index[0]; lo=d.l.iloc[0]; loi=d.index[0]
    for i,(ix,r) in enumerate(d.iterrows()):
        if r.h>hi: hi,hii=r.h,ix
        if r.l<lo: lo,loi=r.l,ix
        if trend>=0 and r.l<hi*(1-thr) and hii>=loi:
            piv.append(('H',hii,hi)); trend=-1; lo,loi=r.l,ix
        elif trend<=0 and r.h>lo*(1+thr) and loi>=hii:
            piv.append(('L',loi,lo)); trend=1; hi,hii=r.h,ix
    return piv
def pivots(s_hi,s_lo,k):
    H=[];L=[]
    for i in range(k,len(s_hi)):
        lo=max(0,i-k); hi=min(len(s_hi),i+k+1)
        if s_hi.iloc[i]==s_hi.iloc[lo:hi].max(): H.append(i)
        if s_lo.iloc[i]==s_lo.iloc[lo:hi].min(): L.append(i)
    return H,L
def zz(d,thr):
    piv=[]; dirn=None; ext=None; exi=None
    for ix,r in d.iterrows():
        if dirn is None:
            dirn=1; ext=r.h; exi=ix; low0=(r.l,ix); continue
        if dirn==1:
            if r.h>=ext: ext,exi=r.h,ix
            elif r.l<=ext*(1-thr): piv.append(('H',exi,ext)); dirn=-1; ext,exi=r.l,ix
        else:
            if r.l<=ext: ext,exi=r.l,ix
            elif r.h>=ext*(1+thr): piv.append(('L',exi,ext)); dirn=1; ext,exi=r.h,ix
    piv.append(('H' if dirn==1 else 'L',exi,ext)); return piv
