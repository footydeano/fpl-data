#!/usr/bin/env python3
"""Verify a named squad against data/current/players.csv (API truth)."""
import csv
import os

ROOT = os.environ.get("FPL_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROWS = list(csv.DictReader(open(os.path.join(ROOT, "data", "current", "players.csv"), encoding="utf-8")))

SQUAD = [
    ("Verbruggen", "BHA"), ("Kinsky", "TOT"), ("Calafiori", "ARS"),
    ("Mosquera", "ARS"), ("Shaw", "MUN"), ("Aina", "NFO"), ("Hume", "SUN"),
    ("Fernandes", "MUN"), ("Mbeumo", "MUN"), ("Szoboszlai", "LIV"),
    ("Ndiaye", "EVE"), ("Yates", "NFO"), ("Haaland", "MCI"),
    ("Pedro", "CHE"), ("Calvert-Lewin", "LEE"),
]

total = 0.0
counts = {}
print("%-16s %-4s %-4s %6s %4s %5s %7s %6s  %s" % (
    "NAME", "TEAM", "POS", "PRICE", "ST", "CHNC", "OWN%", "EPnext", "NEWS"))
for name, team in SQUAD:
    hits = [r for r in ROWS if r["team_short"] == team
            and name.lower() in r["web_name"].lower()]
    if not hits:
        print("!! NOT FOUND: %s (%s)" % (name, team))
        continue
    r = sorted(hits, key=lambda x: -float(x["price"]))[0]
    total += float(r["price"])
    counts[team] = counts.get(team, 0) + 1
    print("%-16s %-4s %-4s %6.1f %4s %5s %7s %6s  %s" % (
        r["web_name"], r["team_short"], r["pos"], float(r["price"]),
        r["status"], r["chance_next"] or "-", r["selected_by_percent"],
        r["ep_next"], (r["news"] or "")[:55]))

print("\nTOTAL: %.1f   ITB: %.1f" % (total, 100.0 - total))
over = {k: v for k, v in counts.items() if v > 3}
print("CLUB COUNTS:", dict(sorted(counts.items(), key=lambda kv: -kv[1])))
print("CLUB LIMIT BREACH:", over if over else "none")
