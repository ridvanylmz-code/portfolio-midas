import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
import json
S=['BIENY','SASA','SMRTG','MIATK']; SEC={'BIENY':'XTAST','SASA':'XKMYA','SMRTG':'XUSIN','MIATK':'XBLSM'}
xu=load('XU100'); out={}
xc=xu.c; A,P_,M_=adx(xu)
print('XU100',xc.iloc[-1],'EMA89',round(ema(xc,89).iloc[-1]),'EMA233',round(ema(xc,233).iloc[-1]),'ADX',round(A.iloc[-1],1),round(P_.iloc[-1],1),round(M_.iloc[-1],1),'EMA21',round(ema(xc,21).iloc[-1]))
for s in S:
    d=load(s); c=d.c; a=atr(d); A,Pd,Md=adx(d); m,sg,hst=macd(c); r=rsi(c)
    E={n:ema(c,n).iloc[-1] for n in [21,34,89,144,233]}
    w=weekly(d); wc=w.c; wm,ws,wh=macd(wc); wr=rsi(wc); ao=((w.h+w.l)/2).rolling(5).mean()-((w.h+w.l)/2).rolling(34).mean()
    dirn,st=supertrend(d,10,2)
    h=pd.read_pickle(P+f'{s}_4h.pkl').set_index('dt')[['o','h','l','c']]
    d4,st4=supertrend(h,10,2); e34_4=ema(h.c,34)
    cl=c.iloc[-1]; adxv=A.iloc[-1]
    if cl>E[21]>E[34]>E[89] and adxv>25 and Pd.iloc[-1]>Md.iloc[-1]: mode='Trend'
    elif cl<E[21]<E[34]<E[89] and adxv>25 and Md.iloc[-1]>Pd.iloc[-1]: mode='Savunma'
    else: mode='Bant'
    rs=(c/xu.c.reindex(c.index).ffill()).dropna(); rse=ema(rs,21)
    rs21=rs.iloc[-1]/rs.iloc[-22]-1; rs63=rs.iloc[-1]/rs.iloc[-64]-1
    rsst='Güçlü' if rs.iloc[-1]>rse.iloc[-1] and rs63>0 else ('Zayıf' if rs.iloc[-1]<rse.iloc[-1] and rs63<0 else 'Nötr')
    ret=c.pct_change().iloc[-120:]; x=load(SEC[s]).c
    cor={'XU100':ret.corr(xu.c.pct_change().reindex(ret.index)),SEC[s]:ret.corr(x.pct_change().reindex(ret.index))}
    rr=(c/x.reindex(c.index).ffill()).dropna(); secrs=(round((rr.iloc[-1]/rr.iloc[-22]-1)*100,1),round((rr.iloc[-1]/rr.iloc[-64]-1)*100,1))
    z=(c-ema(c,21))/a; zl=z.iloc[-1]
    lr=np.log(c).diff().iloc[-120:]; vr5=(np.log(c).diff(5).iloc[-120:].var())/(5*lr.var())
    idx=[i for i in range(30,len(c)-10) if abs(z.iloc[i]-zl)<=0.5]; ev=[];last=-99
    for i in idx:
        if i-last>=5: ev.append(i); last=i
    f5=[c.iloc[i+5]/c.iloc[i]-1 for i in ev]; f10=[c.iloc[i+10]/c.iloc[i]-1 for i in ev]
    o=dict(close=cl,atr=a.iloc[-1],rsi=r.iloc[-1],adx=adxv,pdi=Pd.iloc[-1],mdi=Md.iloc[-1],hist=hst.iloc[-1],hist_prev=hst.iloc[-6:-1].round(3).tolist(),E=E,mode=mode,
      w_rsi=wr.iloc[-1],w_hist=wh.iloc[-1],w_hist_prev=wh.iloc[-5:-1].round(3).tolist(),w_e21=ema(wc,21).iloc[-1],w_e34=ema(wc,34).iloc[-1],
      st_d=('yeşil' if dirn.iloc[-1]==1 else 'kırmızı',st.iloc[-1]),st_4h=('yeşil' if d4.iloc[-1]==1 else 'kırmızı',st4.iloc[-1]),st4_last=[(str(i)[5:16],int(v),round(x_,3)) for i,v,x_ in zip(h.index[-4:],d4.iloc[-4:],st4.iloc[-4:])],e34_4h=e34_4.iloc[-1],
      rs=rsst,rs21=rs21*100,rs63=rs63*100,cor=cor,secrs=secrs,z=zl,vr5=vr5,nev=len(ev),f5=np.mean(f5)*100 if ev else None,f10=np.mean(f10)*100 if ev else None,pos10=np.mean([q>0 for q in f10])*100 if ev else None,nbars=len(c),
      perf={k:(cl/c.iloc[-1-n]-1)*100 for k,n in [('1H',5),('1A',21),('3A',63)]})
    out[s]=o
    print('\n==',s,json.dumps({k:(round(v,3) if isinstance(v,float) else v) for k,v in o.items() if k not in ('E','perf','cor')},ensure_ascii=False,default=str))
    print('  E',{k:round(v,3) for k,v in E.items()},'perf',{k:round(v,1) for k,v in o['perf'].items()},'cor',{k:round(v,2) for k,v in cor.items()})
    print('  last8',d.tail(8)[['o','h','l','c']].round(3).values.tolist())
json.dump(out,open('indb.json','w'),default=float)
