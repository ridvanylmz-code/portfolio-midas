import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
import json
S=['RKLB','CRWV','SGML','WYFI']; SEC={'RKLB':['UFO'],'CRWV':['SMH'],'SGML':['LIT'],'WYFI':['WGMI','SMH']}
spy=load('SPY'); out={}
# regime
sc=spy.c; e89=ema(sc,89); e233=ema(sc,233)
print('SPY',sc.iloc[-1],'EMA89',round(e89.iloc[-1],2),'EMA233',round(e233.iloc[-1],2),'EMA21',round(ema(sc,21).iloc[-1],2))
for s in S:
    d=load(s); c=d.c; a=atr(d); A,Pd,Md=adx(d); m,sg,hst=macd(c); r=rsi(c)
    E={n:ema(c,n).iloc[-1] for n in [21,34,89,144,233]}
    w=weekly(d); wc=w.c; wm,ws,wh=macd(wc); wr=rsi(wc); ao=((w.h+w.l)/2).rolling(5).mean()-((w.h+w.l)/2).rolling(34).mean()
    dirn,st=supertrend(d,10,2);
    h=h4(s); d4,st4=supertrend(h,10,2); e34_4=ema(h.c,34)
    order='>'.join(str(n) for n in sorted(E,key=lambda k:-E[k]))
    full_up=c.iloc[-1]>E[21]>E[34]>E[89]>E[144]>E[233]; full_dn=c.iloc[-1]<E[21]<E[34]<E[89]<E[144]<E[233]
    # mode
    cl=c.iloc[-1]; adxv=A.iloc[-1]
    if cl>E[21]>E[34]>E[89] and adxv>25 and Pd.iloc[-1]>Md.iloc[-1]: mode='Trend'
    elif cl<E[21]<E[34]<E[89] and adxv>25 and Md.iloc[-1]>Pd.iloc[-1]: mode='Savunma'
    else: mode='Bant'
    # RS
    rs=(c/spy.c.reindex(c.index).ffill()).dropna(); rse=ema(rs,21)
    rs21=rs.iloc[-1]/rs.iloc[-22]-1; rs63=rs.iloc[-1]/rs.iloc[-64]-1 if len(rs)>64 else np.nan
    rsst='Güçlü' if rs.iloc[-1]>rse.iloc[-1] and rs63>0 else ('Zayıf' if rs.iloc[-1]<rse.iloc[-1] and rs63<0 else 'Nötr')
    rs52=rs.iloc[-252:];
    cor={}
    ret=c.pct_change().iloc[-120:]
    cor['SPY']=ret.corr(spy.c.pct_change().reindex(ret.index))
    secrs={}
    for e in SEC[s]:
        x=load(e).c; cor[e]=ret.corr(x.pct_change().reindex(ret.index))
        rr=(c/x.reindex(c.index).ffill()).dropna(); secrs[e]=(round((rr.iloc[-1]/rr.iloc[-22]-1)*100,1),round((rr.iloc[-1]/rr.iloc[-64]-1)*100,1), rr.iloc[-1]>ema(rr,21).iloc[-1])
    # quant
    z=(c-ema(c,21))/a; zl=z.iloc[-1]
    lr=np.log(c).diff().iloc[-120:]; vr5=(np.log(c).diff(5).iloc[-120:].var())/(5*lr.var())
    idx=[i for i in range(30,len(c)-10) if abs(z.iloc[i]-zl)<=0.5]
    ev=[];last=-99
    for i in idx:
        if i-last>=5: ev.append(i); last=i
    f5=[c.iloc[i+5]/c.iloc[i]-1 for i in ev]; f10=[c.iloc[i+10]/c.iloc[i]-1 for i in ev]
    o=dict(close=cl,atr=a.iloc[-1],rsi=r.iloc[-1],adx=adxv,pdi=Pd.iloc[-1],mdi=Md.iloc[-1],macd=m.iloc[-1],sig=sg.iloc[-1],hist=hst.iloc[-1],hist_prev=hst.iloc[-6:-1].round(3).tolist(),
      E=E,order=order,full_up=bool(full_up),full_dn=bool(full_dn),mode=mode,
      w_rsi=wr.iloc[-1],w_hist=wh.iloc[-1],w_hist_prev=wh.iloc[-5:-1].round(3).tolist(),w_ao=ao.iloc[-1],w_mom=wc.iloc[-1]-wc.iloc[-11],w_e21=ema(wc,21).iloc[-1],w_e34=ema(wc,34).iloc[-1],
      st_d=('yeşil' if dirn.iloc[-1]==1 else 'kırmızı',st.iloc[-1]), st_4h=('yeşil' if d4.iloc[-1]==1 else 'kırmızı',st4.iloc[-1]), st4_last=[(str(i)[5:16],'Y' if v==1 else 'K',round(x,2)) for i,v,x in zip(h.index[-6:],d4.iloc[-6:],st4.iloc[-6:])], e34_4h=e34_4.iloc[-1],
      rs=rsst,rs21=rs21*100,rs63=rs63*100,rs_vs_ema=bool(rs.iloc[-1]>rse.iloc[-1]),rs52pos=(rs.iloc[-1]-rs52.min())/(rs52.max()-rs52.min()),cor=cor,secrs=secrs,
      z=zl,vr5=vr5,nev=len(ev),f5=np.mean(f5)*100 if ev else None,f10=np.mean(f10)*100 if ev else None,pos10=np.mean([x>0 for x in f10])*100 if ev else None,
      perf={k:(cl/c.iloc[-1-n]-1)*100 for k,n in [('1H',5),('1A',21),('3A',63),('6A',126)]}, nbars=len(c))
    out[s]=o
    print('\n==',s,json.dumps({k:(round(v,3) if isinstance(v,float) else v) for k,v in o.items() if k not in ('E','perf','cor')},ensure_ascii=False,default=str))
    print('  E',{k:round(v,2) for k,v in E.items()},'perf',{k:round(v,1) for k,v in o['perf'].items()},'cor',{k:round(v,2) for k,v in cor.items()})
json.dump(out,open('ind.json','w'),default=float)
