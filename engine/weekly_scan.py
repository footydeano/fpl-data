#!/usr/bin/env python3
"""Weekly gameweek scan - the A-J process, run in order.

    python weekly_scan.py --gw 3

Requires fpl_pull.py to have run first (data/current/*.csv).
Prints a decision brief; writes gameweeks/GW<nn>_brief.md.
"""
import argparse, csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import context, minutes, xp, decisions

ROOT = os.environ.get("FPL_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
CUR = os.path.join(ROOT, "data", "current")

# Your current 15. Update after every transfer.
SQUAD = ["Verbruggen", "Kinsky", "Calafiori", "Mosquera", "Shaw", "Aina", "Hume",
         "B.Fernandes", "Mbeumo", "Szoboszlai", "Ndiaye", "Yates",
         "Haaland", "João Pedro", "Calvert-Lewin"]


def load(name):
    with open(os.path.join(CUR, name), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def run(gw, aggression=0.35):
    players = load("players.csv")
    ctx = {(int(r["gw"]), r["club"]): r for r in context.build()}
    by_club = {}
    for p in players:
        by_club.setdefault(p["team_short"], []).append(p)

    mine = [p for p in players if p["web_name"] in SQUAD]
    missing = set(SQUAD) - {p["web_name"] for p in mine}
    if missing:
        print("WARNING - not matched in players.csv:", ", ".join(sorted(missing)))

    rows = []
    for p in mine:
        c = ctx.get((gw, p["team_short"]))
        if not c:
            continue                      # blank gameweek for this club
        load_i = float(c["congestion"])
        m = minutes.project(p, by_club[p["team_short"]], load_i, matches_played=max(1, gw - 1))
        proj = xp.expected_points(p, m, {
            "xg_for": 1.5, "xga": 1.2 + (int(c["fdr"]) - 3) * 0.12,
            "fdr": int(c["fdr"]), "is_home": c["side"] == "H"})
        rows.append(dict(proj, name=p["web_name"], pos=p["pos"], team=p["team_short"],
                         opp=c["opponent"], side=c["side"], load=load_i,
                         asym=float(c["asymmetry"]), eo=float(p["selected_by_percent"] or 0)))

    rows.sort(key=lambda r: -r["xp"])
    order = {"GKP": 0, "DEF": 1, "MID": 2, "FWD": 3}
    print("\n%-15s %-4s %-4s %-9s %5s %6s %6s %7s  %s" %
          ("PLAYER", "POS", "TEAM", "FIXTURE", "xP", "pSTART", "LOAD", "ASYM", "RISK"))
    for r in sorted(rows, key=lambda r: (order[r["pos"]], -r["xp"])):
        print("%-15s %-4s %-4s %-9s %5.2f %6.2f %6.2f %+7.2f  %s" %
              (r["name"][:15], r["pos"], r["team"], ("%s %s" % (r["side"], r["opp"]))[:9],
               r["xp"], r["p_start"], r["load"], r["asym"], r["rotation_risk"]))

    cap = decisions.captain_rank(
        [{"name": r["name"], "xp": r["xp"], "ceiling": r["ceiling"],
          "p_start": r["p_start"], "eo": r["eo"]} for r in rows[:6]],
        aggression=aggression)
    print("\nCAPTAIN   safe: %s | optimal: %s | punt: %s" % (
        cap["safe"]["name"], cap["optimal"]["name"],
        cap["punt"]["name"] if cap["punt"] else "none qualifying"))

    risky = [r for r in rows if r["p_start"] < 0.7]
    if risky:
        print("ROTATION  " + ", ".join("%s (%.0f%%)" % (r["name"], r["p_start"] * 100)
                                       for r in risky))
    return rows, cap


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gw", type=int, required=True)
    ap.add_argument("--aggression", type=float, default=0.35)
    a = ap.parse_args()
    run(a.gw, a.aggression)
