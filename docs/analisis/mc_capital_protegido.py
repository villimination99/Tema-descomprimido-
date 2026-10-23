# Capital protegido: 500 al 1%/op (Normal). Suelo duro: 450 (-10%) -> HALT.
# Bolsa de ataque = 50% de las ganancias realizadas por encima de 500, al 10%/op.
# 12 semanas, 30 ops/semana. Peor caso para el principal: nunca se usa en ataque.
import numpy as np
rng=np.random.default_rng(5); N=20_000; W=12; T=30
for name,(p,R) in {"excepcional 55%/2.5R":(0.55,2.5),"buena 50%/2R":(0.5,2.0),"realista 45%/1.5R":(0.45,1.5),"sin ventaja 40%/1.5R":(0.40,1.5)}.items():
    floor=0;finals=[];atk_end=[]
    for i in range(N):
        base=500.0;atk=0.0;halted=False
        for t in range(W*T):
            if halted:break
            w=rng.random()<p; rb=0.01*base
            base+= rb*R if w else -rb; base-=0.1*rb
            if base<=450: halted=True;floor+=1;break
            if atk>5:
                ra=0.10*atk; w2=rng.random()<p
                atk+= ra*R if w2 else -ra; atk-=0.1*ra
            if (t+1)%T==0 and base>500:  # cierre semanal: mitad de la ganancia a la bolsa de ataque
                g=base-500; atk+=g/2; base-=g/2
        finals.append(base+atk)
    f=np.array(finals)
    print(f"{name:22s} P(tocar suelo -10%)={floor/N*100:5.1f}%  P(acabar <500)={np.mean(f<500)*100:5.1f}%  P(>=1000)={np.mean(f>=1000)*100:5.1f}%")
