import numpy as np
rng=np.random.default_rng(7)
N=100_000
def run(p,R,f,trades,cost_r=0.1):
    w=rng.random((N,trades))<p
    r=np.where(w,R*f,-f)-cost_r*f   # cost as fraction of R
    eq=np.cumprod(1+r,axis=1)
    final=eq[:,-1]; mn=eq.min(axis=1)
    return final,mn
edges={"bueno (50% acierto, 2R)":(0.50,2.0),"realista (45% acierto, 1.5R)":(0.45,1.5)}
for name,(p,R) in edges.items():
    print(f"\n== Ventaja {name}, 20 ops/semana ==")
    print("riesgo/op | semana: mediana  P(x2)  | 4 semanas: mediana  P(x2+)  P(cae>50%)  P(queda<10%)")
    for f in [0.01,0.02,0.05,0.10,0.20,0.30]:
        f1,_=run(p,R,f,20); f4,m4=run(p,R,f,80)
        print(f"{f*100:5.0f}%    | {np.median(f1):6.2f}x  {np.mean(f1>=2)*100:5.1f}% | {np.median(f4):7.2f}x  {np.mean(f4>=2)*100:5.1f}%  {np.mean(m4<0.5)*100:6.1f}%   {np.mean(f4<0.1)*100:6.1f}%")
