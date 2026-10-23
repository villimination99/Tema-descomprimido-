import numpy as np
rng=np.random.default_rng(11); N=100_000
def run(p,R,f,t,c=0.1):
    w=rng.random((N,t))<p
    eq=np.cumprod(1+np.where(w,R*f,-f)-c*f,axis=1); return eq[:,-1],eq.min(axis=1)
for name,(p,R) in {"excepcional 55%/2.5R":(0.55,2.5),"buena 50%/2R":(0.5,2.0),"realista 45%/1.5R":(0.45,1.5)}.items():
  print(f"\n== {name} ==  (kelly={p-(1-p)/R:.2f})")
  for t in [20,40]:
    for f in [0.05,0.10,0.15,0.20,0.30]:
      f1,m1=run(p,R,f,t)
      print(f" {t} ops/sem riesgo {f*100:4.0f}%: P(>=+800$ semana)={np.mean(f1>=2.6)*100:5.1f}%  P(>=+1000$)={np.mean(f1>=3)*100:5.1f}%  P(perder>50% en la semana)={np.mean(m1<0.5)*100:5.1f}%  P(acabar<100$)={np.mean(f1<0.2)*100:5.1f}%")
