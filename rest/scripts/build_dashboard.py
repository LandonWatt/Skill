#!/usr/bin/env python3
"""Build the Rest Smoking Sensor Analytics HTML dashboard.
Usage: python build_dashboard.py <monthly.txt> <daily.txt> <ASOF YYYY-MM-DD> <out.html>
  monthly.txt lines: "Hotel Name|YYYY-MM:billable,charged,net,rest|..."
  daily.txt   lines: "Hotel Name|YYYY-MM-DD:billable,charged,net|..."
Joins keys/go-live/mgmt from reference/keys_golive.json and Capex/Financed from
reference/model_lists.json. Self-contained page (Chart.js from cdnjs).
"""
import sys, json, os
from datetime import date
from calendar import monthrange
monthly_path, daily_path, asof_s, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
here=os.path.dirname(__file__)
ref=json.load(open(os.path.join(here,"..","reference","keys_golive.json")))
ml=json.load(open(os.path.join(here,"..","reference","model_lists.json")))
capex=set(ml["capex"]); fin=set(ml["financed"])
ASOF=date.fromisoformat(asof_s)
MON=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# ---- parse monthly (billable,charged,net,rest) ----
monthly={}; monthset=set()
for ln in open(monthly_path):
    ln=ln.rstrip("\n")
    if not ln or "|" not in ln: continue
    parts=ln.split("|"); nm=parts[0]; mm={}
    for seg in parts[1:]:
        if not seg: continue
        ym,vals=seg.split(":"); b,c,net,rest=vals.split(","); mm[ym]=[int(b),int(c),float(net),float(rest)]; monthset.add(ym)
    if nm in ref: monthly[nm]=mm
MONTHS=sorted(monthset)
def mlbl(ym):
    y,m=ym.split("-"); return MON[int(m)-1]
MLBL={ym:mlbl(ym) for ym in MONTHS}

def days_live(nm,ym):
    gl=date.fromisoformat(ref[nm]["golive"]); y,m=map(int,ym.split("-"))
    ms=date(y,m,1); me=date(y,m,monthrange(y,m)[1]); s=max(ms,gl); e=min(me,ASOF)
    return (e-s).days+1 if e>=s else 0

order=[n for n in sorted(monthly)]
# ---- DATA (monthly inc/chg) ----
dhotels=[]; port={ym:[0,0,0] for ym in MONTHS}
for nm in order:
    keys=ref[nm]["keys"]; mm=monthly[nm]; model="Capex" if nm in capex else ("Financed" if nm in fin else "—")
    months={}
    for ym in MONTHS:
        dl=days_live(nm,ym); b,c,net,rest=mm.get(ym,[0,0,0,0])
        inc=(b/(keys*dl)) if dl>0 else None
        chg=(c/b) if b>0 else (0 if dl>0 else None)
        kd=keys*dl if dl>0 else None
        months[ym]={"inc":inc,"chg":chg,"bil":b,"chgd":c,"kd":kd}
        if dl>0: port[ym][0]+=b; port[ym][1]+=c; port[ym][2]+=keys*dl
    dhotels.append({"name":nm,"mgmt":ref[nm].get("mgmt",""),"model":model,"keys":keys,"golive":ref[nm]["golive"],"months":months})
portfolio={ym:{"inc":(port[ym][0]/port[ym][2] if port[ym][2] else None),"chg":(port[ym][1]/port[ym][0] if port[ym][0] else None)} for ym in MONTHS}
DATA={"asof":asof_s,"months":MONTHS,"mlbl":MLBL,"hotels":dhotels,"portfolio":portfolio}

# ---- FIN (daily + monthly rest) ----
restM={nm:[monthly[nm].get(ym,[0,0,0,0])[3] for ym in MONTHS] for nm in order}
fhotels=[]
daily={}
for ln in open(daily_path):
    ln=ln.rstrip("\n")
    if not ln or "|" not in ln: continue
    parts=ln.split("|"); nm=parts[0]
    if nm not in ref: continue
    dd=[]
    for seg in parts[1:]:
        if not seg: continue
        d,vals=seg.split(":"); b,c,net=vals.split(","); dd.append([d,int(b),int(c),float(net)])
    daily[nm]=dd
for nm in order:
    model="Capex" if nm in capex else ("Financed" if nm in fin else "—")
    fhotels.append({"name":nm,"mgmt":ref[nm].get("mgmt",""),"model":model,"keys":ref[nm]["keys"],"golive":ref[nm]["golive"],"daily":daily.get(nm,[]),"rest":restM.get(nm,[0]*len(MONTHS))})
FIN={"asof":asof_s,"months":MONTHS,"hotels":fhotels}

TEMPLATE=open(os.path.join(here,"dashboard_template.html")).read()
html=TEMPLATE.replace("__DATA__",json.dumps(DATA)).replace("__FIN__",json.dumps(FIN))
open(out,"w").write(html)
print("saved",out,"| hotels",len(order),"| months",",".join(MONTHS))
