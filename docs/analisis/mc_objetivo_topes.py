# Objetivo +800 USDT/semana con los topes reales del diseño:
# base 350 al 2% (Normal), ataque 150 al 10% (Ataque). Ops repartidas 50/50.
import numpy as np
rng=np.random.default_rng(3); N=100_000
def bucket(cap,p,R,f,t,c=0.1):
    w=rng.random((N,t))<p
    return cap*np.cumprod(1+np.where(w,R*f,-f)-c*f,axis=1)[:,-1]
for name,(p,R) in {"excepcional 55%/2.5R":(0.55,2.5),"buena 50%/2R":(0.5,2.0),"realista 45%/1.5R":(0.45,1.5)}.items():
    for t in [20,40]:
        tot=bucket(350,p,R,0.02,t//2)+bucket(150,p,R,0.10,t//2)
        g=tot-500
        print(f"{name:22s} {t} ops: P(+800)={np.mean(g>=800)*100:5.1f}%  mediana ganancia={np.median(g):7.1f}  P(perder>150)={np.mean(g<=-150)*100:5.1f}%")
