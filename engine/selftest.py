"""End-to-end smoke test on synthetic data (no network needed)."""
import csv
import os

ROOT = os.environ.get("FPL_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), os, tempfile, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp()
os.environ["FPL_ROOT"] = tmp
cur = os.path.join(tmp, "data", "current"); os.makedirs(cur)

fx = [("1","2026-08-21T19:00:00Z","ARS","COV",2,5),("1","2026-08-22T14:00:00Z","MCI","BOU",2,4),
      ("2","2026-08-28T19:00:00Z","CRY","MCI",4,3),("2","2026-08-29T14:00:00Z","MUN","IPS",2,4),
      ("3","2026-09-04T19:00:00Z","ARS","MUN",3,4),("4","2026-09-12T14:00:00Z","MCI","ARS",3,3),
      ("5","2026-09-18T19:00:00Z","CRY","BOU",3,3)]
with open(os.path.join(cur,"fixtures.csv"),"w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["id","gw","kickoff_utc","home","away","home_fdr","away_fdr","finished","home_score","away_score"])
    for i,(gw,ko,h,a,hf,af) in enumerate(fx): w.writerow([i,gw,ko,h,a,hf,af,False,"",""])

import context, minutes, xp, decisions
rows = context.build()
print("context rows:", len(rows))
mci2 = [r for r in rows if r["gw"]==2 and r["club"]=="MCI"][0]
ars4 = [r for r in rows if r["gw"]==4 and r["club"]=="ARS"][0]
print("GW2 MCI @CRY  rest=%sd euro_gap=%s travel=%skm load=%.2f asym=%+.2f"
      % (mci2["rest_days"], mci2["euro_gap_days"] or "-", mci2["travel_km"], mci2["congestion"], mci2["asymmetry"]))
print("GW4 ARS @MCI  rest=%sd euro_gap=%s travel=%skm load=%.2f asym=%+.2f"
      % (ars4["rest_days"], ars4["euro_gap_days"] or "-", ars4["travel_km"], ars4["congestion"], ars4["asymmetry"]))

squad=[{"web_name":"Haaland","pos":"FWD","team_short":"MCI","minutes":2900,"starts":33,
        "goals_scored":31,"expected_goals":27.5,"expected_assists":4.0,"bps":820,
        "defensive_contribution":30,"saves":0,"yellow_cards":3,"red_cards":0,"status":"a","chance_next":None},
       {"web_name":"Marmoush","pos":"FWD","team_short":"MCI","minutes":900,"starts":8,
        "goals_scored":6,"expected_goals":5.5,"expected_assists":3.0,"bps":190,
        "defensive_contribution":25,"saves":0,"yellow_cards":2,"red_cards":0,"status":"a","chance_next":None}]

for p in squad:
    m = minutes.project(p, squad, mci2["congestion"], matches_played=38)
    proj = xp.expected_points(p, m, {"xg_for":2.1,"xga":1.15,"fdr":3,"is_home":False})
    print("  %-10s p_start=%.2f xmins=%4.1f  xP=%.2f  ceiling=%.2f  [%s]"
          % (p["web_name"], m["p_start"], m["xmins"], proj["xp"], proj["ceiling"], m["rotation_risk"]))

cands=[{"name":"Haaland","xp":6.4,"ceiling":15.2,"p_start":0.93,"eo":128.0},
       {"name":"B.Fernandes","xp":5.9,"ceiling":14.1,"p_start":0.95,"eo":74.0},
       {"name":"Ndiaye","xp":4.4,"ceiling":11.8,"p_start":0.88,"eo":17.0}]
r=decisions.captain_rank(cands)
print("\ncaptaincy  safe=%s  optimal=%s  punt=%s"
      % (r["safe"]["name"], r["optimal"]["name"], r["punt"]["name"] if r["punt"] else "-"))
t=decisions.evaluate_transfer("Calvert-Lewin","Sangare",[2.1,2.3,2.0,2.2,2.1],[3.4,3.6,3.2,3.5,3.3],hit=0)
print("transfer  %s->%s  5GW %+0.2f  %s" % (t["out"],t["in"],t["gain_5gw"],t["verdict"]))
print("\nSELFTEST PASS")
