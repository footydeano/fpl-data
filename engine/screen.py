#!/usr/bin/env python3
"""Screen players: python screen.py POS MAXPRICE [MINPRICE] [N]"""
import csv
import os

ROOT = os.environ.get("FPL_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROWS = list(csv.DictReader(open(os.path.join(ROOT, "data", "current", "players.csv"), encoding="utf-8")))

pos = sys.argv[1].upper()
maxp = float(sys.argv[2])
minp = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
n = int(sys.argv[4]) if len(sys.argv) > 4 else 20


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


c = [r for r in ROWS if r["pos"] == pos and minp <= f(r["price"]) <= maxp
     and r["status"] == "a"]
c.sort(key=lambda r: (-f(r["ep_next"]), -f(r["selected_by_percent"])))
print("%-18s %-4s %5s %7s %6s %6s %6s %6s" % (
    "NAME", "TEAM", "PRICE", "OWN%", "EPnext", "PPG", "MINS", "PTS"))
for r in c[:n]:
    print("%-18s %-4s %5.1f %7s %6s %6s %6s %6s" % (
        r["web_name"], r["team_short"], f(r["price"]), r["selected_by_percent"],
        r["ep_next"], r["points_per_game"], r["minutes"], r["total_points"]))
