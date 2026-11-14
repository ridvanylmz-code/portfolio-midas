import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
import json
EARN={'RKLB':'2026-08-11','CRWV':'2026-08-12','SGML':'2026-08-14','WYFI':'2026-08-12'}
def gaps(d,n=60):
    out=[]; x=d.iloc[-n-1:]
    for i in range(1,len(x)):
        ph,pl=x.h.iloc[i-1],x.l.iloc[i-1]
        if x.l.iloc[i]>ph: # up gap: zone ph..low_i
            lo,hi=ph,x.l.iloc[i]; m=x.l.iloc[i+1:].min() if i+1<len(x) else np.inf
            if m>lo: out.append(('yukarı',x.index[i].date(),round(lo,3),round(min(hi,m),3)))
        if x.h.iloc[i]<pl:
            lo,hi=x.h.iloc[i],pl; M=x.h.iloc[i+1:].max() if i+1<len(x) else -np.inf
            if M<hi: out.append(('aşağı',x.index[i].date(),round(max(lo,M),3),round(hi,3)))
    return out
def vprofile(d,n=120,bins=40):
    x=d.iloc[-n:]; lo,hi=x.l.min(),x.h.max(); edges=np.linspace(lo,hi,bins+1); vol=np.zeros(bins)
    for _,r in x.iterrows():
        a=np.searchsorted(edges,r.l,side='right')-1; b=np.searchsorted(edges,r.h,side='right')-1
        a=max(a,0); b=min(b,bins-1); vol[a:b+1]+=r.v/(b-a+1)
    mids=(edges[:-1]+edges[1:])/2
    peaks=[i for i in range(bins) if vol[i]==vol[max(0,i-2):i+3].max()]
    peaks=sorted(peaks,key=lambda i:-vol[i])[:4]
    return [(round(mids[i],3),round(vol[i]/vol.max(),2)) for i in peaks]
def avwap(d,start):
    x=d.loc[start:]; tp=(x.h+x.l+x.c)/3; return (tp*x.v).cumsum().iloc[-1]/x.v.cumsum().iloc[-1]
def darvas(d):
    x=d.iloc[-80:]; n=len(x)
    for i in range(n-4,0,-1):
        if x.h.iloc[i]>=x.h.iloc[i+1:i+4].max() and x.h.iloc[i]>=x.h.iloc[max(0,i-3):i].max():
            top=x.h.iloc[i]; after=x.iloc[i:]
            # bottom: lowest low after top whose next 3 bars don't break it
            lows=after.l; j=lows.values.argmin(); bot=lows.iloc[j]
            conf=(len(after)-1-j)>=3
            broke_up=(after.c.iloc[1:]>top).any()
            return dict(top_date=str(x.index[i].date()),top=round(top,3),bottom=round(bot,3),bottom_date=str(lows.index[j].date()),bottom_confirmed=bool(conf),broken_up=bool(broke_up))
def div(d,k,n,label):
    c=d.c; r=rsi(c); _,_,h=macd(c); x=d.iloc[-n:]
    H,L=pivots(x.h,x.l,k); res=[]
    for kind,idx,ser in [('dip',L,x.l),('tepe',H,x.h)]:
        idx=idx[-3:]
        for a,b in zip(idx[:-1],idx[1:]):
            ia,ib=x.index[a],x.index[b]; pa,pb=ser.iloc[a],ser.iloc[b]
            ra,rb=r.loc[ia],r.loc[ib]; ha,hb=h.loc[ia],h.loc[ib]
            t='—'
            if kind=='dip' and pb<pa and (rb>ra or hb>ha): t='pozitif'+('(RSI)' if rb>ra else '')+('(MACDh)' if hb>ha else '')
            if kind=='tepe' and pb>pa and (rb<ra or hb<ha): t='negatif'+('(RSI)' if rb<ra else '')+('(MACDh)' if hb<ha else '')
            tey='teyitsiz' if b>=len(x)-3 else ''
            res.append(f"{label} {kind} {ia.date().strftime('%d.%m.%y')} {pa:.2f}→{ib.date().strftime('%d.%m.%y')} {pb:.2f} RSI {ra:.1f}→{rb:.1f} MACDh {ha:.2f}→{hb:.2f}: {t} {tey}")
    return res
if __name__=='__main__':
  out={}
  for s in ['RKLB','CRWV','SGML','WYFI']:
      d=load(s); w=weekly(d)
      x60=d.iloc[-60:]; hv=x60.v.idxmax()
      o=dict(gaps=gaps(d),vp=vprofile(d),darvas=darvas(d),hv_day=str(hv.date()))
      print('\n#####',s); print(json.dumps(o,default=str,ensure_ascii=False))
      for l in div(d,3,120,'G')+div(w,2,80,'H'): print(' ',l)
      out[s]=o
  json.dump(out,open('struct.json','w'),default=str)
